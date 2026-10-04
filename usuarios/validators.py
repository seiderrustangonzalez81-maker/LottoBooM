import re
from django.core.exceptions import ValidationError

def validar_telefono_internacional(value):
    if not value:
        return value
    limpio = re.sub(r'[\s\-\(\)\.]', '', value)
    if not re.match(r'^\+\d+$', limpio):
        raise ValidationError("El número debe empezar con '+' seguido de dígitos.")
    if len(limpio) < 5:
        raise ValidationError("El número debe tener al menos 4 dígitos después del código de país.")
    if len(limpio) > 18:
        raise ValidationError("El número es demasiado largo.")
    return limpio