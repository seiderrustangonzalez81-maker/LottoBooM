from pathlib import Path
import re

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# Localizar la función completa
idx_ini = src.find("function preloadBoletaEdit(data) {")
# Encontrar el inicio de la siguiente función
idx_fin = src.find("function inyectarLineasBoleta(data) {")

if idx_ini == -1 or idx_fin == -1:
    print("ERROR: no encontre las funciones")
    raise SystemExit(1)

nueva = '''function preloadBoletaEdit(data) {
  console.log('=== [apostar] INICIO PRECARGA (v3 - robusto) ===');
  console.log('[apostar] Data:', JSON.stringify(data, null, 2));

  var _stats = { cliente: false, fp: false, sorteos: 0, jugadas: 0 };

  // ═══ 1. Setear cliente DIRECTO (sin evento) ═══
  var selCli = document.getElementById('selCliente');
  if (!selCli){
    console.error('[apostar] No existe #selCliente');
    return;
  }

  // Asegurar option
  var optExiste = false;
  for (var _i = 0; _i < selCli.options.length; _i++){
    if (String(selCli.options[_i].value) === String(data.cliente_id)){
      optExiste = true; break;
    }
  }
  if (!optExiste){
    var _opt = document.createElement('option');
    _opt.value = String(data.cliente_id);
    _opt.textContent = (data.cliente_nombre || 'Cliente') + ' (edit)';
    _opt.dataset.nombre = data.cliente_nombre || 'Cliente';
    _opt.dataset.telefono = '';
    _opt.dataset.saldo = '0';
    _opt.dataset.bonos = '0';
    _opt.dataset.rol = 'cliente';
    selCli.appendChild(_opt);
  }
  selCli.value = String(data.cliente_id);

  // Setear variables globales DIRECTAMENTE (evita depender del change event)
  cliente = {
    id: String(data.cliente_id),
    nombre: data.cliente_nombre || 'Cliente',
    telefono: '',
    saldo: 0,
    bonos: 0,
    rol: 'cliente'
  };
  bonoDisp = 0;
  _stats.cliente = true;
  console.log('[apostar] Cliente seteado directo:', cliente.nombre);

  // ═══ 2. Forzar FP seleccionada ═══
  fpSel = String(data.forma_pago_id);
  saldoFP = 0;  // No bloquearemos por saldo en precarga
  chipEspecial = null;
  _stats.fp = true;
  console.log('[apostar] FP forzada:', fpSel);

  // ═══ 3. Setear fecha ═══
  var inpFecha = document.getElementById('inpFecha');
  if (inpFecha && data.fecha_sorteo) inpFecha.value = data.fecha_sorteo;

  // ═══ 4. Cargar formas de pago (para mostrar chips) ═══
  try {
    if (typeof cargarFormasPago === 'function') {
      cargarFormasPago();
    }
  } catch(e){ console.warn('[apostar] cargarFormasPago error:', e); }

  // ═══ 5. Cargar sorteos ═══
  var _sorteosCargados = false;
  function _cargarSorteosYContinuar(){
    if (_sorteosCargados) return;
    _sorteosCargados = true;
    console.log('[apostar] Cargando sorteos...');
    try {
      cargarSorteos();
    } catch(e){ console.warn('[apostar] cargarSorteos error:', e); }
    // Esperar a que aparezcan botones de sorteo
    _esperarYActivarSorteos(0);
  }

  function _esperarYActivarSorteos(intento){
    if (intento > 30){  // max 15s
      console.error('[apostar] Timeout esperando sorteos');
      return;
    }
    var botones = document.querySelectorAll('.sorteo-btn');
    if (!botones.length){
      setTimeout(function(){ _esperarYActivarSorteos(intento + 1); }, 500);
      return;
    }
    console.log('[apostar] Sorteos disponibles:', botones.length);
    // Activar los sorteos de la boleta
    (data.sorteo_ids || []).forEach(function(sid){
      var btn = document.querySelector('.sorteo-btn[data-id="' + sid + '"]');
      if (btn && !btn.classList.contains('active')){
        btn.click();
        _stats.sorteos++;
        console.log('[apostar] Sorteo activado:', sid);
      }
    });
    // Esperar a que se carguen las configs
    _esperarYInyectar(0);
  }

  function _esperarYInyectar(intento){
    if (intento > 40){  // max 20s
      console.error('[apostar] Timeout esperando configs');
      // Inyectar de todos modos
      try { inyectarLineasBoleta(data); } catch(e){}
      return;
    }
    if (typeof sorteosActivos === 'undefined'){
      setTimeout(function(){ _esperarYInyectar(intento + 1); }, 500);
      return;
    }
    var ids = data.sorteo_ids || [];
    var todosCargados = ids.every(function(sid){
      var s = sorteosActivos[String(sid)] || sorteosActivos[sid];
      return s && s.cargado;
    });
    if (!todosCargados){
      setTimeout(function(){ _esperarYInyectar(intento + 1); }, 500);
      return;
    }
    console.log('[apostar] Inyectando lineas...');
    try {
      var st = inyectarLineasBoleta(data);
      _stats.jugadas = st ? st.inyectadas : 0;
    } catch(e){
      console.error('[apostar] Error inyectando:', e);
    }
    console.log('=== [apostar] FIN PRECARGA ===', _stats);
  }

  // Arrancar el flujo
  setTimeout(_cargarSorteosYContinuar, 300);
}

'''

src_new = src[:idx_ini] + nueva + src[idx_fin:]
p.write_text(src_new, encoding="utf-8")
print("OK: preloadBoletaEdit reescrita (v3 robusto)")

# Verificar que sigue estando la función inyectar
if "function inyectarLineasBoleta" in src_new:
    print("OK: inyectarLineasBoleta preservada")
else:
    print("ERROR: se perdio inyectarLineasBoleta")
    raise SystemExit(1)

# Verificar balance básico
print(f"preloadBoletaEdit: {src_new.count('function preloadBoletaEdit')}")
print(f"inyectarLineasBoleta: {src_new.count('function inyectarLineasBoleta')}")
