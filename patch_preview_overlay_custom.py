from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")
original = src

# ═══════════════════════════════════════════════════════════════
# PASO 1: Reemplazar mostrarPreviewApuesta por overlay custom
# ═══════════════════════════════════════════════════════════════
patron_func = re.compile(
    r"function mostrarPreviewApuesta\(data\)\{.*?\n\}",
    re.DOTALL,
)

nueva_func = '''function mostrarPreviewApuesta(data){
  // ═══ OVERLAY CUSTOM (sin Bootstrap) — evita bugs de backdrop ═══
  console.log('[preview] Mostrando overlay custom');

  // Eliminar overlay previo si existe
  var prev = document.getElementById('lottortPreviewOverlay');
  if (prev) prev.remove();

  var adv = data.advertencias || [];
  var p = data.preview || {};
  var jugadas = p.jugadas || [];
  var total = p.total || 0;
  var descartadas = p.descartadas || 0;

  // Advertencias HTML
  var advHtml = '';
  if (adv.length) {
    advHtml = '<div style="background:#fef3c7;border:1.5px solid #f59e0b;color:#78350f;padding:10px 14px;border-radius:10px;margin-bottom:12px;font-weight:700;font-size:.82rem;"><div style="margin-bottom:6px;">⚠️ Advertencias (' + adv.length + '):</div><ul style="margin:0;padding-left:20px;">';
    adv.slice(0,8).forEach(function(w){ advHtml += '<li>' + w + '</li>'; });
    advHtml += '</ul></div>';
  }

  // Lista de jugadas HTML
  var listaHtml = '<div style="font-weight:800;color:#065F46;font-size:.78rem;text-transform:uppercase;letter-spacing:.4px;margin-bottom:8px;">📋 Se guardarán ' + jugadas.length + ' jugadas</div>';
  listaHtml += '<div style="max-height:300px;overflow-y:auto;background:#f0fdf4;border:1.5px solid #86efac;border-radius:10px;padding:10px;">';
  listaHtml += '<table style="width:100%;font-size:.75rem;border-collapse:collapse;">';
  listaHtml += '<thead><tr style="border-bottom:1.5px solid #86efac;"><th style="text-align:left;padding:4px;">Sorteo</th><th style="text-align:left;padding:4px;">Forma</th><th style="text-align:left;padding:4px;">Número</th><th style="text-align:right;padding:4px;">Monto</th></tr></thead><tbody>';
  jugadas.forEach(function(j){
    listaHtml += '<tr><td style="padding:3px 4px;">' + (j.sorteo || '—') + '</td><td style="padding:3px 4px;">' + (j.forma_juego || '—') + '</td><td style="padding:3px 4px;font-family:monospace;">' + (j.numero || '—') + '</td><td style="padding:3px 4px;text-align:right;font-weight:800;color:#065F46;">$' + (j.monto || 0).toFixed(2) + '</td></tr>';
  });
  listaHtml += '</tbody></table></div>';
  if (descartadas > 0) {
    listaHtml += '<div style="margin-top:8px;background:#fee2e2;color:#7f1d1d;border-radius:6px;padding:6px 10px;font-weight:700;font-size:.72rem;">⚠️ ' + descartadas + ' jugada(s) descartada(s) por pool agotado o sorteo cerrado.</div>';
  }

  // Overlay completo
  var overlay = document.createElement('div');
  overlay.id = 'lottortPreviewOverlay';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:10000;display:flex;align-items:center;justify-content:center;padding:16px;overflow-y:auto;';
  overlay.innerHTML = ''
    + '<div style="background:#fff;border-radius:16px;max-width:720px;width:100%;max-height:90vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.4);border:2px solid #10B981;">'
    + '  <div style="background:linear-gradient(135deg,#065F46,#047857);color:#fff;padding:16px 22px;border-radius:14px 14px 0 0;border-bottom:2px solid #052e16;display:flex;justify-content:space-between;align-items:center;">'
    + '    <h5 style="margin:0;font-weight:900;font-size:1rem;"><i class="fas fa-clipboard-check" style="color:#fde047;margin-right:8px;"></i>Confirmar apuesta — Verificación final</h5>'
    + '    <button type="button" class="lottort-preview-close" style="background:transparent;border:none;color:#fff;font-size:1.3rem;cursor:pointer;line-height:1;padding:0 4px;">&times;</button>'
    + '  </div>'
    + '  <div style="padding:18px 22px;overflow-y:auto;flex:1;">'
    +      advHtml
    +      listaHtml
    + '    <div style="background:linear-gradient(135deg,#d1fae5,#a7f3d0);border:2px solid #10B981;border-radius:10px;padding:12px 14px;text-align:center;font-weight:900;color:#065F46;font-size:1.1rem;margin-top:14px;">'
    + '      <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.5px;">💵 Total a descontar</div>'
    + '      <div style="font-size:1.8rem;margin-top:4px;">$' + total.toFixed(2) + '</div>'
    + '    </div>'
    + '  </div>'
    + '  <div style="padding:14px 22px;border-top:1px solid #c8ead4;background:#f9fafb;border-radius:0 0 14px 14px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;">'
    + '    <button type="button" class="lottort-preview-close" style="background:#e5e7eb;color:#374151;border:none;padding:10px 20px;border-radius:10px;font-weight:800;cursor:pointer;font-family:inherit;font-size:.85rem;"><i class="fas fa-arrow-left"></i> Volver a editar</button>'
    + '    <button type="button" class="lottort-preview-confirm" style="background:linear-gradient(135deg,#10B981,#047857);color:#fff;border:none;padding:10px 26px;border-radius:10px;font-weight:900;cursor:pointer;font-family:inherit;font-size:.9rem;box-shadow:0 4px 12px rgba(4,120,87,.3);"><i class="fas fa-check-double"></i> Confirmar y guardar</button>'
    + '  </div>'
    + '</div>';

  document.body.appendChild(overlay);

  // Handlers
  overlay.querySelectorAll('.lottort-preview-close').forEach(function(btn){
    btn.addEventListener('click', function(){ overlay.remove(); });
  });

  overlay.querySelector('.lottort-preview-confirm').addEventListener('click', function(){
    overlay.remove();
    var b = document.getElementById('btnGo');
    if (b) { b.disabled = true; b.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...'; }
    enviarApuesta(false);
  });

  // Cerrar al hacer click fuera (opcional)
  overlay.addEventListener('click', function(e){
    if (e.target === overlay) overlay.remove();
  });
}'''

src_new, n = patron_func.subn(nueva_func, src, count=1)
if n == 0:
    print("ERROR: no encontre 'function mostrarPreviewApuesta'")
    raise SystemExit(1)

src = src_new
print("PASO 1: OK (mostrarPreviewApuesta → overlay custom)")

# ═══════════════════════════════════════════════════════════════
# PASO 2: Buscar si había un wrapper _mostrarPreviewApuesta_real y eliminar
# ═══════════════════════════════════════════════════════════════
patron_wrap = re.compile(
    r"function _mostrarPreviewApuesta_real\(data\)\{.*?\n\}",
    re.DOTALL,
)
src_new, n2 = patron_wrap.subn("", src)
if n2:
    src = src_new
    print(f"PASO 2: OK ({n2} wrapper(s) _real eliminados)")
else:
    print("PASO 2: SKIP")

p.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# REPORTE
# ═══════════════════════════════════════════════════════════════
print("\n═══ REPORTE ═══")
print(f"  lottortPreviewOverlay: {src.count('lottortPreviewOverlay')}")
print(f"  _mostrarPreviewApuesta_real: {src.count('_mostrarPreviewApuesta_real')}")
print(f"  modalPreview (HTML): {src.count('id=\"modalPreview\"')}")

# Verificar
if src == original:
    print("ERROR: sin cambios")
    raise SystemExit(1)
print("OK: archivo actualizado")
