# -*- coding: utf-8 -*-
import re
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import Perfil


def validar_telefono_internacional(value):
    """Valida y limpia un número de teléfono con código de país."""
    if not value:
        return value
    # Eliminar espacios, guiones, paréntesis, puntos
    limpio = re.sub(r'[\s\-\(\)\.]', '', value)
    if not re.match(r'^\+\d+$', limpio):
        raise ValidationError("El número debe empezar con '+' seguido de dígitos.")
    if len(limpio) < 5:
        raise ValidationError("El número debe tener al menos 4 dígitos después del código de país.")
    if len(limpio) > 18:
        raise ValidationError("El número es demasiado largo.")
    return limpio


class RegistroForm(UserCreationForm):
    email = forms.EmailField(
        label='Correo electrónico',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'ejemplo@correo.com'
        }),
    )
    telefono = forms.CharField(
        label='Teléfono',
        max_length=20,
        required=True,
        validators=[validar_telefono_internacional],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+5355551234'
        }),
        help_text='Debe incluir el código de país (ej: +53)',
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'telefono', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicar clases de Bootstrap
        for field_name, field in self.fields.items():
            if 'class' in field.widget.attrs:
                continue
            field.widget.attrs['class'] = 'form-control'
        self.fields['username'].widget.attrs['placeholder'] = 'Nombre de usuario'
        self.fields['username'].help_text = (
            'Requerido. 150 caracteres o menos. Letras, dígitos y @/./+/-/_ solamente.'
        )
        self.fields['password1'].widget.attrs['placeholder'] = 'Contraseña'
        self.fields['password1'].help_text = 'La contraseña debe tener al menos 8 caracteres.'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirmar contraseña'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError('Ya existe un usuario con este correo electrónico.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        # No se asignan first_name ni last_name (quedan vacíos)
        if commit:
            user.save()
            perfil, _ = Perfil.objects.get_or_create(usuario=user)
            perfil.telefono = self.cleaned_data['telefono']
            if not perfil.codigo_referido:
                perfil.codigo_referido = perfil.generar_codigo_referido()
            perfil.save()
        return user


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label='Usuario',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Usuario'})
    )
    telefono = forms.CharField(
        max_length=20,
        label='Teléfono',
        validators=[validar_telefono_internacional],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Teléfono (ej: +5355551234)'
        })
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'})
    )


class EditarPerfilForm(forms.ModelForm):
    email = forms.EmailField(
        label='Correo electrónico',
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    telefono = forms.CharField(
        label='Teléfono',
        max_length=20,
        required=True,
        validators=[validar_telefono_internacional],
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+5355551234'})
    )

    class Meta:
        model = User
        fields = ['username', 'email']

    def __init__(self, *args, **kwargs):
        self.perfil_instance = kwargs.pop('perfil_instance', None)
        super().__init__(*args, **kwargs)
        if self.perfil_instance:
            self.fields['telefono'].initial = self.perfil_instance.telefono
        self.fields['username'].widget.attrs['readonly'] = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            qs = User.objects.filter(email=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('Ya existe otro usuario con este correo electrónico.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            if self.perfil_instance:
                self.perfil_instance.telefono = self.cleaned_data['telefono']
                self.perfil_instance.save()
        return user