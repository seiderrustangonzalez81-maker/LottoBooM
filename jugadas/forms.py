from django import forms
from .models import Jugada, FormaJuego
from sorteos.models import Sorteo
from pagos.models import FormaPago


class ApostarForm(forms.ModelForm):
    class Meta:
        model = Jugada
        fields = ['sorteo', 'forma_juego', 'numero', 'monto', 'forma_pago']
        widgets = {
            'sorteo': forms.Select(attrs={'class': 'form-control', 'id': 'id_sorteo'}),
            'forma_juego': forms.Select(attrs={'class': 'form-control', 'id': 'id_forma_juego'}),
            'numero': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_numero', 'placeholder': 'Ej: 123'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_monto', 'placeholder': '0.00', 'step': '0.01'}),
            'forma_pago': forms.Select(attrs={'class': 'form-control', 'id': 'id_forma_pago'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sorteo'].queryset = Sorteo.objects.filter(activo=True)
        self.fields['forma_juego'].queryset = FormaJuego.objects.filter(activo=True)
        self.fields['forma_pago'].queryset = FormaPago.objects.filter(activo=True)

    def clean_numero(self):
        numero = self.cleaned_data.get('numero')
        if not numero:
            raise forms.ValidationError("El número es obligatorio.")
        return numero

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto is None or monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor a 0.")
        return monto
