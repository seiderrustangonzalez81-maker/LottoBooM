from pathlib import Path

p = Path("/home/LottoBooM/templates/roles/solicitar_retiro.html")
src = p.read_text(encoding="utf-8")

if 'name="motivo_tipo"' in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

# Ancla: el campo "Mensaje para el gestor" — insertamos ANTES
ancla = '''        <div class="ret-field">
          <label class="ret-label">Mensaje para el gestor</label>'''

if ancla not in src:
    print("ERROR: no encontre el ancla del mensaje")
    raise SystemExit(1)

bloque_motivo = '''        <div class="ret-field">
          <label class="ret-label">Motivo del retiro <span class="req">*</span></label>
          <select name="motivo_tipo" id="ret-motivo-tipo" class="ret-select" required>
            <option value="">-- Selecciona el motivo --</option>
            <option value="cobro_premios">Cobro de premios</option>
            <option value="donacion_banco">Donacion al banco</option>
            <option value="donacion_comercial">Donacion al comercial</option>
            <option value="donacion_gestor">Donacion al gestor</option>
            <option value="otro">Otro (especificar)</option>
          </select>
        </div>

        <div class="ret-field" id="ret-motivo-otro-wrap" style="display:none;">
          <label class="ret-label">Especifica el motivo <span class="req">*</span></label>
          <input type="text" name="motivo_detalle" id="ret-motivo-detalle"
                 class="ret-input" maxlength="200"
                 placeholder="Escribe el motivo del retiro...">
        </div>

'''

src_new = src.replace(ancla, bloque_motivo + ancla, 1)

# Insertar JS para mostrar/ocultar el campo "otro"
js_ancla = "const selFP = document.getElementById('ret-forma-pago');"
js_add = '''const selMotivo = document.getElementById('ret-motivo-tipo');
  const wrapMotivoOtro = document.getElementById('ret-motivo-otro-wrap');
  const inpMotivoDetalle = document.getElementById('ret-motivo-detalle');

  if (selMotivo) {
    selMotivo.addEventListener('change', function(){
      if (this.value === 'otro') {
        wrapMotivoOtro.style.display = '';
        inpMotivoDetalle.required = true;
      } else {
        wrapMotivoOtro.style.display = 'none';
        inpMotivoDetalle.required = false;
        inpMotivoDetalle.value = '';
      }
    });
  }

  '''

if js_ancla in src_new:
    src_new = src_new.replace(js_ancla, js_add + js_ancla, 1)
    print("OK JS toggle agregado")
else:
    print("WARN no encontre el JS para insertar el toggle")

p.write_text(src_new, encoding="utf-8")
print("OK template con dropdown de motivos")

assert 'name="motivo_tipo"' in src_new
assert 'ret-motivo-otro-wrap' in src_new
print("OK verificacion")

