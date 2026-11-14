import os
import re
import shutil
import py_compile

print("🚀 INICIANDO CONFIGURACIÓN PARA GEORGIA (ID 54)...\n")

views_path = 'jugadas/views.py'
if os.path.exists(views_path):
    shutil.copy(views_path, views_path + '.bak')
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content

    # --- A. FORZAR FECHA EN EL POST ---
    patron_post = re.compile(r'(def apostar\(request\).*?if request\.method\s*==\s*[\'"]POST[\'"]:\n)', re.DOTALL)
    
    def inyectar_fecha(match):
        return match.group(1) + """        # FIX_GEORGIA_54: Forzar fecha a mañana para el sorteo 54
        from datetime import timedelta
        from django.utils import timezone
        _sorteo_id = request.POST.get('sorteo') or request.POST.get('sorteo_id')
        if str(_sorteo_id) == '54':
            request.POST = request.POST.copy()
            request.POST['fecha_sorteo'] = (timezone.localdate() + timedelta(days=1)).strftime('%Y-%m-%d')
            request.POST['fecha'] = request.POST['fecha_sorteo']
"""

    if patron_post.search(content) and "FIX_GEORGIA_54" not in content:
        content = patron_post.sub(inyectar_fecha, content)
        print("   ✅ Lógica de fecha forzada inyectada en el POST (views.py)")

    # --- B. REDIRECCIÓN INTELIGENTE ---
    patron_redirect = re.compile(r'( *)return redirect\([\'"]jugadas:mis_apuestas[\'"]\)')
    
    def inyectar_redirect(match):
        indentacion = match.group(1)
        return f"""{indentacion}# FIX_REDIRECT_GEORGIA: Redirigir a la fecha de la última jugada
{indentacion}from jugadas.models import Jugada as _Jugada
{indentacion}_ult_jug = _Jugada.objects.filter(usuario=request.user).order_by('-id').first()
{indentacion}if _ult_jug:
{indentacion}    _f_str = _ult_jug.fecha_sorteo.strftime('%Y-%m-%d')
{indentacion}    from django.urls import reverse
{indentacion}    return redirect(f"{{reverse('jugadas:mis_apuestas')}}?fecha_desde={{_f_str}}&fecha_hasta={{_f_str}}")
{indentacion}return redirect('jugadas:mis_apuestas')"""

    if patron_redirect.search(content) and "FIX_REDIRECT_GEORGIA" not in content:
        content = patron_redirect.sub(inyectar_redirect, content)
        print("   ✅ Redirección inteligente inyectada (views.py)")
    elif "FIX_REDIRECT_GEORGIA" in content:
        print("   ℹ️ La redirección ya estaba configurada previamente.")

    if content != original:
        with open(views_path, 'w', encoding='utf-8') as f:
            f.write(content)

else:
    print("   ❌ No se encontró jugadas/views.py")

# ==============================================================================
# 2. PARCHEAR EL FRONTEND (HTML/JS)
# ==============================================================================
html_path = None
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.git', 'venv', 'env', '__pycache__']): continue
    for file in files:
        if file == 'apostar.html':
            html_path = os.path.join(root, file)
            break
    if html_path: break

if html_path:
    shutil.copy(html_path, html_path + '.bak')
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    js_code = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    // FIX_GEORGIA_JS: Forzar fecha futura al seleccionar Georgia 12:34 AM
    const sorteoSelect = document.querySelector('select[name="sorteo"]') || document.getElementById('id_sorteo');
    const fechaInput = document.querySelector('input[name="fecha_sorteo"]') || document.querySelector('input[name="fecha"]') || document.getElementById('id_fecha_sorteo');
    
    if (sorteoSelect && fechaInput) {
        sorteoSelect.addEventListener('change', function() {
            if (this.value === '54') {
                let manana = new Date();
                manana.setDate(manana.getDate() + 1);
                let fechaFmt = manana.toISOString().split('T')[0];
                fechaInput.value = fechaFmt;
                if (fechaInput._flatpickr) {
                    fechaInput._flatpickr.setDate(fechaFmt);
                }
            }
        });
    }
});
</script>
"""
    if "FIX_GEORGIA_JS" not in html_content:
        if "{% endblock %}" in html_content:
            html_content = html_content.replace("{% endblock %}", js_code + "\n{% endblock %}", 1)
        else:
            html_content = html_content.replace("</body>", js_code + "\n</body>")
            
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"   ✅ JavaScript inyectado en: {html_path}")
    else:
        print("   ℹ️ El JavaScript ya estaba inyectado en el HTML.")
else:
    print("   ⚠️ No se encontró el archivo apostar.html para inyectar el JS.")

# ==============================================================================
# 3. VERIFICAR SINTAXIS
# ==============================================================================
print("\n3. Verificando sintaxis del backend...")
if os.path.exists(views_path):
    try:
        py_compile.compile(views_path, doraise=True)
        print(f"   ✅ Sintaxis OK: {views_path}")
    except py_compile.PyCompileError as e:
        print(f"   ❌ ERROR en {views_path}. Restaurando respaldo...")
        shutil.copy(views_path + '.bak', views_path)
        print(f"      Restaurado. Error: {e}")

print("\n🎉 ¡PROCESO TERMINADO! Por favor, ve a la pestaña Web y haz clic en 'Reload'.")
