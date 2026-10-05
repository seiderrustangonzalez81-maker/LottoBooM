from pathlib import Path

p = Path("/home/LottoBooM/templates/publico/home.html")
src = p.read_text(encoding="utf-8")

if "FIX_ANIMATE_COUNTER_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

viejo = """  const counters = document.querySelectorAll('[data-stat]');
  function animateCounter(el) {
    const target = parseInt(el.getAttribute('data-stat'), 10) || 0;
    if (target === 0) { el.textContent = '0'; return; }
    if (reduceMotion) { el.textContent = target.toLocaleString(); return; }
    const duration = 1200;
    const start = performance.now();
    const step = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(eased * target).toLocaleString();
      if (t < 1) requestAnimationFrame(step);
      else el.textContent = target.toLocaleString();
    };
    requestAnimationFrame(step);
  }"""

nuevo = """  // FIX_ANIMATE_COUNTER_V1: leer el texto renderizado, no data-stat
  const counters = document.querySelectorAll('[data-stat]');
  function animateCounter(el) {
    // El valor real ya está en el textContent que renderizó Django
    const raw = (el.textContent || '').replace(/[^0-9.\\-]/g, '');
    const target = parseFloat(raw) || 0;
    if (target === 0) { el.textContent = '0'; return; }
    // Si no animamos, dejamos el valor tal cual
    if (reduceMotion) return;
    const esMoneda = el.textContent.includes('$');
    const decimales = esMoneda ? 2 : 0;
    const duration = 1200;
    const start = performance.now();
    const fmt = (n) => {
      if (esMoneda) return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      return Math.round(n).toLocaleString('en-US');
    };
    const step = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = fmt(eased * target);
      if (t < 1) requestAnimationFrame(step);
      else el.textContent = fmt(target);
    };
    requestAnimationFrame(step);
  }"""

if viejo not in src:
    print("ERROR: no encontré el bloque animateCounter")
    raise SystemExit(1)

src = src.replace(viejo, nuevo, 1)
p.write_text(src, encoding="utf-8")
print("OK: FIX_ANIMATE_COUNTER_V1 aplicado")
print("  · ahora lee el textContent renderizado, no data-stat")
print("  · respeta el prefijo $ para moneda")
