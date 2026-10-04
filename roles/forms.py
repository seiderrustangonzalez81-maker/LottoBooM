# roles/forms.py
# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError

from .models import ViaPago
from pagos.models import FormaPago


# Formas de pago que usan tarjeta (16 dígitos + teléfono)
FORMAS_TARJETA = {'Tarjeta', 'Clásica', 'MLC'}

# Formas de pago que usan solo teléfono
FORMAS_TELEFONO = {'Saldo móvil', 'Monedero', 'Zelle'}


class ViaPagoForm(forms.ModelForm):
    class Meta:
        model = ViaPago
        fields = ['forma_pago', 'nombre', 'numero', 'numero_tarjeta', 'telefono']
        widgets = {
            'forma_pago': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Visa Personal',
                'required': True,
            }),
            'numero': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Alias / identificador corto',
            }),
            'numero_tarjeta': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '1234 5678 9012 3456',
                'maxlength': '19',
                'inputmode': 'numeric',
                'autocomplete': 'off',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+53 5555 0001',
                'inputmode': 'tel',
                'autocomplete': 'off',
            }),
        }
        labels = {
            'forma_pago': 'Forma de Pago',
            'nombre': 'Nombre / Alias de la vía',
            'numero': 'Identificador interno',
            'numero_tarjeta': 'Número de tarjeta',
            'telefono': 'Teléfono',
        }

    def __init__(self, *args, **kwargs):
        self.gestor = kwargs.pop('gestor', None)
        super().__init__(*args, **kwargs)
        # Solo formas activas (Bono y Cash están desactivados en DB)
        self.fields['forma_pago'].queryset = (
            FormaPago.objects.filter(activo=True)
            .order_by('nombre')
        )
        if not self.fields['forma_pago'].queryset.exists():
            self.fields['forma_pago'].choices = [('', 'No hay formas de pago disponibles')]
            self.fields['forma_pago'].widget.attrs['disabled'] = True

        # El campo 'numero' no es obligatorio (queda como alias interno)
        self.fields['numero'].required = False
        self.fields['numero_tarjeta'].required = False
        self.fields['telefono'].required = False

    def clean(self):
        cleaned_data = super().clean()
        forma_pago = cleaned_data.get('forma_pago')
        nombre = cleaned_data.get('nombre')
        numero_tarjeta = (cleaned_data.get('numero_tarjeta') or '').strip()
        telefono = (cleaned_data.get('telefono') or '').strip()

        if not forma_pago or not nombre:
            return cleaned_data

        nombre_fp = forma_pago.nombre.lower()

        # Tarjeta / Clásica / MLC → requiere tarjeta + teléfono
        if forma_pago.nombre in FORMAS_TARJETA:
            if not numero_tarjeta:
                raise ValidationError('El número de tarjeta es obligatorio para esta forma de pago.')
            if not telefono:
                raise ValidationError('El teléfono es obligatorio para esta forma de pago.')

            # Limpiar espacios y validar 16 dígitos
            digitos = numero_tarjeta.replace(' ', '').replace('-', '')
            if not digitos.isdigit():
                raise ValidationError('El número de tarjeta debe contener solo dígitos.')
            if len(digitos) != 16:
                raise ValidationError('El número de tarjeta debe tener exactamente 16 dígitos.')
            cleaned_data['numero_tarjeta'] = ' '.join(digitos[i:i+4] for i in range(0, 16, 4))

        # Saldo móvil / Monedero / Zelle → solo teléfono
        elif forma_pago.nombre in FORMAS_TELEFONO:
            if not telefono:
                raise ValidationError('El teléfono es obligatorio para esta forma de pago.')
            if numero_tarjeta:
                cleaned_data['numero_tarjeta'] = None

        # Efectivo → solo nombre (sin datos de vía)
        elif forma_pago.nombre.lower() == 'efectivo':
            cleaned_data['numero_tarjeta'] = None
            cleaned_data['telefono'] = None

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.gestor and not instance.pk:
            instance.gestor = self.gestor
        instance.tipo = 'otros'
        instance.direccion = 'ambos'
        instance.activo = True
        # Generar 'numero' con lo que tenga (alias interno)
        if not instance.numero:
            if instance.numero_tarjeta:
                instance.numero = instance.numero_tarjeta.replace(' ', '')
            elif instance.telefono:
                instance.numero = instance.telefono
            else:
                instance.numero = (instance.nombre or 'sin-numero')[:50]
        if commit:
            instance.save()
        return instance
