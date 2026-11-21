# -*- coding: utf-8 -*-
import json
import re
from datetime import datetime
from django import forms
from .models import Sorteo


# ============================================================
# CHOICES DE FORMAS DE JUEGO
# (deben coincidir con las claves usadas en el JSONField `formas_juego`)
# ============================================================
FORMAS_JUEGO_CHOICES = [
    ('pick2', 'Pick 2'),
    ('pick3', 'Pick 3'),
    ('pick4', 'Pick 4'),
    ('pick5', 'Pick 5'),
    ('fijo', 'Fijo'),
    ('corrido1', 'Corrido 1'),
    ('corrido2', 'Corrido 2'),
    ('pf', 'PF'),
    ('vspf', 'VS PF'),
    ('vspick2', 'VS Pick2'),
    ('pick2vspf', 'Pick2 vs PF'),
    ('tripleta', 'Tripleta'),
    ('posicion', 'Posición'),
    ('centena corrida1', 'Centena Corrida 1'),
    ('centena corrida2', 'Centena Corrida 2'),
    ('superparlet', 'Superparlet'),
    ('parlet', 'Parlet'),
    ('par frontal', 'Par frontal'),
    ('vs', 'VS'),
]


class SorteoForm(forms.ModelForm):
    formas_juego = forms.MultipleChoiceField(
        choices=FORMAS_JUEGO_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Formas de juego admitidas'
    )

    class Meta:
        model = Sorteo
        fields = [
            'nombre',
            'activo',
            'origen',
            'horarios',
            'hora_salida',
            'minutos_cierre',
            'formas_juego',
        ]
        widgets = {
            'horarios': forms.Textarea(attrs={'rows': 6, 'class': 'form-control font-monospace'}),
            'hora_salida': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'origen': forms.Select(attrs={'class': 'form-select'}),
            'minutos_cierre': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'horarios': 'Formato JSON: {"invierno": {"lunes": "08:00", ...}, "verano": {...}}',
            'formas_juego': 'Marca las formas de juego que este sorteo admite.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si estamos editando un sorteo existente, precargar los valores actuales
        if self.instance and self.instance.pk:
            if self.instance.horarios:
                try:
                    self.initial['horarios'] = json.dumps(
                        self.instance.horarios, indent=2, ensure_ascii=False
                    )
                except Exception:
                    self.initial['horarios'] = '{}'
            self.initial['formas_juego'] = self.instance.formas_juego or []

    def clean_horarios(self):
        data = self.cleaned_data.get('horarios')
        if not data:
            return {}
        if isinstance(data, dict):
            return data
        try:
            horarios = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            raise forms.ValidationError('El formato JSON de horarios no es válido.')

        if not isinstance(horarios, dict):
            raise forms.ValidationError('Los horarios deben ser un objeto JSON por temporada.')

        dias_validos = {
            'lunes', 'martes', 'miercoles', 'miércoles', 'jueves',
            'viernes', 'sabado', 'sábado', 'domingo',
        }
        patron_hora = re.compile(r'^\\d{2}:\\d{2}
    def clean_formas_juego(self):
        return list(self.cleaned_data.get('formas_juego', [])))
        for temporada, dias in horarios.items():
            if not isinstance(temporada, str) or not temporada.strip():
                raise forms.ValidationError('Cada temporada debe tener un nombre válido.')
            if not isinstance(dias, dict):
                raise forms.ValidationError(f'La temporada "{temporada}" debe contener un objeto de días.')
            for dia, hora in dias.items():
                if str(dia).lower() not in dias_validos:
                    raise forms.ValidationError(f'Día no reconocido en "{temporada}": {dia}.')
                if hora in (None, ''):
                    continue
                if not isinstance(hora, str) or not patron_hora.fullmatch(hora):
                    raise forms.ValidationError(f'La hora de {dia} en "{temporada}" debe usar HH:MM o estar vacía.')
                try:
                    datetime.strptime(hora, '%H:%M')
                except ValueError:
                    raise forms.ValidationError(f'La hora de {dia} en "{temporada}" no es válida.')
        return horarios

    def clean_formas_juego(self):
        return list(self.cleaned_data.get('formas_juego', []))