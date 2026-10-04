# pagos/forms.py

from django import forms
from django.contrib.auth.models import User
from .models import Pago, FormaPago


class CrearPagoForm(forms.ModelForm):
    """Formulario para crear un pago"""

    class Meta:
        model = Pago
        fields = ['usuario', 'cantidad', 'metodo', 'referencia', 'nota']
        widgets = {
            'usuario': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'metodo': forms.Select(attrs={'class': 'form-select'}),
            'referencia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de referencia'
            }),
            'nota': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Nota opcional'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.usuario_logueado = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)

        # Si el usuario es comercial, solo mostrar sus clientes
        if self.usuario_logueado:
            from roles.models import Subordinacion, Rol

            es_comercial = Rol.objects.filter(
                usuario=self.usuario_logueado,
                tipo='comercial',
                activo=True
            ).exists()

            if es_comercial:
                clientes_ids = Subordinacion.objects.filter(
                    jefe=self.usuario_logueado,
                    activo=True
                ).values_list('subordinado_id', flat=True)

                self.fields['usuario'].queryset = User.objects.filter(
                    id__in=clientes_ids
                )

            # Si es banco, mostrar comerciales y clientes
            es_banco = Rol.objects.filter(
                usuario=self.usuario_logueado,
                tipo='banco',
                activo=True
            ).exists()

            if es_banco:
                subordinados_ids = Subordinacion.objects.filter(
                    jefe=self.usuario_logueado,
                    activo=True
                ).values_list('subordinado_id', flat=True)

                self.fields['usuario'].queryset = User.objects.filter(
                    id__in=subordinados_ids
                )

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor a 0.")
        return cantidad


class CambiarEstadoPagoForm(forms.Form):
    """Formulario para cambiar estado de un pago"""

    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('rechazado', 'Rechazado'),
        ('cancelado', 'Cancelado'),
    ]

    estado = forms.ChoiceField(
        choices=ESTADOS,
        label="Nuevo estado",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    nota = forms.CharField(
        max_length=200,
        required=False,
        label="Nota",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Razón del cambio de estado...'
        })
    )