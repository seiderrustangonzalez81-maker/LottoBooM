from pathlib import Path
import ast, re

p = Path("/home/LottoBooM/roles/views.py")
src = p.read_text(encoding="utf-8")

if "def api_pool_gestor" in src:
    print("SKIP: ya existe")
    raise SystemExit(0)

endpoint = '''

@login_required
def api_pool_gestor(request):
    """Devuelve pool por forma de juego para (gestor + sorteo + forma_pago)."""
    from roles.utils import get_pool_gestor
    from jugadas.models import FormaJuego

    gestor_id = (request.GET.get('gestor_id') or '').strip()
    sorteo_id = (request.GET.get('sorteo_id') or '').strip()
    forma_pago_id = (request.GET.get('forma_pago_id') or '').strip()

    if not (gestor_id.isdigit() and sorteo_id.isdigit()):
        return JsonResponse({'success': False, 'error': 'Faltan parametros'}, status=400)

    try:
        gestor = User.objects.get(id=int(gestor_id))
        sorteo = Sorteo.objects.get(id=int(sorteo_id))
    except (User.DoesNotExist, Sorteo.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'No encontrado'}, status=404)

    forma_pago = None
    if forma_pago_id.isdigit():
        try:
            forma_pago = FormaPago.objects.get(id=int(forma_pago_id))
        except FormaPago.DoesNotExist:
            pass

    pools = {}
    for fj in FormaJuego.objects.filter(activo=True):
        try:
            val = get_pool_gestor(gestor, sorteo, fj, forma_pago)
            pools[fj.nombre.lower()] = float(val or 0)
        except Exception:
            pools[fj.nombre.lower()] = 0

    return JsonResponse({'success': True, 'pools': pools})

'''

src += endpoint
p.write_text(src, encoding="utf-8")
print("OK: endpoint api_pool_gestor agregado")

try:
    ast.parse(src)
    print("OK: sintaxis")
except SyntaxError as e:
    print("ERROR:", e)
    raise SystemExit(1)

pu = Path("/home/LottoBooM/roles/urls.py")
srcurls = pu.read_text(encoding="utf-8")
if "api_pool_gestor" not in srcurls:
    m = re.search(r"urlpatterns\s*=\s*\[", srcurls)
    srcurls = srcurls[:m.end()] + "\n    path('api/pool-gestor/', views.api_pool_gestor, name='api_pool_gestor')," + srcurls[m.end():]
    pu.write_text(srcurls, encoding="utf-8")
    print("OK: URL agregada")
