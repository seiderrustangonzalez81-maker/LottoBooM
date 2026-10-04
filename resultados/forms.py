from django import forms
from .models import Resultado
from sorteos.models import Sorteo


class ResultadoForm(forms.ModelForm):
    """
    Formulario para crear/editar un resultado de sorteo.
    Los campos derivados (PF, Fijo, Corridos, Centenas, Parlet, etc.)
    se muestran como readonly o editables según el tipo de sorteo.
    """

    # Campos principales (ingreso manual)
    pick2 = forms.CharField(
        max_length=2, required=False, label="Pick 2",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00'})
    )
    pick3 = forms.CharField(
        max_length=3, required=False, label="Pick 3",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '000'})
    )
    pick4 = forms.CharField(
        max_length=4, required=False, label="Pick 4",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0000'})
    )
    pick5 = forms.CharField(
        max_length=5, required=False, label="Pick 5",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000'})
    )

    # Campos derivados (automáticos o manuales según sorteo)
    pf = forms.CharField(
        max_length=2, required=False, label="PF (Par Frontal)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )
    fijo = forms.CharField(
        max_length=2, required=False, label="Fijo",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    corrido_1 = forms.CharField(
        max_length=2, required=False, label="Corrido 1",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    corrido_2 = forms.CharField(
        max_length=2, required=False, label="Corrido 2",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    centena_corrida_1 = forms.CharField(
        max_length=3, required=False, label="Centena Corrida 1",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )
    centena_corrida_2 = forms.CharField(
        max_length=3, required=False, label="Centena Corrida 2",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )

    parlet = forms.CharField(
        max_length=200, required=False, label="Parlet",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )
    posicion = forms.CharField(
        max_length=200, required=False, label="Posición",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )
    tripleta = forms.CharField(
        max_length=200, required=False, label="Tripleta",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )

    vspf = forms.CharField(
        max_length=200, required=False, label="VSPF",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )
    vspick2 = forms.CharField(
        max_length=200, required=False, label="VSPick2",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )
    pick2vspf = forms.CharField(
        max_length=200, required=False, label="Pick2 vsPF",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )
    superparlet = forms.CharField(
        max_length=500, required=False, label="Superparlet",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )

    class Meta:
        model = Resultado
        fields = ['sorteo', 'fecha', 'hora']
        widgets = {
            'sorteo': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Permite pasar un objeto 'sorteo' al formulario para ajustar los campos dinámicamente
        sorteo = kwargs.pop('sorteo', None)
        super().__init__(*args, **kwargs)

        # Filtramos el queryset del campo 'sorteo' para mostrar solo sorteos activos
        self.fields['sorteo'].queryset = Sorteo.objects.filter(activo=True)

        # Si se proporciona un sorteo, ajustamos los campos según su configuración
        if sorteo:
            self._ajustar_campos_segun_sorteo(sorteo)

    def _ajustar_campos_segun_sorteo(self, sorteo):
        """
        Ajusta el atributo 'readonly' de los campos según el tipo de sorteo.

        - Si el sorteo tiene Pick3 → Fijo y PF son readonly (se derivan automáticamente).
        - Si el sorteo tiene Pick4 → Corrido1 y Corrido2 son readonly (se derivan automáticamente).
        - Si el sorteo NO tiene Pick3 → Fijo es editable (manual).
        - Si el sorteo NO tiene Pick4 → Corrido1 y Corrido2 son editables (manuales).
        - Los campos como Centenas, Parlet, Posición, etc., siempre son readonly.
        """
        # Campos que SIEMPRE son readonly (automáticos)
        readonly_auto = [
            'pf', 'centena_corrida_1', 'centena_corrida_2',
            'parlet', 'posicion', 'tripleta', 'vspf', 'vspick2',
            'pick2vspf', 'superparlet'
        ]

        for campo in readonly_auto:
            if campo in self.fields:
                self.fields[campo].widget.attrs['readonly'] = True

        # Fijo: readonly si tiene Pick3, editable en caso contrario
        if sorteo.tiene_pick3:
            self.fields['fijo'].widget.attrs['readonly'] = True
        else:
            self.fields['fijo'].widget.attrs.pop('readonly', None)  # Elimina readonly

        # Corridos: readonly si tiene Pick4, editable en caso contrario
        if sorteo.tiene_pick4:
            self.fields['corrido_1'].widget.attrs['readonly'] = True
            self.fields['corrido_2'].widget.attrs['readonly'] = True
        else:
            self.fields['corrido_1'].widget.attrs.pop('readonly', None)
            self.fields['corrido_2'].widget.attrs.pop('readonly', None)

        # PF siempre readonly (se deriva de Pick3 o de Fijo manual)
        # (Ya está marcado como readonly en la definición del campo)

    def clean(self):
        """
        Validaciones adicionales:
        - Verifica que los campos principales (Pick2, Pick3, Pick4, Pick5)
          tengan exactamente la cantidad de dígitos esperada.
        """
        cleaned_data = super().clean()
        sorteo = cleaned_data.get('sorteo')
        if not sorteo:
            return cleaned_data

        # Validar campos según las propiedades del sorteo
        if sorteo.tiene_pick2:
            pick2 = cleaned_data.get('pick2', '').strip()
            if pick2 and (not pick2.isdigit() or len(pick2) != 2):
                self.add_error('pick2', 'Pick 2 debe tener exactamente 2 dígitos numéricos.')

        if sorteo.tiene_pick3:
            pick3 = cleaned_data.get('pick3', '').strip()
            if pick3 and (not pick3.isdigit() or len(pick3) != 3):
                self.add_error('pick3', 'Pick 3 debe tener exactamente 3 dígitos numéricos.')

        if sorteo.tiene_pick4:
            pick4 = cleaned_data.get('pick4', '').strip()
            if pick4 and (not pick4.isdigit() or len(pick4) != 4):
                self.add_error('pick4', 'Pick 4 debe tener exactamente 4 dígitos numéricos.')

        if sorteo.tiene_pick5:
            pick5 = cleaned_data.get('pick5', '').strip()
            if pick5 and (not pick5.isdigit() or len(pick5) != 5):
                self.add_error('pick5', 'Pick 5 debe tener exactamente 5 dígitos numéricos.')

        return cleaned_data