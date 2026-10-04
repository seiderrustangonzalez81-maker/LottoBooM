from django import forms
from .models import Resultado

class ResultadoForm(forms.ModelForm):
    class Meta:
        model = Resultado
        fields = ['sorteo', 'fecha', 'hora', 'numeros', 'activo']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'hora': forms.TimeInput(attrs={'type': 'time'}),
            'numeros': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Ej: {"pick2": "12", "pick3": "123"}'}),
        }
        help_texts = {
            'numeros': 'Ingresa los números ganadores en formato JSON. Ej: {"pick2": "12", "pick3": "123"}',
        }