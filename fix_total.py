import os
import re
import shutil
import py_compile

print("🚀 INICIANDO REPARACIÓN QUIRÚRGICA...\n")

# La nueva función mejorada
nueva_funcion = """def jugada_es_ganadora(jugada, resultado):
    if not jugada.forma_juego:
        return False, 0
        
    forma = jugada.forma_juego.nombre.lower()
    num_jugado = str(jugada.numero).strip()
    
    fijo_g = str(resultado.fijo).strip() if resultado.fijo else None
    corr1_g = str(resultado.corrido_1).strip() if resultado.corrido_1 else None
    corr2_g = str(resultado.corrido_2).strip() if resultado.corrido_2 else None

    if 'fijo' in forma:
        if num_jugado == fijo_g:
            return True, 80
        return False, 0

    if 'corrido' in forma:
        if num_jugado in [corr1_g, corr2_g]:
            return True, 60
        if num_jugado == fijo_g:
            tiene_fijo = False
            if jugada.boleta:
                from jugadas.models import Jugada
                tiene_fijo = Jugada.objects.filter(
                    boleta=jugada.boleta, numero=num_jugado, forma_juego__nombre__icontains='fijo'
                ).exists()
            if tiene_fijo:
                return True, 60
            return False, 0

    return False, 0
"""

archivos_objetivo = ['resultados/views.py', 'resultados/utils.py', 'resultados/procesamiento.py', 'resultados/reconciliacion.py']
archivo_funcion_encontrada = False
archivo_pago_encontrado = False

for path in archivos_objetivo:
    if not os.path.exists(path):
        continue
        
    # Crear respaldo
    shutil.copy(path, path + '.bak')
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    original = content

    # 1. Reemplazar la función si existe aquí
    if 'def jugada_es_ganadora' in content:
        pattern = re.compile(r'^def jugada_es_ganadora\(.*?(?=^def |\Z)', re.MULTILINE | re.DOTALL)
        content = pattern.sub(nueva_funcion + '\n\n', content)
        archivo_funcion_encontrada = True
        print(f"   ✅ Función 'jugada_es_ganadora' reemplazada en: {path}")

    # 2. Parchear el bloque de pago (usando Regex para ignorar espacios)
    # Busca: if created or not premio.cobrado:
    patron_pago = re.compile(r'( *)if created or not premio\.cobrado:')
    
    def reemplazo_pago(match):
        indentacion = match.group(1)
        return f"""{indentacion}# BLINDAJE: Verificar si realmente el movimiento existe en la BD
{indentacion}from roles.models import MovimientoFondo
{indentacion}ya_tiene_movimiento = MovimientoFondo.objects.filter(
{indentacion}    receptor=jugada.usuario, 
{indentacion}    nota__icontains=f"jugada #{{jugada.id}}"
{indentacion}).exists()

{indentacion}if not premio.cobrado or not ya_tiene_movimiento:"""

    if patron_pago.search(content):
        content = patron_pago.sub(reemplazo_pago, content)
        archivo_pago_encontrado = True
        print(f"   ✅ Bucle de pago parcheado en: {path}")

    # Guardar solo si hubo cambios
    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

# Verificar sintaxis de los archivos modificados
print("\n3. Verificando sintaxis...")
for path in archivos_objetivo:
    if os.path.exists(path):
        try:
            py_compile.compile(path, doraise=True)
            print(f"   ✅ Sintaxis OK: {path}")
        except py_compile.PyCompileError as e:
            print(f"   ❌ ERROR en {path}. Restaurando respaldo...")
            shutil.copy(path + '.bak', path)
            print(f"      Restaurado. Error: {e}")

if not archivo_funcion_encontrada:
    print("\n⚠️ ADVERTENCIA: No se encontró la función 'jugada_es_ganadora' en los archivos escaneados.")
if not archivo_pago_encontrado:
    print("\n⚠️ ADVERTENCIA: No se encontró el bloque 'if created or not premio.cobrado:' para parchear.")

print("\n🎉 REPARACIÓN COMPLETA. Por favor, ve a la pestaña Web y haz clic en 'Reload'.")
