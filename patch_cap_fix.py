from pathlib import Path
import ast, re

# ═══════════════════════════════════════════════════════════════
# 1. Backend: api_limites_gestor acepta forma_pago_id + devuelve consumido
# ═══════════════════════════════════════════════════════════════
p1 = Path("/home/LottoBooM/roles/views.py")
src1 = p1.read_text(encoding="utf-8")

viejo = '''    gestor_id = (request.GET.get('gestor_id') or '').strip()
    sorteo_id = (request.GET.get('sorteo_id') or '').strip()

    if not gestor_id.isdigit() or not sorteo_id.isdigit():
        return JsonResponse({'success': False, 'error': 'Faltan parametros'}, status=400)

    try:
        gestor = User.objects.get(id=int(gestor_id))
        sorteo = Sorteo.objects.get(id=int(sorteo_id))
    except (User.DoesNotExist, Sorteo.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'No encontrado'}, status=404)'''

nuevo = '''    gestor_id = (request.GET.get('gestor_id') or '').strip()
    sorteo_id = (request.GET.get('sorteo_id') or '').strip()
    forma_pago_id = (request.GET.get('forma_pago_id') or '').strip()
    fecha_str = (request.GET.get('fecha') or '').strip()

    if not gestor_id.isdigit() or not sorteo_id.isdigit():
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

    from datetime import datetime as _dt
    fecha = None
    if fecha_str:
        try:
            fecha = _dt.strptime(fecha_str, '%Y-%m-%d').date()
        except Exception:
            fecha = None
    if not fecha:
        from django.utils import timezone as _tz
        fecha = _tz.localdate()'''

if "forma_pago = None" in src1 and "gestor_id = (request.GET.get('gestor_id')" in src1 and src1.count("forma_pago_id = (request.GET.get('forma_pago_id')") >= 1:
    print("1a: SKIP (backend ya tiene forma_pago_id)")
else:
    if viejo in src1:
        src1 = src1.replace(viejo, nuevo, 1)
        p1.write_text(src1, encoding="utf-8")
        print("1a: OK (backend acepta forma_pago_id)")
    else:
        print("1a: WARN (no matcheo el bloque)")
        # Verificar si ya tiene forma_pago_id
        if "forma_pago_id = (request.GET.get('forma_pago_id')" in src1:
            print("1a: ya tenia forma_pago_id")

# Cambiar las llamadas a get_pool_gestor para usar forma_pago
viejo2 = """        try:
            fila['limite'] = float(get_pool_gestor(gestor, sorteo, fj, None) or 0)
        except Exception:
            pass"""

nuevo2 = """        try:
            fila['limite'] = float(get_pool_gestor(gestor, sorteo, fj, forma_pago) or 0)
        except Exception:
            pass
        # Consumido del gestor para esa forma en (sorteo, fecha, FP)
        try:
            from jugadas.models import Jugada as _J
            from django.db.models import Sum as _Sum
            _q = _J.objects.filter(
                destinatario=gestor, sorteo=sorteo, forma_juego=fj,
                fecha_sorteo=fecha, estado__in=['confirmada', 'pendiente'],
            )
            if forma_pago:
                _q = _q.filter(forma_pago=forma_pago)
            fila['consumido'] = float(_q.aggregate(t=_Sum('monto'))['t'] or 0)
        except Exception:
            fila['consumido'] = 0.0
        fila['disponible'] = max(0.0, fila['limite'] - fila['consumido'])"""

if "fila['consumido']" in src1:
    print("1b: SKIP (consumido ya calculado)")
elif viejo2 in src1:
    src1 = src1.replace(viejo2, nuevo2, 1)
    p1.write_text(src1, encoding="utf-8")
    print("1b: OK (consumido + disponible agregados)")
else:
    print("1b: WARN (no matcheo el bloque de fila['limite'])")

try:
    ast.parse(src1)
    print("OK: sintaxis views.py")
except SyntaxError as e:
    print("ERROR views:", e)
    raise SystemExit(1)


# ═══════════════════════════════════════════════════════════════
# 2. Frontend: fetch con FP + usar disponible + no forzar parlet
# ═══════════════════════════════════════════════════════════════
p2 = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src2 = p2.read_text(encoding="utf-8")

# 2a: fetch con forma_pago_id + fecha
viejo3 = """        fetch("{% url 'roles:api_limites_gestor' %}?gestor_id=" + gestorId + "&sorteo_id=" + sid, {"""
nuevo3 = """        var hoy = new Date().toISOString().slice(0,10);
        fetch("{% url 'roles:api_limites_gestor' %}?gestor_id=" + gestorId + "&sorteo_id=" + sid + "&forma_pago_id=" + (fpSel || '') + "&fecha=" + hoy, {"""

if "&forma_pago_id=\" + (fpSel" in src2:
    print("2a: SKIP (fetch ya con FP)")
elif viejo3 in src2:
    src2 = src2.replace(viejo3, nuevo3, 1)
    print("2a: OK (fetch con forma_pago_id)")
else:
    print("2a: WARN (no matcheo fetch)")

# 2b: guardar disponible (no limite)
viejo4 = """                (d.formas || []).forEach(function(f){
                    var k = String(f.forma || '').toLowerCase().trim();
                    // El backend ya devuelve 'limite' = pool (limite + sobrelimite aplicados)
                    pools[k] = parseFloat(f.limite || 0);
                });"""

nuevo4 = """                (d.formas || []).forEach(function(f){
                    var k = String(f.forma || '').toLowerCase().trim();
                    // Usar 'disponible' = pool - consumido. Fallback a 'limite'.
                    var disp = parseFloat(f.disponible);
                    if (isNaN(disp)) disp = parseFloat(f.limite || 0);
                    pools[k] = disp;
                });"""

if "f.disponible" in src2:
    print("2b: SKIP (usa disponible)")
elif viejo4 in src2:
    src2 = src2.replace(viejo4, nuevo4, 1)
    print("2b: OK (usa disponible)")
else:
    print("2b: WARN (no matcheo lectura de formas)")

# 2c: NO auto-forzar parlet al escribir candado (mantener candado, no tocar parlet)
viejo5 = """          } else { // candado
            row.montos['candado'] = this.value;
            if (inpParlet){
              // TRUNCAR (no redondear) para que percap * nPlays <= candado
              const percap = Math.floor((val / nPlays) * 100) / 100;
              row.montos['parlet'] = percap.toFixed(2);
              inpParlet.value = percap.toFixed(2);
              // El candado REAL cobrado = percap * nPlays (puede ser < val)
              const candadoReal = (percap * nPlays).toFixed(2);
              row.montos['candado'] = candadoReal;
              if (inpCand) inpCand.value = candadoReal;
              inpParlet.readOnly = true;
              inpParlet.classList.add('monto-blocked');
            }
          }"""

nuevo5 = """          } else { // candado
            row.montos['candado'] = this.value;
            // CAP_CANDADO_V2: solo capar si excede pool*nPlays, no tocar parlet
            // (el usuario ve el candado tal cual lo escribió)
          }"""

if "CAP_CANDADO_V2" in src2:
    print("2c: SKIP (cap candado ya aplicado)")
elif viejo5 in src2:
    src2 = src2.replace(viejo5, nuevo5, 1)
    print("2c: OK (no forzar parlet desde candado)")
else:
    print("2c: WARN (no matcheo bloque candado)")

p2.write_text(src2, encoding="utf-8")
print("OK: template actualizado")

print("")
print("--- VERIFICACION ---")
print("consumido en views:", src1.count("fila['consumido']"))
print("disponible en template:", src2.count("f.disponible"))
print("CAP_CANDADO_V2:", src2.count("CAP_CANDADO_V2"))
