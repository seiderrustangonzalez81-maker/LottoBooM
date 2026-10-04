# -*- coding: utf-8 -*-
"""
6 tareas:
1. Ventas desplegable por sorteo
2. Premios desplegable por sorteo
3. Eliminar botón Aplicar
4. Filtros dinámicos (selects + date)
5. Filtros por rol en cuadre (comercial ve fecha)
6. Verificar banco→comercial escribe envío/recibo
"""
import re, shutil, datetime, sys
from pathlib import Path

TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
RAIZ = Path('/home/LottoBooM')

def backup(p):
    b = p.with_suffix(p.suffix + '.bak_fix_' + TS)
    shutil.copy2(p, b)
    print(f'  Backup: {b.name}')

# ═══════════════════════════════════════════════════════════
# SCRIPT 1 — Backend services.py
# ═══════════════════════════════════════════════════════════
print()
print('=' * 70)
print('1. services.py — desglose ventas/premios por sorteo')
print('=' * 70)

SERV = RAIZ / 'roles' / 'services.py'
s = SERV.read_text(encoding='utf-8')
orig = s

viejo_matriz = '''        filas = []
        for s_id, s in sorteos.items():
            montos = {
                fp_id: filas_dict[s_id].get(fp_id, Decimal('0.00'))
                for fp_id in formas_pago
            }
            filas.append({
                'sorteo': s,
                'montos': montos,
                'total': sum(montos.values(), Decimal('0.00')),
            })

        return {
            'sorteos': list(sorteos.values()),
            'formas_pago': list(formas_pago.values()),
            'filas': filas,
            'totales_por_fp': dict(totales_por_fp),
            'totales_por_sorteo': dict(totales_por_sorteo),
            'gran_total': gran_total,
        }'''

nuevo_matriz = '''        filas = []
        for s_id, s in sorteos.items():
            montos = {
                fp_id: filas_dict[s_id].get(fp_id, Decimal('0.00'))
                for fp_id in formas_pago
            }
            filas.append({
                'sorteo': s,
                'montos': montos,
                'total': sum(montos.values(), Decimal('0.00')),
            })

        # FIX_CUADRE_DESGLOSE: agrupar ventas y premios por (FP, sorteo)
        ventas_por_fp_sorteo = defaultdict(lambda: defaultdict(Decimal))
        premios_por_fp_sorteo = defaultdict(lambda: defaultdict(Decimal))
        for j in jugadas:
            if j.forma_pago_id:
                if j.monto:
                    ventas_por_fp_sorteo[j.forma_pago_id][j.sorteo_id] += j.monto
                if j.estado == 'ganadora' and j.monto_premio:
                    premios_por_fp_sorteo[j.forma_pago_id][j.sorteo_id] += j.monto_premio

        ventas_por_sorteo = {}
        for fp_id, sort_dict in ventas_por_fp_sorteo.items():
            ventas_por_sorteo[fp_id] = [
                {'sorteo': sorteos.get(sid), 'monto': m}
                for sid, m in sorted(sort_dict.items(), key=lambda x: -x[1])
            ]

        premios_por_sorteo = {}
        for fp_id, sort_dict in premios_por_fp_sorteo.items():
            premios_por_sorteo[fp_id] = [
                {'sorteo': sorteos.get(sid), 'monto': m}
                for sid, m in sorted(sort_dict.items(), key=lambda x: -x[1])
                if m > 0
            ]

        return {
            'sorteos': list(sorteos.values()),
            'formas_pago': list(formas_pago.values()),
            'filas': filas,
            'totales_por_fp': dict(totales_por_fp),
            'totales_por_sorteo': dict(totales_por_sorteo),
            'gran_total': gran_total,
            'ventas_por_sorteo': ventas_por_sorteo,
            'premios_por_sorteo': premios_por_sorteo,
        }'''

if 'FIX_CUADRE_DESGLOSE' in s:
    print('  -- matriz ya parcheada')
elif viejo_matriz in s:
    s = s.replace(viejo_matriz, nuevo_matriz, 1)
    print('  ✅ _construir_matriz: desglose por sorteo')
else:
    print('  ❌ bloque matriz no encontrado')

# Añadir al control
viejo_control = '''        control = {
            'fondo_inicial': {},
            'limpio': {},
            'enviado_banco': {},
            'recibido_banco': {},
            'ajuste': {},
            'fondo_final': {},
            'fondo_actual': {},   # alias legacy
            'ventas': {},
            'premios': {},
            'comision': {},
            'deuda_total': cuadre.deuda_total or Decimal('0.00'),
            'pagado': cuadre.pagado or Decimal('0.00'),
            'cerrado': cuadre.cerrado,
        }'''

nuevo_control = '''        control = {
            'fondo_inicial': {},
            'limpio': {},
            'enviado_banco': {},
            'recibido_banco': {},
            'ajuste': {},
            'fondo_final': {},
            'fondo_actual': {},   # alias legacy
            'ventas': {},
            'premios': {},
            'comision': {},
            'deuda_total': cuadre.deuda_total or Decimal('0.00'),
            'pagado': cuadre.pagado or Decimal('0.00'),
            'cerrado': cuadre.cerrado,
            'ventas_por_sorteo': {},   # FIX_CUADRE_DESGLOSE
            'premios_por_sorteo': {},  # FIX_CUADRE_DESGLOSE
        }'''

if 'ventas_por_sorteo' in s and 'FIX_CUADRE_DESGLOSE' in s:
    print('  -- control ya parcheado')
elif viejo_control in s:
    s = s.replace(viejo_control, nuevo_control, 1)
    print('  ✅ control: claves ventas_por_sorteo/premios_por_sorteo')
else:
    print('  ❌ bloque control no encontrado')

# Añadir en el loop de formas de pago
viejo_loop = """            control['ventas'][nombre] = ventas_fp
            control['premios'][nombre] = premios_fp
            control['comision'][nombre] = comision_fp
            control['limpio'][nombre] = limpio
            control['fondo_final'][nombre] = fondo_final
            control['fondo_actual'][nombre] = fondo_final  # alias legacy"""

nuevo_loop = """            control['ventas'][nombre] = ventas_fp
            control['premios'][nombre] = premios_fp
            control['comision'][nombre] = comision_fp
            control['limpio'][nombre] = limpio
            control['fondo_final'][nombre] = fondo_final
            control['fondo_actual'][nombre] = fondo_final  # alias legacy
            # FIX_CUADRE_DESGLOSE: desglose por sorteo
            control['ventas_por_sorteo'][fp.id] = matriz.get('ventas_por_sorteo', {}).get(fp.id, [])
            control['premios_por_sorteo'][fp.id] = matriz.get('premios_por_sorteo', {}).get(fp.id, [])"""

if viejo_loop in s:
    s = s.replace(viejo_loop, nuevo_loop, 1)
    print('  ✅ loop: control con desglose por sorteo')
else:
    print('  ❌ loop de formas de pago no encontrado')

if s != orig:
    backup(SERV)
    SERV.write_text(s, encoding='utf-8')
    print('  ✅ services.py guardado')

print()
print('PASO 1 COMPLETO')
print()
print('⚠️  Ahora los scripts 2-6 requieren verificación manual de sintaxis.')
print('   Copia los próximos bloques por separado.')
