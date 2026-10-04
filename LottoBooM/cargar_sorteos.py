import os
import sys
import json
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LottoBooM.settings')
django.setup()

from sorteos.models import Sorteo

def cargar_sorteos():
    # Ruta al archivo JSON (ajusta si es necesario)
    ruta_json = 'sorteos/fixtures/sorteos.json'

    with open(ruta_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for item in data:
        fields = item['fields']
        nombre = fields['nombre']
        activo = fields['activo']
        horarios = fields['horarios']

        # Usar update_or_create para evitar duplicados
        sorteo, creado = Sorteo.objects.update_or_create(
            nombre=nombre,
            defaults={
                'activo': activo,
                'horarios': horarios,
            }
        )
        if creado:
            print(f"✅ Creado: {nombre}")
        else:
            print(f"🔄 Actualizado: {nombre}")

    print(f"🎉 Total de sorteos en BD: {Sorteo.objects.count()}")

if __name__ == '__main__':
    cargar_sorteos()