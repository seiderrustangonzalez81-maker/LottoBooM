# -*- coding: utf-8 -*-
"""Filtro de comerciales en cuadre: solo usuarios con rol comercial."""
import shutil, datetime, py_compile
from pathlib import Path

VIEWS = Path('/home/LottoBooM/roles/views.py')
TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

v = VIEWS.read_text(encoding='utf-8')
orig = v

# ═══════════════════════════════════════════════════════════
# Fix 1 — Vista BANCO
# ═══════════════════════════════════════════════════════════
viejo_banco = '''    if es_banco:
        comerciales_ids = Subordinacion.objects.filter(jefe=usuario_actual, activo=True).values_list('subordinado_id', flat=True)
        comerciales = User.objects.filter(id__in=comerciales_ids, is_active=True)
        comercial_id = request.GET.get("comercial_id")
        if comercial_id:
            comercial = get_object_or_404(User, pk=comercial_id, id__in=comerciales_ids)'''

nuevo_banco = '''    if es_banco:
        # FIX_COMERCIALES_FILTRO: solo subordinados con rol COMERCIAL
        comerciales_ids_all = Subordinacion.objects.filter(
            jefe=usuario_actual, activo=True
        ).values_list('subordinado_id', flat=True)
        comerciales_ids = Rol.objects.filter(
            usuario_id__in=comerciales_ids_all,
            tipo='comercial',
            activo=True,
        ).values_list('usuario_id', flat=True)
        comerciales = User.objects.filter(id__in=comerciales_ids, is_active=True)
        comercial_id = request.GET.get("comercial_id")
        if comercial_id:
            comercial = get_object_or_404(User, pk=comercial_id, id__in=comerciales_ids)'''

if 'FIX_COMERCIALES_FILTRO' in v and 'comerciales_ids_all' in v:
    print('-- vista banco ya parcheada')
elif viejo_banco in v:
    v = v.replace(viejo_banco, nuevo_banco, 1)
    print('OK: vista banco filtra por rol comercial')
else:
    print('!! bloque banco no encontrado')

# ═══════════════════════════════════════════════════════════
# Fix 2 — Vista SUPERADMIN (filtro por banco)
# ═══════════════════════════════════════════════════════════
viejo_super = '''                    context["banco_seleccionado"] = banco_obj
                    comerciales = User.objects.filter(
                        id__in=Subordinacion.objects.filter(
                            jefe_id=banco_obj.id, activo=True
                        ).values_list('subordinado_id', flat=True),
                        is_active=True,
                    ).order_by('username')'''

nuevo_super = '''                    context["banco_seleccionado"] = banco_obj
                    # FIX_COMERCIALES_FILTRO: solo comerciales del banco
                    _sub_ids = Subordinacion.objects.filter(
                        jefe_id=banco_obj.id, activo=True
                    ).values_list('subordinado_id', flat=True)
                    _com_ids = Rol.objects.filter(
                        usuario_id__in=_sub_ids,
                        tipo='comercial',
                        activo=True,
                    ).values_list('usuario_id', flat=True)
                    comerciales = User.objects.filter(
                        id__in=_com_ids, is_active=True
                    ).order_by('username')'''

if 'FIX_COMERCIALES_FILTRO: solo comerciales del banco' in v:
    print('-- vista superadmin (comercial_id) ya parcheada')
elif viejo_super in v:
    v = v.replace(viejo_super, nuevo_super, 1)
    print('OK: vista superadmin (comercial_id) filtra por rol comercial')
else:
    print('-- bloque superadmin (comercial_id) no encontrado')

# ═══════════════════════════════════════════════════════════
# Fix 3 — Vista SUPERADMIN (cuando selecciona banco)
# ═══════════════════════════════════════════════════════════
viejo_super_banco = '''            # Comerciales SOLO de ese banco
            comerciales = User.objects.filter(
                id__in=Subordinacion.objects.filter(
                    jefe_id=banco.id, activo=True
                ).values_list('subordinado_id', flat=True),
                is_active=True,
            ).order_by('username')'''

nuevo_super_banco = '''            # FIX_COMERCIALES_FILTRO: comerciales (rol) del banco
            _sub_ids_b = Subordinacion.objects.filter(
                jefe_id=banco.id, activo=True
            ).values_list('subordinado_id', flat=True)
            _com_ids_b = Rol.objects.filter(
                usuario_id__in=_sub_ids_b,
                tipo='comercial',
                activo=True,
            ).values_list('usuario_id', flat=True)
            comerciales = User.objects.filter(
                id__in=_com_ids_b, is_active=True
            ).order_by('username')'''

if 'FIX_COMERCIALES_FILTRO: comerciales (rol) del banco' in v:
    print('-- vista superadmin (banco seleccionado) ya parcheada')
elif viejo_super_banco in v:
    v = v.replace(viejo_super_banco, nuevo_super_banco, 1)
    print('OK: vista superadmin (banco) filtra por rol comercial')
else:
    print('-- bloque superadmin (banco) no encontrado')

# ═══════════════════════════════════════════════════════════
# Validar y guardar
# ═══════════════════════════════════════════════════════════
if v == orig:
    print('Sin cambios')
    raise SystemExit(0)

tmp = VIEWS.with_suffix('.py.chk')
tmp.write_text(v, encoding='utf-8')
try:
    py_compile.compile(str(tmp), doraise=True)
    print('OK: sintaxis Python')
finally:
    tmp.unlink(missing_ok=True)

bak = VIEWS.with_suffix(VIEWS.suffix + '.bak_comfilter_' + TS)
shutil.copy2(VIEWS, bak)
print(f'Backup: {bak.name}')
VIEWS.write_text(v, encoding='utf-8')
print('GUARDADO')
print()
print('FIX_COMERCIALES_FILTRO COMPLETO')
