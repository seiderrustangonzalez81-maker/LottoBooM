# comercial/forms.py

from django import forms
from django.contrib.auth.models import User
from roles.models import Subordinacion
from pagos.models import FormaPago
from sorteos.models import Sorteo


class AsignarClienteForm(forms.Form):
    """Formulario para asignar un cliente a un comercial"""

    cliente = forms.ModelChoiceField(
        queryset=User.objects.filter(roles__tipo="cliente", roles__activo=True),
        label="Cliente",
        help_text="Selecciona un cliente para asignar",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        self.comercial = kwargs.pop('comercial', None)
        super().__init__(*args, **kwargs)

        # Filtrar clientes que ya tienen un comercial asignado
        if self.comercial:
            clientes_asignados = Subordinacion.objects.filter(
                jefe=self.comercial,
                activo=True
            ).values_list('subordinado_id', flat=True)

            self.fields['cliente'].queryset = self.fields['cliente'].queryset.exclude(
                id__in=clientes_asignados
            )

    def clean_cliente(self):
        cliente = self.cleaned_data.get('cliente')

        # Verificar que el cliente no esté ya asignado a otro comercial
        if self.comercial:
            ya_asignado = Subordinacion.objects.filter(
                subordinado=cliente,
                activo=True
            ).exclude(jefe=self.comercial).exists()

            if ya_asignado:
                raise forms.ValidationError("Este cliente ya está asignado a otro comercial.")

        return cliente


class AsignarFondoForm(forms.Form):
    """Formulario para asignar fondos a un cliente"""

    monto = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        label="Monto a asignar",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        })
    )
    forma_pago = forms.ModelChoiceField(
        queryset=FormaPago.objects.filter(activo=True),
        label="Forma de pago",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    sorteo = forms.ModelChoiceField(
        queryset=Sorteo.objects.filter(activo=True),
        label="Sorteo (opcional)",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    nota = forms.CharField(
        max_length=200,
        required=False,
        label="Nota",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Nota opcional sobre esta asignación'
        })
    )

    def __init__(self, *args, **kwargs):
        self.cliente = kwargs.pop('cliente', None)
        self.comercial = kwargs.pop('comercial', None)
        super().__init__(*args, **kwargs)

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor a 0.")
        return monto


class BuscarClienteForm(forms.Form):
    """Formulario para buscar clientes"""

    query = forms.CharField(
        max_length=100,
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre, email o teléfono...'
        })
    )
    tipo = forms.ChoiceField(
        choices=[
            ('todos', 'Todos'),
            ('asignados', 'Mis clientes'),
            ('no_asignados', 'Sin comercial'),
        ],
        required=False,
        label="Filtro",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        self.comercial = kwargs.pop('comercial', None)
        super().__init__(*args, **kwargs)

    def filter_queryset(self, queryset):
        """Aplica los filtros al queryset"""
        from django.db import models
        query = self.cleaned_data.get('query', '')
        tipo = self.cleaned_data.get('tipo', 'todos')

        if query:
            queryset = queryset.filter(
                models.Q(username__icontains=query) |
                models.Q(email__icontains=query) |
                models.Q(perfil__telefono__icontains=query)
            )

        if tipo == 'asignados' and self.comercial:
            clientes_ids = Subordinacion.objects.filter(
                jefe=self.comercial,
                activo=True
            ).values_list('subordinado_id', flat=True)
            queryset = queryset.filter(id__in=clientes_ids)

        elif tipo == 'no_asignados':
            clientes_con_comercial = Subordinacion.objects.filter(
                activo=True
            ).values_list('subordinado_id', flat=True)
            queryset = queryset.exclude(id__in=clientes_con_comercial)

        return queryset


class ApostarParaClienteForm(forms.Form):
    """Formulario para apostar por un cliente (desde comercial)"""

    cliente = forms.ModelChoiceField(
        queryset=User.objects.filter(roles__tipo="cliente", roles__activo=True),
        label="Cliente",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    sorteo = forms.ModelChoiceField(
        queryset=Sorteo.objects.filter(activo=True),
        label="Sorteo",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    forma_juego = forms.ModelChoiceField(
        queryset=None,  # Se llenará en __init__
        label="Forma de juego",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    forma_pago = forms.ModelChoiceField(
        queryset=FormaPago.objects.filter(activo=True),
        label="Forma de pago",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    numero = forms.CharField(
        max_length=20,
        label="Número",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 123'
        })
    )
    monto = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        label="Monto",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        })
    )

    def __init__(self, *args, **kwargs):
        self.comercial = kwargs.pop('comercial', None)
        super().__init__(*args, **kwargs)

        from jugadas.models import FormaJuego
        self.fields['forma_juego'].queryset = FormaJuego.objects.filter(activo=True)

        # Filtrar clientes asignados a este comercial
        if self.comercial:
            clientes_ids = Subordinacion.objects.filter(
                jefe=self.comercial,
                activo=True
            ).values_list('subordinado_id', flat=True)

            self.fields['cliente'].queryset = self.fields['cliente'].queryset.filter(
                id__in=clientes_ids
            )

    def clean_numero(self):
        numero = self.cleaned_data.get('numero')
        forma_juego = self.cleaned_data.get('forma_juego')

        if forma_juego and forma_juego.digitos_esperados:
            digitos = len(str(numero).strip())
            if digitos != forma_juego.digitos_esperados:
                raise forms.ValidationError(
                    f"Este juego requiere {forma_juego.digitos_esperados} dígitos. "
                    f"Has ingresado {digitos}."
                )

        return numero

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor a 0.")
        return monto