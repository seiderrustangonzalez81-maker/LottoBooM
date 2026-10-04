from pathlib import Path
import ast, re

p = Path("/home/LottoBooM/roles/views.py")
src = p.read_text(encoding="utf-8")

if "def api_clientes_gestor" in src:
    print("SKIP: ya existe")
    raise SystemExit(0)

endpoint = '''

@login_required
def api_clientes_gestor(request):
    """Clientes con sus FPs y saldos para el retiro rapido."""
    user = request.user
    es_superadmin = user.is_superuser or user.roles.filter(tipo='superadmin', activo=True).exists()
    es_banco = user.roles.filter(tipo='banco', activo=True).exists()
    es_comercial = user.roles.filter(tipo='comercial', activo=True).exists()
    if not (es_superadmin or es_banco or es_comercial):
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)

    if es_superadmin:
        qs = Fondo.objects.filter(activo=True)
    elif es_banco:
        comerciales_ids = list(Subordinacion.objects.filter(jefe=user, activo=True).values_list('subordinado_id', flat=True))
        qs = Fondo.objects.filter(Q(asignado_por=user) | Q(asignado_por__in=comerciales_ids), activo=True)
    else:
        qs = Fondo.objects.filter(asignado_por=user, activo=True)

    cmap = {}
    for f in qs.select_related('usuario', 'forma_pago').order_by('usuario__username'):
        if not f.forma_pago:
            continue
        cid = f.usuario_id
        if cid not in cmap:
            cmap[cid] = {'id': cid, 'nombre': f.usuario.username, 'fps': []}
        cmap[cid]['fps'].append({
            'id': f.forma_pago_id,
            'nombre': f.forma_pago.nombre,
            'saldo': float(f.monto or 0),
        })

    return JsonResponse({'success': True, 'clientes': list(cmap.values())})

'''

src += endpoint
p.write_text(src, encoding="utf-8")
print("OK: endpoint agregado")

try:
    ast.parse(src)
    print("OK: sintaxis")
except SyntaxError as e:
    print("ERROR:", e)
    raise SystemExit(1)

pu = Path("/home/LottoBooM/roles/urls.py")
srcurls = pu.read_text(encoding="utf-8")
if "api_clientes_gestor" not in srcurls:
    m = re.search(r"urlpatterns\s*=\s*\[", srcurls)
    srcurls = srcurls[:m.end()] + "\n    path('api/clientes-gestor/', views.api_clientes_gestor, name='api_clientes_gestor')," + srcurls[m.end():]
    pu.write_text(srcurls, encoding="utf-8")
    print("OK: URL agregada")
