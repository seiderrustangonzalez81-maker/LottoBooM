from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "lottortRetiroBtn" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# ═══════════════════════════════════════════════════════════════
# 1. BOTONES — insertar junto al botón "Recargar a este cliente"
# ═══════════════════════════════════════════════════════════════
viejo_btn = '''<button type="button" id="btnRecargarQuick" style="'''

if viejo_btn not in src:
    print("ERROR: no encontre btnRecargarQuick")
    raise SystemExit(1)

# Insertar botones antes de btnRecargarQuick
nuevos_botones = '''<button type="button" id="lottortLimitesBtn" style="
              width:100%;padding:9px 14px;margin-bottom:8px;
              background:linear-gradient(145deg,#6366f1,#4f46e5);
              color:#fff;font-weight:800;font-size:.85rem;
              border:2px solid #3730a3;border-radius:10px;
              cursor:pointer;box-shadow:3px 3px 0 #3730a3;
              display:none;align-items:center;justify-content:center;gap:8px;
              font-family:inherit;letter-spacing:.3px;transition:.15s;">
              <i class="fas fa-chart-bar"></i> Ver limites del gestor
            </button>
            <button type="button" id="lottortRetiroBtn" style="
              width:100%;padding:9px 14px;margin-bottom:8px;
              background:linear-gradient(145deg,#dc2626,#991b1b);
              color:#fff;font-weight:800;font-size:.85rem;
              border:2px solid #7f1d1d;border-radius:10px;
              cursor:pointer;box-shadow:3px 3px 0 #7f1d1d;
              display:none;align-items:center;justify-content:center;gap:8px;
              font-family:inherit;letter-spacing:.3px;transition:.15s;">
              <i class="fas fa-hand-holding-usd"></i> Descontar del fondo
            </button>
            '''

src = src.replace(viejo_btn, nuevos_botones + viejo_btn, 1)
print("OK: botones insertados")

# ═══════════════════════════════════════════════════════════════
# 2. JS — lógica de los botones + modales con overlay custom
# ═══════════════════════════════════════════════════════════════
script_js = '''
/* ═══════════════════════════════════════════════════════════════
   lottort-retiro-limites: Botones de retiro + límites del gestor
   ═══════════════════════════════════════════════════════════════ */
(function(){
  var _modalAbierto = null;

  function _cerrarModal(){
    if (_modalAbierto){
      try { _modalAbierto.remove(); } catch(e){}
      _modalAbierto = null;
    }
  }

  function _crearOverlay(html){
    _cerrarModal();
    var ov = document.createElement('div');
    ov.id = 'lottortOverlayHelper';
    ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:10001;display:flex;align-items:center;justify-content:center;padding:16px;overflow-y:auto;';
    ov.innerHTML = html;
    document.body.appendChild(ov);
    ov.addEventListener('click', function(e){ if (e.target === ov) _cerrarModal(); });
    _modalAbierto = ov;
    return ov;
  }

  // ═══ VISIBILIDAD DE BOTONES ═══
  function _actualizarVisibilidadBotones(){
    var btnRetiro = document.getElementById('lottortRetiroBtn');
    var btnLimites = document.getElementById('lottortLimitesBtn');
    if (!btnRetiro || !btnLimites) return;

    // Retiro: solo si NO es cliente y hay cliente + FP seleccionados
    var esGestor = !ES_CLIENTE;
    var tieneDatos = cliente && cliente.id && fpSel;
    btnRetiro.style.display = (esGestor && tieneDatos) ? 'inline-flex' : 'none';

    // Limites: siempre visible cuando hay cliente + al menos 1 sorteo activo
    var tieneSorteo = typeof ordenSorteos !== 'undefined' && ordenSorteos.length > 0;
    btnLimites.style.display = (tieneDatos && tieneSorteo) ? 'inline-flex' : 'none';
  }

  // Observar cambios cada 500ms (sencillo y suficiente)
  setInterval(_actualizarVisibilidadBotones, 500);
  setTimeout(_actualizarVisibilidadBotones, 1000);

  // ═══ BOTON RETIRO ═══
  document.addEventListener('click', function(e){
    var btn = e.target.closest && e.target.closest('#lottortRetiroBtn');
    if (!btn) return;
    if (!cliente || !fpSel) return;

    // Mostrar saldo actual del chip
    var chipAct = document.querySelector('.fp-chip.active');
    var fondoAct = chipAct && chipAct.querySelector('strong') ? chipAct.querySelector('strong').textContent : '$0.00';

    var overlay = _crearOverlay(''
      + '<div style="background:#fff;border-radius:16px;max-width:520px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.4);border:2px solid #DC2626;">'
      + '  <div style="background:linear-gradient(135deg,#DC2626,#7f1d1d);color:#fff;padding:16px 22px;border-radius:14px 14px 0 0;display:flex;justify-content:space-between;align-items:center;">'
      + '    <h5 style="margin:0;font-weight:900;font-size:1rem;"><i class="fas fa-hand-holding-usd" style="margin-right:8px;"></i>Descontar del fondo</h5>'
      + '    <button type="button" class="lottort-cerrar" style="background:transparent;border:none;color:#fff;font-size:1.4rem;cursor:pointer;line-height:1;">&times;</button>'
      + '  </div>'
      + '  <div style="padding:18px 22px;">'
      + '    <div style="background:#fef2f2;border:1.5px solid #fca5a5;border-radius:8px;padding:10px 12px;margin-bottom:14px;font-size:.82rem;">'
      + '      <div style="font-weight:800;color:#7f1d1d;">Cliente: ' + (cliente.nombre || '—') + '</div>'
      + '      <div style="color:#991b1b;font-weight:700;font-size:.78rem;margin-top:2px;">Fondo disponible: ' + fondoAct + '</div>'
      + '    </div>'
      + '    <label style="font-weight:800;font-size:.78rem;color:#7f1d1d;display:block;margin-bottom:6px;">Motivo *</label>'
      + '    <select id="lottortRetiroMotivo" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:700;color:#7f1d1d;background:#fff;font-size:.85rem;font-family:inherit;margin-bottom:14px;">'
      + '      <option value="cobro_premios">Cobro de premios</option>'
      + '      <option value="donacion_banco">Donacion al banco</option>'
      + '      <option value="donacion_comercial">Donacion al comercial</option>'
      + '      <option value="donacion_gestor">Donacion al gestor</option>'
      + '      <option value="ajuste">Ajuste de fondo</option>'
      + '      <option value="retiro_presencial">Retiro presencial</option>'
      + '      <option value="otro">Otro (especificar)</option>'
      + '    </select>'
      + '    <input type="text" id="lottortRetiroDetalle" placeholder="Detalle (si es Otro)" maxlength="200" style="width:100%;padding:8px 12px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:700;color:#7f1d1d;background:#fff;font-size:.85rem;font-family:inherit;margin-bottom:14px;display:none;">'
      + '    <label style="font-weight:800;font-size:.78rem;color:#7f1d1d;display:block;margin-bottom:6px;">Monto a descontar *</label>'
      + '    <input type="number" id="lottortRetiroMonto" step="0.01" min="0.01" placeholder="0" style="width:100%;padding:10px 14px;border-radius:8px;border:1.5px solid #fca5a5;font-weight:900;color:#7f1d1d;background:#fff;font-size:1.1rem;font-family:inherit;margin-bottom:14px;">'
      + '    <div id="lottortRetiroError" style="display:none;background:#fee2e2;border:1.5px solid #dc2626;color:#7f1d1d;padding:8px 12px;border-radius:8px;font-weight:700;font-size:.78rem;margin-bottom:12px;"></div>'
      + '  </div>'
      + '  <div style="padding:14px 22px;border-top:1px solid #fca5a5;background:#f9fafb;border-radius:0 0 14px 14px;display:flex;justify-content:space-between;gap:10px;">'
      + '    <button type="button" class="lottort-cerrar" style="background:#e5e7eb;color:#374151;border:none;padding:10px 20px;border-radius:10px;font-weight:800;cursor:pointer;font-family:inherit;font-size:.85rem;">Cancelar</button>'
      + '    <button type="button" id="lottortRetiroConfirmar" style="background:linear-gradient(135deg,#DC2626,#7f1d1d);color:#fff;border:none;padding:10px 26px;border-radius:10px;font-weight:900;cursor:pointer;font-family:inherit;font-size:.9rem;"><i class="fas fa-check"></i> Confirmar retiro</button>'
      + '  </div>'
      + '</div>');

    overlay.querySelectorAll('.lottort-cerrar').forEach(function(b){
      b.addEventListener('click', _cerrarModal);
    });

    var selMotivo = document.getElementById('lottortRetiroMotivo');
    var inpDetalle = document.getElementById('lottortRetiroDetalle');
    selMotivo.addEventListener('change', function(){
      inpDetalle.style.display = (this.value === 'otro') ? 'block' : 'none';
    });

    document.getElementById('lottortRetiroConfirmar').addEventListener('click', function(){
      var monto = parseFloat(document.getElementById('lottortRetiroMonto').value) || 0;
      var motivo = selMotivo.value;
      var detalle = inpDetalle.value.trim();
      var errBox = document.getElementById('lottortRetiroError');
      if (monto <= 0){
        errBox.textContent = 'Ingresa un monto mayor a 0';
        errBox.style.display = 'block';
        return;
      }
      errBox.style.display = 'none';
      var btnC = this;
      btnC.disabled = true;
      btnC.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

      var fd = new FormData();
      fd.append('usuario_id', cliente.id);
      fd.append('forma_pago_id', fpSel);
      fd.append('monto', monto.toFixed(2));
      fd.append('motivo_tipo', motivo);
      fd.append('motivo_detalle', detalle);
      fd.append('csrfmiddlewaretoken', CSRF);

      fetch("{% url 'roles:api_retiro_rapido' %}", {
        method: 'POST', body: fd,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      }).then(function(r){ return r.json(); }).then(function(d){
        if (!d.success){
          errBox.textContent = d.error || 'Error';
          errBox.style.display = 'block';
          btnC.disabled = false;
          btnC.innerHTML = '<i class="fas fa-check"></i> Confirmar retiro';
          return;
        }
        _cerrarModal();
        if (typeof toast === 'function') toast('Retiro de $' + d.monto.toFixed(2) + '. Nuevo saldo: $' + d.saldo_despues.toFixed(2), 'success');
        if (typeof cargarFormasPago === 'function') cargarFormasPago();
      }).catch(function(e){
        errBox.textContent = 'Error: ' + e.message;
        errBox.style.display = 'block';
        btnC.disabled = false;
        btnC.innerHTML = '<i class="fas fa-check"></i> Confirmar retiro';
      });
    });
  });

  // ═══ BOTON LIMITES ═══
  document.addEventListener('click', function(e){
    var btn = e.target.closest && e.target.closest('#lottortLimitesBtn');
    if (!btn) return;
    if (!cliente || !ordenSorteos.length) return;

    // Sorteo activo
    var sid = ordenSorteos[0];
    var s = (typeof sorteosActivos !== 'undefined') ? sorteosActivos[sid] : null;
    var nombreSorteo = s ? s.nombre : '—';
    var gestorId = (typeof getDestinatarioId === 'function') ? getDestinatarioId() : null;

    var overlay = _crearOverlay(''
      + '<div style="background:#fff;border-radius:16px;max-width:600px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.4);border:2px solid #4f46e5;">'
      + '  <div style="background:linear-gradient(135deg,#4f46e5,#3730a3);color:#fff;padding:16px 22px;border-radius:14px 14px 0 0;display:flex;justify-content:space-between;align-items:center;">'
      + '    <h5 style="margin:0;font-weight:900;font-size:1rem;"><i class="fas fa-chart-bar" style="margin-right:8px;"></i>Limites y dosis del gestor</h5>'
      + '    <button type="button" class="lottort-cerrar" style="background:transparent;border:none;color:#fff;font-size:1.4rem;cursor:pointer;line-height:1;">&times;</button>'
      + '  </div>'
      + '  <div style="padding:18px 22px;">'
      + '    <div style="background:#eef2ff;border:1.5px solid #c7d2fe;border-radius:8px;padding:10px 12px;margin-bottom:14px;font-size:.82rem;">'
      + '      <div style="font-weight:800;color:#3730a3;">Gestor: ' + (s ? 'activo' : '—') + '</div>'
      + '      <div style="color:#4338ca;font-weight:700;font-size:.78rem;margin-top:2px;">Sorteo: ' + nombreSorteo + '</div>'
      + '    </div>'
      + '    <div id="lottortLimitesContenido" style="min-height:100px;text-align:center;color:#6B7280;padding:20px;">'
      + '      <i class="fas fa-spinner fa-spin"></i> Cargando limites...'
      + '    </div>'
      + '  </div>'
      + '  <div style="padding:14px 22px;border-top:1px solid #c7d2fe;background:#f9fafb;border-radius:0 0 14px 14px;text-align:right;">'
      + '    <button type="button" class="lottort-cerrar" style="background:#e5e7eb;color:#374151;border:none;padding:10px 20px;border-radius:10px;font-weight:800;cursor:pointer;font-family:inherit;font-size:.85rem;">Cerrar</button>'
      + '  </div>'
      + '</div>');

    overlay.querySelectorAll('.lottort-cerrar').forEach(function(b){
      b.addEventListener('click', _cerrarModal);
    });

    // Fetch limites
    fetch("{% url 'roles:api_limites_gestor' %}?gestor_id=" + gestorId + "&sorteo_id=" + sid)
      .then(function(r){ return r.json(); })
      .then(function(d){
        var cont = document.getElementById('lottortLimitesContenido');
        if (!d.success){
          cont.innerHTML = '<div style="color:#dc2626;">' + (d.error || 'Error al cargar') + '</div>';
          return;
        }
        var formas = d.formas || [];
        if (!formas.length){
          cont.innerHTML = '<div style="color:#6B7280;font-style:italic;">Sin limites configurados para este sorteo.</div>';
          return;
        }
        var html = '<table style="width:100%;border-collapse:collapse;font-size:.82rem;">'
                 + '<thead><tr style="background:#eef2ff;color:#3730a3;">'
                 + '<th style="padding:8px;text-align:left;border-radius:6px 0 0 0;">Forma</th>'
                 + '<th style="padding:8px;text-align:right;">Limite</th>'
                 + '<th style="padding:8px;text-align:right;">Dosis</th>'
                 + '<th style="padding:8px;text-align:right;border-radius:0 6px 0 0;">Sobrelimite</th>'
                 + '</tr></thead><tbody>';
        formas.forEach(function(f){
          html += '<tr style="border-bottom:1px solid #e5e7eb;">'
               + '<td style="padding:8px;font-weight:800;color:#3730a3;">' + f.forma + '</td>'
               + '<td style="padding:8px;text-align:right;font-family:monospace;font-weight:800;color:#065F46;">$' + f.limite.toFixed(2) + '</td>'
               + '<td style="padding:8px;text-align:right;font-family:monospace;font-weight:800;color:#4338ca;">x' + f.dosis.toFixed(2) + '</td>'
               + '<td style="padding:8px;text-align:right;font-family:monospace;font-weight:800;color:#b45309;">$' + f.sobrelimite.toFixed(2) + '</td>'
               + '</tr>';
        });
        html += '</tbody></table>';
        cont.innerHTML = html;
      })
      .catch(function(e){
        document.getElementById('lottortLimitesContenido').innerHTML = '<div style="color:#dc2626;">Error: ' + e.message + '</div>';
      });
  });
})();
'''

# Insertar antes de "window.autoformatear"
ancla = "window.autoformatear = autoformatear;"
if "_esperarChipFPSaldo" in src and "lottort-retiro-limites" not in src:
    src = src.replace(ancla, script_js + "\n" + ancla, 1)
    print("OK: JS insertado")
else:
    if "lottort-retiro-limites" in src:
        print("SKIP: JS ya insertado")
    else:
        print("WARN: no encontre ancla de window.autoformatear")

p.write_text(src, encoding="utf-8")
print("OK: template apostar.html actualizado")
print(f"lottortRetiroBtn: {src.count('lottortRetiroBtn')}")
print(f"lottortLimitesBtn: {src.count('lottortLimitesBtn')}")
