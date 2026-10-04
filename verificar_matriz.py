from django.contrib.auth import get_user_model
from jugadas.models import FormaJuego
from sorteos.models import Sorteo
from roles.utils import get_matriz_limites_dosis

User = get_user_model()
suleiman = User.objects.get(username="Suleiman")

r = get_matriz_limites_dosis(suleiman)
print(f"Filas: {len(r['filas'])}  FPs: {len(list(r['formas_pago']))}")

# Ver Texas 7 PM
for fila in r['filas']:
    if 'texas 7' in fila['sorteo'].nombre.lower():
        print(f"\nSorteo: {fila['sorteo'].nombre}")
        for combo in fila['combos']:
            fj = combo['forma_juego']
            vals_lim = list(combo['limites'].values())[:1]
            vals_sob = list(combo['sobrelimites'].values())[:1]
            vals_dos = list(combo['dosis'].values())[:1]
            print(f"  {fj.nombre:<20} lim={vals_lim[0]:>10.2f}  sob={vals_sob[0]:>10.2f}  dosis={vals_dos[0]:>8.2f}")
        break
