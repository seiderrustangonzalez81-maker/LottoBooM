# ubicaciones/forms.py

from django import forms
from .models import UbicacionUsuario


class UbicacionForm(forms.ModelForm):
    """Formulario para registrar/editar ubicaciones"""

    class Meta:
        model = UbicacionUsuario
        fields = ['telefono', 'direccion', 'ciudad', 'provincia', 'latitud', 'longitud']
        widgets = {
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+53 5555 5555'
            }),
            'direccion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Calle 123 #456'
            }),
            'ciudad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'La Habana'
            }),
            'provincia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'La Habana'
            }),
            'latitud': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '23.113592',
                'step': '0.000001'
            }),
            'longitud': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '-82.366596',
                'step': '0.000001'
            }),
        }

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono')
        if telefono:
            import re
            telefono = re.sub(r'[\s\-\(\)]', '', telefono)
        return telefono

    def clean_latitud(self):
        latitud = self.cleaned_data.get('latitud')
        if latitud is not None and (latitud < -90 or latitud > 90):
            raise forms.ValidationError("La latitud debe estar entre -90 y 90")
        return latitud

    def clean_longitud(self):
        longitud = self.cleaned_data.get('longitud')
        if longitud is not None and (longitud < -180 or longitud > 180):
            raise forms.ValidationError("La longitud debe estar entre -180 y 180")
        return longitud


class BuscarUbicacionForm(forms.Form):
    """Formulario para buscar ubicaciones"""

    telefono = forms.CharField(
        max_length=20,
        required=False,
        label="Teléfono",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por teléfono...'
        })
    )
    ciudad = forms.CharField(
        max_length=100,
        required=False,
        label="Ciudad",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ciudad...'
        })
    )
    provincia = forms.CharField(
        max_length=100,
        required=False,
        label="Provincia",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Provincia...'
        })
    )

    def filter_queryset(self, queryset):
        """Aplica los filtros al queryset"""
        telefono = self.cleaned_data.get('telefono', '').strip()
        ciudad = self.cleaned_data.get('ciudad', '').strip()
        provincia = self.cleaned_data.get('provincia', '').strip()

        if telefono:
            queryset = queryset.filter(telefono__icontains=telefono)

        if ciudad:
            queryset = queryset.filter(ciudad__icontains=ciudad)

        if provincia:
            queryset = queryset.filter(provincia__icontains=provincia)

        return queryset