from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if 'id="modalRecargaRapida"' in src:
    print("SKIP: modal ya existe")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# 1) Modal HTML
# ═══════════════════════════════════════════════════════════════
modal_html = '''
{# ═══════ MODAL RECARGA RÁPIDA ═══════ #}
<div class="modal fade" id="modalRecargaRapida" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content" style="border-radius:16px;border:2px solid #f59e0b;">
      <div class="modal-header" style="background:linear-gradient(135deg,#d97706,#92400e);color:#fff;border-bottom:2px solid #78350f;">
        <h5 class="modal-title fw-bold" style="text-shadow:0 1px 2px rgba(0,0,0,.4);">
          <i class="fas fa-plus-circle me-2" style="color:#fde047;"></i>
          Recargar a este cliente
        </h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div style="background:#f0fdf4;border:1.5px solid #86efac;border-radius:8px;padding:10px 12px;margin-bottom:14px;font-size:.82rem;">
          <div style="font-weight:800;color:#065F46;">Cliente: <span id="mrrCliente">—</span></div>
          <div style="color:#047857;font-weight:700;font-size:.78rem;margin-top:2px;">Fondo actual: <span id="mrrFondoActual">$0.00</span></div>
        </div>

        <div class="mb-3">
          <label class="ap-label mb-1" style="font-weight:800;">Forma de pago <span style="color:#DC2626;">*</span></label>
          <select id="mrrFormaPago" class="form-select" style="border-radius:10px;border:1.5px solid #b6e5c2;font-weight:700;color:#1e3a8a;">
            {% for fp in formas_pago_recarga %}<option value="{{ fp.id }}">{{ fp.nombre }}</option>{% endfor %}
          </select>
        </div>

        <div class="mb-3">
          <label class="ap-label mb-1" style="font-weight:800;">Monto a recargar <span style="color:#DC2626;">*</span></label>
          <input type="number" step="0.01" min="0.01" id="mrrMonto" class="form-control" placeholder="0" style="border-radius:10px;border:1.5px solid #b6e5c2;font-weight:700;color:#1e3a8a;font-size:1.1rem;">
        </div>

        <div id="mrrError" style="display:none;background:#fee2e2;border:1.5px solid #fca5a5;color:#7f1d1d;padding:8px 12px;border-radius:8px;font-weight:700;font-size:.8rem;"></div>
      </div>
      <div class="modal-footer" style="border-top:1px solid #c8ead4;">
        <button type="button" class="btn btn-secondary fw-bold" data-bs-dismiss="modal" style="border-radius:10px;">Cancelar</button>
        <button type="button" class="btn fw-bold" id="mrrConfirmar" style="background:linear-gradient(135deg,#f59e0b,#d97706);color:#fff;border-radius:10px;">
          <i class="fas fa-check"></i> Confirmar recarga
        </button>
      </div>
    </div>
  </div>
</div>
'''

# Insertar antes del modalPreview
if 'id="modalPreview"' in src:
    src = src.replace('<div class="modal fade" id="modalPreview"', modal_html + '\n<div class="modal fade" id="modalPreview"', 1)
else:
    if "{% block extra_js %}" in src:
        src = src.replace("{% block extra_js %}", modal_html + "\n{% block extra_js %}", 1)
    else:
        idx = src.rfind("{% endblock %}")
        src = src[:idx] + modal_html + src[idx:]
print("OK: modal HTML agregado")

# ═══════════════════════════════════════════════════════════════
# 2) Reescribir el handler del boton btnRecargarQuick
# ═══════════════════════════════════════════════════════════════
# Buscar el bloque original del JS que maneja recarga
viejo_js = """  var preselect = '{{ cliente_preseleccionado_id|default:\"\" }}';"""

# Insertar antes del bloque de preselect un nuevo handler
nuevo_js = '''  // ═══════════════════════════════════════════════════════════════
  // MODAL RECARGA RÁPIDA (reemplaza el redirect)
  // ═══════════════════════════════════════════════════════════════
  btn.addEventListener('click', function(e){
    e.preventDefault();
    e.stopImmediatePropagation();
    if (!cliente || !fpSel) return;

    // Setup modal
    var modalEl = document.getElementById('modalRecargaRapida');
    if (!modalEl) { alert('Modal no disponible'); return; }
    var mrrCli = document.getElementById('mrrCliente');
    if (mrrCli) mrrCli.textContent = cliente.nombre;
    var mrrSel = document.getElementById('mrrFormaPago');
    if (mrrSel && fpSel) mrrSel.value = fpSel;
    var mrrInp = document.getElementById('mrrMonto');
    if (mrrInp) mrrInp.value = '';
    var mrrErr = document.getElementById('mrrError');
    if (mrrErr) mrrErr.style.display = 'none';

    // Mostrar fondo actual del chip
    var chipAct = document.querySelector('.fp-chip.active');
    var fondoAct = chipAct ? (chipAct.querySelector('strong') ? chipAct.querySelector('strong').textContent : '$0.00') : '$0.00';
    var mrrFondo = document.getElementById('mrrFondoActual');
    if (mrrFondo) mrrFondo.textContent = fondoAct;

    new bootstrap.Modal(modalEl).show();
  }, true);  // capture: true para que se ejecute ANTES que otros listeners

  // Boton confirmar del modal
  setTimeout(function(){
    var btnConf = document.getElementById('mrrConfirmar');
    if (!btnConf || btnConf.dataset.bound) return;
    btnConf.dataset.bound = '1';
    btnConf.addEventListener('click', function(){
      var fp = document.getElementById('mrrFormaPago').value;
      var monto = parseFloat(document.getElementById('mrrMonto').value) || 0;
      var errBox = document.getElementById('mrrError');

      if (!fp || monto <= 0){
        errBox.textContent = 'Selecciona forma de pago y monto mayor a 0.';
        errBox.style.display = 'block';
        return;
      }
      errBox.style.display = 'none';
      btnConf.disabled = true;
      btnConf.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

      var fd = new FormData();
      fd.append('usuario_id', cliente.id);
      fd.append('forma_pago_id', fp);
      fd.append('monto', monto.toFixed(2));
      fd.append('csrfmiddlewaretoken', CSRF);

      fetch("{% url 'roles:api_recarga_rapida' %}", {
        method: 'POST',
        body: fd,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
      .then(function(r){ return r.json(); })
      .then(function(d){
        btnConf.disabled = false;
        btnConf.innerHTML = '<i class="fas fa-check"></i> Confirmar recarga';
        if (d.success){
          bootstrap.Modal.getInstance(document.getElementById('modalRecargaRapida')).hide();
          if (typeof toast === 'function') {
            toast('💰 Recarga exitosa: $' + d.monto.toFixed(2) + ' en ' + d.forma_pago_nombre + '. Nuevo saldo: $' + d.saldo_actual.toFixed(2), 'success');
          }
          // Recargar chips (sin recargar la página)
          if (typeof cargarFormasPago === 'function') {
            cargarFormasPago();
          }
        } else {
          errBox.textContent = d.error || 'Error al recargar';
          errBox.style.display = 'block';
        }
      })
      .catch(function(e){
        btnConf.disabled = false;
        btnConf.innerHTML = '<i class="fas fa-check"></i> Confirmar recarga';
        errBox.textContent = 'Error de conexión: ' + e.message;
        errBox.style.display = 'block';
      });
    });
  }, 500);

  var preselect = '{{ cliente_preseleccionado_id|default:"" }}';'''

if viejo_js not in src:
    print("WARN: no encontre el ancla del preselect, no agregue el handler del modal")
else:
    src = src.replace(viejo_js, nuevo_js, 1)
    print("OK: handler modal agregado")

p.write_text(src, encoding="utf-8")
print("OK: template actualizado")
