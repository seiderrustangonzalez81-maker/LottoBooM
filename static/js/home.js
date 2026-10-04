document.addEventListener('DOMContentLoaded', function () {
  const messages = [
    "🎁 Bono de bienvenida: regístrate y recibe crédito para tu primera jugada.",
    "🏆 Sorteos semanales con premios acumulados: participa ahora.",
    "🔒 Pagos seguros y soporte 24/7 para jugar con tranquilidad.",
    "🎯 Jugadas rápidas desde tu móvil: apuesta en segundos.",
    "📣 Invita amigos y gana recompensas con nuestro programa de referidos."
  ];
  const inner = document.getElementById('promo-inner');
  const pauseBtn = document.getElementById('promo-pause');
  if (!inner) return;
  let idx = 0;
  let running = true;
  function showNext() {
    inner.style.opacity = 0;
    setTimeout(() => {
      inner.textContent = messages[idx];
      inner.style.opacity = 1;
      idx = (idx + 1) % messages.length;
    }, 300);
  }
  showNext();
  const interval = setInterval(() => { if (running) showNext(); }, 4200);
  if (pauseBtn) {
    pauseBtn.addEventListener('click', () => {
      running = !running;
      pauseBtn.textContent = running ? 'Pausar' : 'Reanudar';
      pauseBtn.setAttribute('aria-pressed', String(!running));
    });
  }

  // Gentle parallax for cards (performance-friendly)
  const cards = document.querySelectorAll('.card');
  let lastX = 0, lastY = 0;
  document.addEventListener('mousemove', (e) => {
    const x = (e.clientX / window.innerWidth) - 0.5;
    const y = (e.clientY / window.innerHeight) - 0.5;
    if (Math.abs(x - lastX) < 0.01 && Math.abs(y - lastY) < 0.01) return;
    lastX = x; lastY = y;
    cards.forEach((c, i) => {
      const depth = (i % 6) * 0.4 + 0.6;
      c.style.transform = `translate3d(${x * depth}px, ${y * depth}px, 0)`;
    });
  });

  // Respect prefers-reduced-motion
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce) {
    document.querySelectorAll('.rainbow-bg, .rainbow-overlay').forEach(el => el.style.animation = 'none');
    clearInterval(interval);
  }
});
