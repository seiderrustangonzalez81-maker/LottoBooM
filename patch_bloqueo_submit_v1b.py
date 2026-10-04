from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

# ═══════════════════════════════════════════════════════════════
# 1) Guard DENTRO de enviarApuesta
# ═══════════════════════════════════════════════════════════════
if "GUARD_ENVIAR_APUESTA_V1" not in src:
    viejo = """function enviarApuesta(dryRun){
  if (typeof dryRun === 'undefined') dryRun = false;

  const items = recolectarItems();
  if (!items.length){ toast('No hay jugadas para guardar.', 'warning'); return; }"""

    nuevo = """function enviarApuesta(dryRun){
  if (typeof dryRun === 'undefined') dryRun = false;

  // ═══ GUARD_ENVIAR_APUESTA_V1: bloquear si hay filas que exceden ═══
  try {
    if (typeof _hayExcepcionesActivas === 'function'){
      var _exc = _hayExcepcionesActivas();
      if (_exc.bloqueado){
        _avisarExcepciones(_exc);
        var _b = document.getElementById('btnGo');
        if (_b){ _b.disabled = false; _b.innerHTML = '<i class="fas fa-check-circle"></i> Confirmar apuesta'; }
        return;
      }
    }
  } catch(_eG){ console.warn('[GUARD_ENVIAR]', _eG); }
  // ═══ FIN GUARD_ENVIAR_APUESTA_V1 ═══

  const items = recolectarItems();
  if (!items.length){ toast('No hay jugadas para guardar.', 'warning'); return; }"""

    if viejo not in src:
        print("ERROR: no encontré el header exacto de enviarApuesta")
        print("Pégame: sed -n '4220,4225p' /home/LottoBooM/jugadas/templates/jugadas/apostar.html")
        raise SystemExit(1)
    src = src.replace(viejo, nuevo, 1)
    print("OK 1: GUARD_ENVIAR_APUESTA_V1 insertado dentro de enviarApuesta")
else:
    print("SKIP 1: guard ya existe")


# ═══════════════════════════════════════════════════════════════
# 2) Añadir #btnGo al interceptor de click (defensa extra)
# ═══════════════════════════════════════════════════════════════
viejo_interceptor = "var btn = ev.target.closest && ev.target.closest('#btnEnviar, .btn-enviar, button[type=\"submit\"], [data-action=\"enviar\"]');"
nuevo_interceptor = "var btn = ev.target.closest && ev.target.closest('#btnGo, #btnEnviar, .btn-enviar, button[type=\"submit\"], [data-action=\"enviar\"]');"
if viejo_interceptor in src:
    src = src.replace(viejo_interceptor, nuevo_interceptor, 1)
    print("OK 2: interceptor ahora también atrapa #btnGo")
else:
    print("WARN 2: no encontré la línea del interceptor (quizá ya cambió)")


# ═══════════════════════════════════════════════════════════════
# 3) CSS del pulse (forzar, sin el check buggy)
# ═══════════════════════════════════════════════════════════════
if "@keyframes btnExcedePulse" not in src:
    css = """
  /* BLOQUEO_SUBMIT_V1 */
  @keyframes btnExcedePulse{
    0%,100%{ transform: scale(1); box-shadow: 0 0 0 0 rgba(220,38,38,.55); }
    50%    { transform: scale(1.03); box-shadow: 0 0 0 8px rgba(220,38,38,0); }
  }
  .btn-excede-pulse{
    animation: btnExcedePulse 0.55s ease-in-out 3;
    background: #dc2626 !important;
    border-color: #dc2626 !important;
    color: #fff !important;
  }
"""
    idx = src.find("</style>")
    if idx == -1:
        print("WARN 3: no encontré </style>")
    else:
        src = src[:idx] + css + src[idx:]
        print("OK 3: CSS insertado")
else:
    print("SKIP 3: CSS ya existe (@keyframes btnExcedePulse encontrado)")

p.write_text(src, encoding="utf-8")

print()
print("═══ Resumen ═══")
print("GUARD_ENVIAR_APUESTA_V1 :", src.count("GUARD_ENVIAR_APUESTA_V1"))
print("_hayExcepcionesActivas  :", src.count("_hayExcepcionesActivas"))
print("@keyframes btnExcedePulse:", src.count("@keyframes btnExcedePulse"))
print("#btnGo, #btnEnviar      :", src.count("#btnGo, #btnEnviar"))
