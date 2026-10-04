from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count

from sorteos.models import Sorteo
from .models import VisitaDiaria


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
def _calcular_estadisticas():
    """
    Devuelve todas las estadísticas para el home.
    Tolera ausencia de modelos (Jugada) sin romper.
    """
    hoy = timezone.now().date()
    ahora = timezone.now()

    # ── Usuarios ──
    total_usuarios = User.objects.filter(is_active=True).count()

    # ── Visitas ──
    total_visitas = VisitaDiaria.objects.count()
    visitas_hoy = VisitaDiaria.objects.filter(fecha=hoy).count()

    # ── Sorteos ──
    try:
        total_sorteos = Sorteo.objects.filter(activo=True).count()
        # Sorteos pendientes = activos cuya hora de salida aún no pasó hoy
        # (ajustar el campo según tu modelo real)
        sorteos_pendientes = Sorteo.objects.filter(
            activo=True,
            hora_salida__gte=ahora
        ).count()
    except Exception:
        total_sorteos = 0
        sorteos_pendientes = 0

    # ── Apostadores y ventas del día (Jugada) ──
    apostadores_hoy = 0
    ventas_hoy = 0
    try:
        from jugadas.models import Jugada
        qs_hoy = Jugada.objects.filter(fecha__date=hoy)
        apostadores_hoy = qs_hoy.values('usuario').distinct().count()
        ventas_hoy = qs_hoy.aggregate(total=Sum('monto'))['total'] or 0
    except Exception:
        pass

    return {
        'total_usuarios':     total_usuarios,
        'total_visitas':      total_visitas,
        'visitas_hoy':        visitas_hoy,
        'total_sorteos':      total_sorteos,
        'sorteos_pendientes': sorteos_pendientes,
        'apostadores_hoy':    apostadores_hoy,
        'ventas_hoy':         float(ventas_hoy),
        'actualizado':        ahora.isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
#  HOME
# ═══════════════════════════════════════════════════════════════
def home(request):
    """
    Página principal de LottoBooM.
    """
    stats = _calcular_estadisticas()

    context = {
        'fecha_actual': timezone.now(),
        'user_authenticated': request.user.is_authenticated,
        **stats,
    }

    if request.user.is_authenticated:
        context['mensaje'] = f'🎉 ¡Bienvenido, {request.user.username}!'
        context['sorteos_activos'] = Sorteo.objects.filter(
            activo=True
        ).order_by('-creado_en')[:5]
    else:
        context['titulo'] = '🎰 LottoBooM'
        context['subtitulo'] = 'La mejor plataforma de lotería. Regístrate y empieza a ganar.'

    return render(request, 'publico/home.html', context)


# ═══════════════════════════════════════════════════════════════
#  API — Estadísticas en tiempo real
# ═══════════════════════════════════════════════════════════════
@login_required
def api_estadisticas(request):
    """Devuelve las estadísticas en JSON para refrescar sin recargar."""
    return JsonResponse(_calcular_estadisticas())


# ═══════════════════════════════════════════════════════════════
#  VISTAS SIMPLES
# ═══════════════════════════════════════════════════════════════
def faq_view(request):
    faqs = [
        {'pregunta': '¿Cómo puedo apostar?', 'respuesta': 'Regístrate, recarga fondos y selecciona tus números.'},
        {'pregunta': '¿Cuándo se realizan los sorteos?', 'respuesta': 'Consulta los horarios en la sección de sorteos.'},
        {'pregunta': '¿Cómo puedo retirar mis ganancias?', 'respuesta': 'Solicita un retiro desde tu panel de usuario.'},
        {'pregunta': '¿Qué es el bono de bienvenida?', 'respuesta': 'Es un bono de $50 que recibes al registrarte.'},
    ]
    return render(request, 'publico/faq.html', {'faqs': faqs})


def contacto_view(request):
    if request.method == 'POST':
        messages.success(request, "✅ Tu mensaje ha sido enviado. Te responderemos pronto.")
        return redirect('publico:contacto')
    return render(request, 'publico/contacto.html')


def promociones_view(request):
    promociones = [
        {'titulo': '🎁 Bono de bienvenida', 'descripcion': '50% de bonificación en tu primera recarga.'},
        {'titulo': '🏆 Sorteo especial', 'descripcion': 'Participa en nuestro sorteo mensual.'},
        {'titulo': '💰 Cashback semanal', 'descripcion': 'Recibe el 5% de tus pérdidas cada semana.'},
    ]
    return render(request, 'publico/promociones.html', {'promociones': promociones})


# ═══════════════════════════════════════════════════════════════
# LA CHARADA
# ═══════════════════════════════════════════════════════════════

from functools import lru_cache
import re as _re_charada


@lru_cache(maxsize=1)
def _parse_charada():
    """Parsea charada_source.txt y devuelve dict {num: {'principales': [], 'todas': []}}"""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta = os.path.join(base, 'publico', 'data', 'charada_source.txt')
    if not os.path.exists(ruta):
        return {}

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Split por bloques: cada bloque empieza con N: al inicio de línea
    bloques = _re_charada.split(r'^\s*(\d+)\s*:\s*$', contenido, flags=_re_charada.MULTILINE)

    charada = {}
    # bloques[0] = preámbulo, bloques[1] = número, bloques[2] = contenido, etc.
    for i in range(1, len(bloques), 2):
        try:
            num = int(bloques[i])
        except (ValueError, IndexError):
            continue
        cuerpo = bloques[i + 1] if i + 1 < len(bloques) else ''

        # Extraer Principales y Todas
        principales = []
        todas = []

        # Buscar secciones
        m_ppal = _re_charada.search(r'Principales?:\s*(.*?)(?=Todas?:|$)', cuerpo, _re_charada.DOTALL | _re_charada.IGNORECASE)
        m_todas = _re_charada.search(r'Todas?:\s*(.*?)$', cuerpo, _re_charada.DOTALL | _re_charada.IGNORECASE)

        def parse_items(texto):
            if not texto:
                return []
            # Limpiar
            texto = texto.strip()
            # Split por coma o salto
            items = _re_charada.split(r'[,;\n]+', texto)
            return [it.strip() for it in items if it.strip()]

        if m_ppal:
            principales = parse_items(m_ppal.group(1))
        if m_todas:
            todas = parse_items(m_todas.group(1))

        charada[num] = {
            'principales': principales,
            'todas': todas,
        }

    return charada


def charada_view(request):
    """Vista pública: La Charada."""
    charada = _parse_charada()

    # Emoji por número (según primer principal)
    # Mapping explícito por número (0-99)
    EMOJIS = {
        0: '🚗', 1: '🐴', 2: '🦋', 3: '👶', 4: '🕯️', 5: '🌊',
        6: '🐢', 7: '💩', 8: '💀', 9: '🐘', 10: '🐟',
        11: '🐓', 12: '🐕', 13: '🐘', 14: '🐈', 15: '🐀',
        16: '🐝', 17: '🌙', 18: '🐱', 19: '🚩', 20: '📖',
        21: '💰', 22: '⭐', 23: '🦅', 24: '🕊️', 25: '🏠',
        26: '👨‍⚕️', 27: '🐒', 28: '🐐', 29: '🦌', 30: '🦀',
        31: '🦆', 32: '😈', 33: '✝️', 34: '🐵', 35: '🕷️',
        36: '🐦', 37: '🧙', 38: '🚗', 39: '🐰', 40: '🧑‍🚒',
        41: '🦎', 42: '🐏', 43: '🦂', 44: '⛈️', 45: '🦈',
        46: '🚌', 47: '🌹', 48: '🪳', 49: '👻', 50: '💧',
        51: '👓', 52: '🚲', 53: '💎', 54: '💐', 55: '🦇',
        56: '👑', 57: '👼', 58: '🔪', 59: '💍', 60: '🤡',
        61: '🍚', 62: '❄️', 63: '🗡️', 64: '🥭', 65: '🐇',
        66: '💋', 67: '🏥', 68: '🎳', 69: '🎹', 70: '🌈',
        71: '🐆', 72: '🐂', 73: '♟️', 74: '🪁', 75: '🎸',
        76: '🎻', 77: '🏫', 78: '👑', 79: '🚂', 80: '🌕',
        81: '🎭', 82: '🦁', 83: '🦯', 84: '💼', 85: '🪞',
        86: '🐿️', 87: '🕊️', 88: '🥃', 89: '🎰', 90: '🍬',
        91: '🚋', 92: '🛩️', 93: '💎', 94: '🌺', 95: '🦂',
        96: '👞', 97: '🦗', 98: '💋', 99: '🐓',
    }

    def emoji_para(num, principales=None):
        return EMOJIS.get(num, '🔮')
        primero = principales[0].lower()
        for kw, emoji in EMOJIS_KEYWORDS:
            if kw in primero:
                return emoji
        return '🔮'

    # Paleta zodiacal (10 colores base que rotan)
    PALETA = [
        ('#ef4444', '#fee2e2'),  # rojo
        ('#f97316', '#ffedd5'),  # naranja
        ('#eab308', '#fef9c3'),  # amarillo
        ('#22c55e', '#dcfce7'),  # verde
        ('#06b6d4', '#cffafe'),  # cyan
        ('#3b82f6', '#dbeafe'),  # azul
        ('#8b5cf6', '#ede9fe'),  # violeta
        ('#ec4899', '#fce7f3'),  # rosa
        ('#14b8a6', '#ccfbf1'),  # teal
        ('#a16207', '#fef3c7'),  # dorado
    ]

    # Enriquecer cada entrada
    entradas = []
    for num in sorted(charada.keys()):
        data = charada[num]
        color_fuerte, color_suave = PALETA[num % 10]
        entradas.append({
            'numero': num,
            'principales': data['principales'],
            'todas': data['todas'],
            'emoji': emoji_para(num, data['principales']),
            'color': color_fuerte,
            'color_suave': color_suave,
            'total_items': len(data['principales']) + len(data['todas']),
        })

    context = {
        'entradas': entradas,
        'total_numeros': len(entradas),
    }
    return render(request, 'publico/charada.html', context)

