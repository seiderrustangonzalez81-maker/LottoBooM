from pathlib import Path

p = Path("/home/LottoBooM/publico/templates/publico/home.html")
if not p.exists():
    # Fallback — buscar dónde está
    for alt in [
        "/home/LottoBooM/templates/publico/home.html",
        "/home/LottoBooM/publico/templates/publico/home.html",
    ]:
        if Path(alt).exists():
            p = Path(alt)
            break
    else:
        print("ERROR: no encontré home.html")
        raise SystemExit(1)

print(f"Modificando: {p}")
src = p.read_text(encoding="utf-8")

if "ORB_PUBNAV_V1" in src:
    print("SKIP: ya aplicado")
    raise SystemExit(0)

cambios = 0

# ══════════════════════════════════════════════════════════════
# 1. CSS — Insertar antes de la sección RESPONSIVE
# ══════════════════════════════════════════════════════════════
css_anchor = """/* ─────────────────────────────────────────────────
   RESPONSIVE
   ───────────────────────────────────────────────── */
@media (max-width: 1024px) {"""

css_nuevo = """/* ─────────────────────────────────────────────────
   ORB_PUBNAV_V1 — Explora páginas públicas
   ───────────────────────────────────────────────── */
.orb-pubnav { margin-bottom: 22px; }
.orb-pubnav__head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 14px; flex-wrap: wrap;
}
.orb-pubnav__title {
  font-family: 'Orbitron', sans-serif; font-weight: 800;
  font-size: 0.85rem; letter-spacing: 1.8px; text-transform: uppercase;
  color: var(--ink); display: flex; align-items: center; gap: 8px;
}
.orb-pubnav__title i { color: var(--violet-2); }
.orb-pubnav__hint {
  font-family: 'SF Mono', monospace; font-size: 0.68rem; font-weight: 700;
  color: var(--ink-mute); letter-spacing: 0.5px;
}
.orb-pubnav__grid {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px;
}
.orb-pubnav__card {
  position: relative; padding: 18px 16px; border-radius: 16px;
  text-decoration: none; color: var(--ink);
  display: flex; flex-direction: column; gap: 6px;
  min-height: 110px; transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
  overflow: hidden; border: 1px solid;
}
.orb-pubnav__card::after {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(circle at var(--mx, 50%) var(--my, 50%),
    rgba(255,255,255,0.5), transparent 60%);
  opacity: 0; pointer-events: none; transition: opacity 0.2s;
}
.orb-pubnav__card:hover { transform: translateY(-3px); }
.orb-pubnav__card:hover::after { opacity: 1; }
.orb-pubnav__card:focus-visible {
  outline: 3px solid var(--violet-2); outline-offset: 3px;
}
.orb-pubnav__icon { font-size: 1.6rem; margin-bottom: 4px; }
.orb-pubnav__label {
  font-family: 'Orbitron', sans-serif; font-weight: 800;
  font-size: 0.82rem; letter-spacing: 0.4px;
}
.orb-pubnav__sub {
  font-size: 0.7rem; color: var(--ink-mute); font-weight: 600;
}

.orb-pubnav__card--amber {
  background: linear-gradient(160deg, #fffbeb 0%, #ffffff 70%);
  border-color: rgba(251,191,36,0.35);
  box-shadow: 0 14px 30px -18px rgba(251,191,36,0.5);
}
.orb-pubnav__card--amber:hover {
  box-shadow: 0 20px 40px -18px rgba(251,191,36,0.65);
  border-color: rgba(251,191,36,0.65);
}
.orb-pubnav__card--sky {
  background: linear-gradient(160deg, #f0f9ff 0%, #ffffff 70%);
  border-color: rgba(56,189,248,0.35);
  box-shadow: 0 14px 30px -18px rgba(56,189,248,0.5);
}
.orb-pubnav__card--sky:hover {
  box-shadow: 0 20px 40px -18px rgba(56,189,248,0.65);
  border-color: rgba(56,189,248,0.65);
}
.orb-pubnav__card--coral {
  background: linear-gradient(160deg, #fff1f2 0%, #ffffff 70%);
  border-color: rgba(251,113,133,0.35);
  box-shadow: 0 14px 30px -18px rgba(251,113,133,0.5);
}
.orb-pubnav__card--coral:hover {
  box-shadow: 0 20px 40px -18px rgba(251,113,133,0.65);
  border-color: rgba(251,113,133,0.65);
}
.orb-pubnav__card--violet {
  background: linear-gradient(160deg, #f5f3ff 0%, #ffffff 70%);
  border-color: rgba(167,139,250,0.35);
  box-shadow: 0 14px 30px -18px rgba(167,139,250,0.5);
}
.orb-pubnav__card--violet:hover {
  box-shadow: 0 20px 40px -18px rgba(167,139,250,0.65);
  border-color: rgba(167,139,250,0.65);
}

/* ─────────────────────────────────────────────────
   RESPONSIVE
   ───────────────────────────────────────────────── */
@media (max-width: 1024px) {"""

if css_anchor not in src:
    print("WARN 1: no encontré el anchor de RESPONSIVE")
    print("  ¿el home.html es el que me pasaste?")
    raise SystemExit(1)

src = src.replace(css_anchor, css_nuevo, 1)
print("OK 1: CSS pubnav insertado")
cambios += 1

# ══════════════════════════════════════════════════════════════
# 2. CSS móvil extra — antes del cierre del <style>
# ══════════════════════════════════════════════════════════════
cierre_anchor = """.orb-btn, .orb-action, .orb-action__icon { transition: none; }
}
</style>
{% endblock %}"""

cierre_nuevo = """.orb-btn, .orb-action, .orb-action__icon { transition: none; }
}

/* ─────────────────────────────────────────────────
   ORB_PUBNAV_V1 — Responsive fino + móvil
   ───────────────────────────────────────────────── */
@media (max-width: 900px) {
  .orb-pubnav__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .orb { padding: 8px 0 32px; }
  .orb-nav { padding: 8px 12px; gap: 8px; margin-bottom: 14px; border-radius: 16px; }
  .orb-nav__name { font-size: 0.82rem; }
  .orb-nav__chip { font-size: 0.62rem; padding: 4px 8px; gap: 5px; }
  .orb-nav__mark { width: 26px; height: 26px; font-size: 0.8rem; }

  .orb-hero { gap: 12px; margin-bottom: 14px; }
  .orb-hero__left { padding: 22px 18px; border-radius: 18px; }
  .orb-hero__title { font-size: 1.55rem; margin-bottom: 10px; letter-spacing: -0.8px; }
  .orb-hero__sub { font-size: 0.85rem; margin-bottom: 16px; line-height: 1.5; }
  .orb-kicker { font-size: 0.62rem; padding: 4px 10px; margin-bottom: 14px; }

  .orb-count { padding: 18px 14px; border-radius: 18px; }
  .orb-count__orb { width: 158px; height: 158px; }
  .orb-count__core { width: 122px; height: 122px; }
  .orb-count__hh, .orb-count__mm, .orb-count__ss { font-size: 1.3rem; }
  .orb-count__sep { font-size: 1.3rem; }
  .orb-count__label { margin-bottom: 12px; font-size: 0.6rem; letter-spacing: 1.4px; }
  .orb-count__foot { margin-top: 14px; padding: 8px 12px; border-radius: 12px; }

  .orb-stats { gap: 8px; margin-bottom: 14px; }
  .orb-stat { padding: 14px 12px; border-radius: 14px; }
  .orb-stat__value { font-size: 1.35rem; letter-spacing: -0.6px; }
  .orb-stat__label { font-size: 0.56rem; letter-spacing: 1.1px; margin-bottom: 8px; gap: 5px; }
  .orb-stat__label i { font-size: 0.68rem; }

  .orb-stream { border-radius: 16px; margin-bottom: 14px; }
  .orb-stream__head { padding: 12px 14px; }
  .orb-stream__title { font-size: 0.7rem; letter-spacing: 1.2px; }
  .orb-stream__link { font-size: 0.6rem; }
  .orb-stream__body::before { left: 26px; }
  .orb-signal { padding: 10px 14px; gap: 10px; }
  .orb-signal__idx { font-size: 0.56rem; min-width: 26px; }
  .orb-signal__name { font-size: 0.78rem; }
  .orb-signal__date { font-size: 0.6rem; padding: 2px 7px; }
  .orb-signal__node { width: 14px; height: 14px; }

  .orb-actions { gap: 10px; margin-bottom: 14px; }
  .orb-action { padding: 16px; gap: 12px; border-radius: 16px; min-height: 90px; }
  .orb-action__icon { width: 46px; height: 46px; font-size: 1.25rem; }
  .orb-action__title { font-size: 0.9rem; margin-bottom: 2px; }
  .orb-action__sub { font-size: 0.7rem; }
  .orb-action__arrow { font-size: 1.1rem; }

  .orb-final { padding: 26px 18px; border-radius: 18px; }
  .orb-final__kicker { font-size: 0.6rem; }
  .orb-final__title { font-size: 1.35rem; letter-spacing: -0.6px; }
  .orb-final__sub { font-size: 0.82rem; margin-bottom: 16px; }

  .orb-pubnav__head { margin-bottom: 10px; }
  .orb-pubnav__title { font-size: 0.72rem; letter-spacing: 1.2px; }
  .orb-pubnav__hint { font-size: 0.6rem; }
  .orb-pubnav__grid { gap: 8px; }
  .orb-pubnav__card { padding: 12px 12px; min-height: 92px; border-radius: 14px; gap: 4px; }
  .orb-pubnav__icon { font-size: 1.35rem; margin-bottom: 2px; }
  .orb-pubnav__label { font-size: 0.72rem; letter-spacing: 0.2px; }
  .orb-pubnav__sub { font-size: 0.64rem; }
}

@media (max-width: 480px) {
  .orb-hero__title { font-size: 1.35rem; }
  .orb-count__orb { width: 140px; height: 140px; }
  .orb-count__core { width: 108px; height: 108px; }
  .orb-count__hh, .orb-count__mm, .orb-count__ss { font-size: 1.15rem; }
  .orb-count__sep { font-size: 1.15rem; }
  .orb-stat__value { font-size: 1.2rem; }
  .orb-stat { padding: 12px 10px; }
  .orb-stat__label { font-size: 0.52rem; letter-spacing: 0.9px; }
  .orb-pubnav__card { min-height: 86px; padding: 10px 10px; }
  .orb-pubnav__icon { font-size: 1.2rem; }
  .orb-pubnav__label { font-size: 0.68rem; }
  .orb-pubnav__sub { display: none; }
}

@media (max-width: 360px) {
  .orb-hero__title { font-size: 1.2rem; letter-spacing: -0.4px; }
  .orb-count__orb { width: 126px; height: 126px; }
  .orb-count__core { width: 96px; height: 96px; }
  .orb-count__hh, .orb-count__mm, .orb-count__ss { font-size: 1rem; }
  .orb-count__sep { font-size: 1rem; }
  .orb-stats { grid-template-columns: minmax(0, 1fr); }
  .orb-stat__value { font-size: 1.4rem; }
  .orb-btn { width: 100%; justify-content: center; padding: 12px 18px; font-size: 0.76rem; }
}

@media (orientation: landscape) and (max-height: 500px) {
  .orb { padding: 6px 0 20px; }
  .orb-nav { padding: 6px 12px; margin-bottom: 10px; }
  .orb-nav__chip { font-size: 0.6rem; padding: 3px 7px; }
  .orb-hero { gap: 10px; margin-bottom: 10px; }
  .orb-hero__left { padding: 16px 16px; }
  .orb-hero__title { font-size: 1.3rem; margin-bottom: 6px; }
  .orb-hero__sub { display: none; }
  .orb-hero__ctas { gap: 8px; }
  .orb-btn { padding: 10px 16px; min-height: 40px; font-size: 0.72rem; }
  .orb-count { padding: 12px 12px; }
  .orb-count__orb { width: 128px; height: 128px; }
  .orb-count__core { width: 98px; height: 98px; }
  .orb-count__hh, .orb-count__mm, .orb-count__ss { font-size: 1rem; }
  .orb-count__sep { font-size: 1rem; }
  .orb-count__label { margin-bottom: 8px; font-size: 0.56rem; }
  .orb-count__foot { margin-top: 10px; }
  .orb-stats { gap: 8px; margin-bottom: 10px; }
  .orb-stat { padding: 10px 10px; }
  .orb-stat__value { font-size: 1.15rem; }
  .orb-stat__label { margin-bottom: 6px; }
  .orb-stream { margin-bottom: 10px; }
  .orb-stream__body::before { top: 16px; bottom: 16px; }
  .orb-action { padding: 12px 14px; min-height: 74px; }
  .orb-action__icon { width: 40px; height: 40px; font-size: 1.1rem; }
  .orb-pubnav { margin-bottom: 12px; }
  .orb-pubnav__card { padding: 10px 12px; min-height: 74px; }
  .orb-final { padding: 22px 18px; }
  .orb-final__title { font-size: 1.25rem; }
  .orb-final__sub { margin-bottom: 14px; font-size: 0.8rem; }
}
</style>
{% endblock %}"""

if cierre_anchor not in src:
    print("WARN 2: no encontré el cierre del style")
    print("  buscando alternativa...")
    # Fallback: anclar en prefers-reduced-motion
    alt = """.orb-btn, .orb-action, .orb-action__icon { transition: none; }
}"""
    if alt in src:
        cierre_anchor = alt
        cierre_nuevo = cierre_nuevo.replace("</style>\n{% endblock %}", "")
        cierre_nuevo = cierre_nuevo.rstrip()
        src = src.replace(cierre_anchor, cierre_nuevo, 1)
        print("OK 2 (fallback): CSS móvil insertado")
        cambios += 1
    else:
        print("ERROR 2: no pude insertar CSS móvil")
        raise SystemExit(1)
else:
    src = src.replace(cierre_anchor, cierre_nuevo, 1)
    print("OK 2: CSS móvil insertado")
    cambios += 1

# ══════════════════════════════════════════════════════════════
# 3. HTML — Insertar sección Explora antes de FINAL CTA
# ══════════════════════════════════════════════════════════════
html_anchor = """  {# ═══════ FINAL CTA ═══════ #}"""

html_nuevo = """  {# ═══════ ORB_PUBNAV_V1 — Explora páginas públicas ═══════ #}
  <section class="orb-pubnav" aria-labelledby="orbPubnavTitle">
    <div class="orb-pubnav__head">
      <span class="orb-pubnav__title" id="orbPubnavTitle">
        <i class="fas fa-compass" aria-hidden="true"></i> Explora
      </span>
      <span class="orb-pubnav__hint">Sin iniciar sesión</span>
    </div>
    <div class="orb-pubnav__grid">
      <a href="{% url 'publico:charada' %}" class="orb-pubnav__card orb-pubnav__card--amber">
        <span class="orb-pubnav__icon" aria-hidden="true">🎴</span>
        <span class="orb-pubnav__label">La Charada</span>
        <span class="orb-pubnav__sub">Sueños y números</span>
      </a>
      <a href="{% url 'publico:faq' %}" class="orb-pubnav__card orb-pubnav__card--sky">
        <span class="orb-pubnav__icon" aria-hidden="true">❓</span>
        <span class="orb-pubnav__label">Preguntas</span>
        <span class="orb-pubnav__sub">Cómo funciona</span>
      </a>
      <a href="{% url 'publico:promociones' %}" class="orb-pubnav__card orb-pubnav__card--coral">
        <span class="orb-pubnav__icon" aria-hidden="true">🎁</span>
        <span class="orb-pubnav__label">Promociones</span>
        <span class="orb-pubnav__sub">Bonos y ofertas</span>
      </a>
      <a href="{% url 'publico:contacto' %}" class="orb-pubnav__card orb-pubnav__card--violet">
        <span class="orb-pubnav__icon" aria-hidden="true">📞</span>
        <span class="orb-pubnav__label">Contacto</span>
        <span class="orb-pubnav__sub">Estamos para ti</span>
      </a>
    </div>
  </section>

  {# ═══════ FINAL CTA ═══════ #}"""

if html_anchor not in src:
    print("ERROR 3: no encontré el anchor FINAL CTA")
    raise SystemExit(1)

src = src.replace(html_anchor, html_nuevo, 1)
print("OK 3: HTML pubnav insertado")
cambios += 1

# ══════════════════════════════════════════════════════════════
# 4. JS — Extender cursor glow a las nuevas cards
# ══════════════════════════════════════════════════════════════
js_anchor = """    document.querySelectorAll('.orb-action').forEach((card) => {
      card.addEventListener('mousemove', (e) => {"""

js_nuevo = """    document.querySelectorAll('.orb-action, .orb-pubnav__card').forEach((card) => {
      card.addEventListener('mousemove', (e) => {"""

if js_anchor in src:
    src = src.replace(js_anchor, js_nuevo, 1)
    print("OK 4: cursor glow extendido")
    cambios += 1
else:
    print("WARN 4: no encontré el cursor glow (skip)")

# Marcar como aplicado
src = src.replace("{% block extra_css %}", "{% block extra_css %}\n{# ORB_PUBNAV_V1 #}", 1)

p.write_text(src, encoding="utf-8")
print(f"\n✅ {cambios} cambio(s) aplicado(s) en {p.name}")

