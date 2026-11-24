# Generated for the fixed ten-minute betting cutoff.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sorteos", "0004_sorteo_formas_juego"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sorteo",
            name="minutos_cierre",
            field=models.IntegerField(
                default=10,
                verbose_name="Minutos antes de la salida para cerrar apuestas",
            ),
        ),
    ]
