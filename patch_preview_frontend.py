from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if 'id="modalPreview"' in src:
    print("SKIP: modal ya existe")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# 1) Añadir modalPreview al HTML (antes del bloque extra_js)
# ═══════════════════════════════════════════════════════════════
modal_html = '''
{# ═══════ MODAL PREVIEW (opción 1) ═══════ #}
<div class="modal fade" id="modalPreview" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-lg">
    <div class="modal-content" style="border-radius:16px;border:2px solid #10B981;">
      <div class="modal-header" style="background:linear-gradient(135deg,#065F46,#047857);color:#fff;border-bottom:2px solid #052e16;">
        <h5 class="modal-title fw-bold" style="text-shadow:0 1px 2px rgba(0,0,0,.4);">
          <i class="fas fa-clipboard-check me-2" style="color:#fde047;"></i>
          Confirmar apuesta — Verificación final
        </h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body" style="max-height:60vh;overflow-y:auto;">
        <div id="previewAdvertencias"></div>
        <div id="previewJugadasLista" style="background:#f0fdf4;border:1.5px solid #86efac;border-radius:10px;padding:12px 14px;margin-bottom:12px;"></div>
        <div id="previewResumen" style="background:linear-gradient(135deg,#d1fae5,#a7f3d0);border:2px solid #10B981;border-radius:10px;padding:12px 14px;text-align:center;font-weight:900;color:#065F46;font-size:1.1rem;"></div>
      </div>
      <div class="modal-footer" style="border-top:1px solid #c8ead4;">
        <button type="button" class="btn btn-secondary fw-bold" data-bs-dismiss="modal" style="border-radius:10px;">
          <i class="fas fa-arrow-left"></i> Volver a editar
        </button>
        <button type="button" class="btn fw-bold" id="btnPreviewConfirmar" style="background:linear-gradient(135deg,#10B981,#047857);color:#fff;border-radius:10px;">
          <i class="fas fa-check-double"></i> Confirmar y guardar
        </button>
      </div>
    </div>
  </div>
</div>
'''

# Insertar antes de "{% block extra_js %}" o "{% endblock %}"
if "{% block extra_js %}" in src:
    src = src.replace("{% block extra_js %}", modal_html + "\n{% block extra_js %}", 1)
elif "{% endblock %}" in src:
    idx = src.rfind("{% endblock %}")
    src = src[:idx] + modal_html + src[idx:]
else:
    print("ERROR: no encontre donde insertar el modal")
    raise SystemExit(1)
print("OK: modalPreview agregado al HTML")

# ═══════════════════════════════════════════════════════════════
# 2) Modificar enviarApuesta() para que soporte modo preview
# ═══════════════════════════════════════════════════════════════
viejo_enviar = "function enviarApuesta(){"

nuevo_enviar = '''function enviarApuesta(dryRun){
  if (typeof dryRun === 'undefined') dryRun = false;
'''
if viejo_enviar not in src:
    print("ERROR: no encontre function enviarApuesta(){")
    raise SystemExit(1)
src = src.replace(viejo_enviar, nuevo_enviar, 1)
print("OK: enviarApuesta ahora acepta dryRun")

# ═══════════════════════════════════════════════════════════════
# 3) Añadir dry_run al FormData dentro de enviarApuesta
# ═══════════════════════════════════════════════════════════════
viejo_fd = "  fd.append('csrfmiddlewaretoken', CSRF);"
nuevo_fd = """  fd.append('csrfmiddlewaretoken', CSRF);
  if (dryRun) fd.append('dry_run', 'true');"""
if viejo_fd not in src:
    print("ERROR: no encontre fd.append('csrfmiddlewaretoken', CSRF);")
    raise SystemExit(1)
src = src.replace(viejo_fd, nuevo_fd, 1)
print("OK: dry_run agregado al FormData")

# ═══════════════════════════════════════════════════════════════
# 4) Modificar el .then() de fetch para manejar preview
# ═══════════════════════════════════════════════════════════════
viejo_then = """  .then(d=>{
    if (d.success){
      if (d.advertencias && d.advertencias.length){
        d.advertencias.slice(0,4).forEach(w => toast('⚠️ ' + w, 'warning'));
      }
      toast('✅ ' + d.message, 'success');
      setTimeout(()=>{ window.location.href = "{% url 'jugadas:mis_apuestas' %}"; }, 1400);
    } else {"""

nuevo_then = """  .then(d=>{
    if (d.success){
      // MODO PREVIEW: mostrar modal 2
      if (dryRun && d.preview){
        mostrarPreviewApuesta(d);
        // Restaurar botón
        const b = document.getElementById('btnGo');
        if (b) { b.disabled = false; b.innerHTML = '<i class="fas fa-check-circle"></i> Confirmar apuesta'; }
        return;
      }
      // MODO REAL: guardar y redirigir
      if (d.advertencias && d.advertencias.length){
        d.advertencias.slice(0,4).forEach(w => toast('⚠️ ' + w, 'warning'));
      }
      toast('✅ ' + d.message, 'success');
      setTimeout(()=>{ window.location.href = "{% url 'jugadas:mis_apuestas' %}"; }, 1400);
    } else {"""

if viejo_then not in src:
    print("ERROR: no encontre el then(d=>{ if (d.success){")
    print("Corre: grep -n \"if (d.success){\" jugadas/templates/jugadas/apostar.html | head -3")
    raise SystemExit(1)
src = src.replace(viejo_then, nuevo_then, 1)
print("OK: then() maneja preview")

# ═══════════════════════════════════════════════════════════════
# 5) Añadir funcion mostrarPreviewApuesta + hook al btnPreviewConfirmar
# ═══════════════════════════════════════════════════════════════
func_preview = '''
function mostrarPreviewApuesta(data){
  var adv = data.advertencias || [];
  var p = data.preview || {};
  var jugadas = p.jugadas || [];
  var total = p.total || 0;
  var descartadas = p.descartadas || 0;

  // Advertencias
  var advCont = document.getElementById('previewAdvertencias');
  if (advCont) {
    if (adv.length) {
      var advHtml = '<div style="background:linear-gradient(145deg,#fef3c7,#fde68a);border:1.5px solid #f59e0b;color:#78350f;padding:10px 14px;border-radius:10px;margin-bottom:12px;font-weight:700;font-size:.82rem;"><div style="margin-bottom:6px;">⚠️ Advertencias (' + adv.length + '):</div><ul style="margin:0;padding-left:20px;">';
      adv.slice(0,8).forEach(function(w){ advHtml += '<li>' + w + '</li>'; });
      advHtml += '</ul></div>';
      advCont.innerHTML = advHtml;
    } else {
      advCont.innerHTML = '';
    }
  }

  // Lista de jugadas
  var listaCont = document.getElementById('previewJugadasLista');
  if (listaCont) {
    var html = '<div style="font-weight:800;color:#065F46;font-size:.78rem;text-transform:uppercase;letter-spacing:.4px;margin-bottom:8px;">📋 Se guardarán ' + jugadas.length + ' jugadas</div>';
    html += '<table style="width:100%;font-size:.75rem;border-collapse:collapse;">';
    html += '<thead><tr style="border-bottom:1.5px solid #86efac;"><th style="text-align:left;padding:4px;">Sorteo</th><th style="text-align:left;padding:4px;">Forma</th><th style="text-align:left;padding:4px;">Número</th><th style="text-align:right;padding:4px;">Monto</th></tr></thead><tbody>';
    jugadas.forEach(function(j){
      html += '<tr><td style="padding:3px 4px;">' + (j.sorteo || '—') + '</td><td style="padding:3px 4px;">' + (j.forma_juego || '—') + '</td><td style="padding:3px 4px;font-family:monospace;">' + (j.numero || '—') + '</td><td style="padding:3px 4px;text-align:right;font-weight:800;color:#065F46;">$' + (j.monto || 0).toFixed(2) + '</td></tr>';
    });
    html += '</tbody></table>';
    if (descartadas > 0) {
      html += '<div style="margin-top:8px;background:#fee2e2;color:#7f1d1d;border-radius:6px;padding:6px 10px;font-weight:700;font-size:.72rem;">⚠️ ' + descartadas + ' jugada(s) descartada(s) por pool agotado, sorteo cerrado o forma no permitida.</div>';
    }
    listaCont.innerHTML = html;
  }

  // Resumen
  var resumenCont = document.getElementById('previewResumen');
  if (resumenCont) {
    resumenCont.innerHTML = '<div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.5px;">💵 Total a descontar</div><div style="font-size:1.8rem;margin-top:4px;">$' + total.toFixed(2) + '</div>';
  }

  // Mostrar modal
  new bootstrap.Modal(document.getElementById('modalPreview')).show();
}

document.addEventListener('DOMContentLoaded', function(){
  var btnPreview = document.getElementById('btnPreviewConfirmar');
  if (btnPreview && !btnPreview.dataset.bound) {
    btnPreview.dataset.bound = '1';
    btnPreview.addEventListener('click', function(){
      bootstrap.Modal.getInstance(document.getElementById('modalPreview')).hide();
      var b = document.getElementById('btnGo');
      if (b) { b.disabled = true; b.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...'; }
      enviarApuesta(false);  // Guardar de verdad
    });
  }
});

'''

# Insertar antes de la última llave de cierre del script
# Buscar "console.log('[apostar] Funciones expuestas"
ancla_js = "window.autoformatear = autoformatear;"
if ancla_js not in src:
    print("ERROR: no encontre el ancla de funciones expuestas")
    raise SystemExit(1)
src = src.replace(ancla_js, func_preview + "\n" + ancla_js, 1)
print("OK: funcion mostrarPreviewApuesta + hook agregados")

# ═══════════════════════════════════════════════════════════════
# 6) Modificar btnPwdOk para llamar preview primero
# ═══════════════════════════════════════════════════════════════
viejo_pwd = """    bootstrap.Modal.getInstance($('modalPwd')).hide();
    enviarApuesta();"""

nuevo_pwd = """    bootstrap.Modal.getInstance($('modalPwd')).hide();
    // Primero llamamos en modo preview
    const b = document.getElementById('btnGo');
    if (b) { b.disabled = true; b.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Verificando...'; }
    enviarApuesta(true);  // dry_run=true"""

if viejo_pwd not in src:
    print("WARN: no encontre el patron de btnPwdOk → enviarApuesta()")
    print("     Quizas el flujo de contraseña es distinto, revisar a mano")
else:
    src = src.replace(viejo_pwd, nuevo_pwd, 1)
    print("OK: btnPwdOk ahora usa preview")

p.write_text(src, encoding="utf-8")
print("OK: template actualizado")
