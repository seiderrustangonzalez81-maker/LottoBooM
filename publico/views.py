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
    # FIX_TZ_CONTADORES_V1: usar fecha local (Cuba), no UTC
    hoy = timezone.localdate()
    ahora = timezone.now()

    # ── Usuarios ──
    total_usuarios = User.objects.filter(is_active=True).count()

    # ── Visitas ──
    total_visitas = VisitaDiaria.objects.count()
    visitas_hoy = VisitaDiaria.objects.filter(fecha=hoy).count()

    # ── Sorteos ──
    # FIX_SORTEOS_PENDIENTES_V1: usar get_hora_salida (respeta horarios JSON)
    try:
        total_sorteos = Sorteo.objects.filter(activo=True).count()
        from sorteos.utils import get_hora_salida
        hora_actual = timezone.localtime(ahora).time()
        sorteos_pendientes = 0
        for s in Sorteo.objects.filter(activo=True):
            try:
                hs = get_hora_salida(s, hoy)
                if hs and hs > hora_actual:
                    sorteos_pendientes += 1
            except Exception:
                pass
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

    return render(request, 'publico/home_v2.html', context)


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



# ═══════════════════════════════════════════════════════════════
#  HOME V3 — Broadcast Live
# ═══════════════════════════════════════════════════════════════
def home_v3(request):
    """
    Home alternativo (BROADCAST // LIVE).
    Diseño en tiempo real, adaptativo por rol, con datos reales.
    """
    from django.db.models import Sum, Count
    from sorteos.utils import get_sorteos_hoy

    stats = _calcular_estadisticas()
    ahora = timezone.now()
    hoy = timezone.localdate()

    # ── Sorteos del día (con estado calculado) ──
    try:
        sorteos_hoy, _totales = get_sorteos_hoy(hoy)
    except Exception:
        sorteos_hoy = []

    # Próximo sorteo (el abierto más cercano a cerrar)
    proximo_sorteo = None
    for s in sorteos_hoy:
        if getattr(s, 'estado_actual', None) == 'abierto':
            proximo_sorteo = s
            break

    # ── Últimos resultados reales ──
    ultimos_resultados = []
    try:
        from resultados.models import Resultado
        ultimos_resultados = list(
            Resultado.objects
            .select_related('sorteo')
            .order_by('-fecha', '-hora')[:8]
        )
    except Exception:
        pass

    # ── Live feed real (premios recientes) ──
    premios_recientes = []
    try:
        from resultados.models import Premio
        premios_recientes = list(
            Premio.objects
            .select_related('jugada__usuario', 'jugada__sorteo')
            .order_by('-creado_en')[:12]
        )
    except Exception:
        pass

    # ── Top ganadores de hoy ──
    top_ganadores_hoy = []
    try:
        from resultados.models import Premio
        top_ganadores_hoy = list(
            Premio.objects
            .filter(creado_en__date=hoy)
            .values('jugada__usuario__username')
            .annotate(total=Sum('monto_premio'), count=Count('id'))
            .order_by('-total')[:5]
        )
    except Exception:
        pass

    # ── Saldos del usuario (solo logueado) ──
    saldos_usuario = None
    if request.user.is_authenticated:
        try:
            from roles.models import Fondo, Bono, Postpago
            fondos = Fondo.objects.filter(
                usuario=request.user, activo=True
            ).aggregate(t=Sum('monto'))['t'] or 0
            bonos = Bono.objects.filter(
                usuario=request.user, estado='activo'
            ).aggregate(t=Sum('saldo_restante'))['t'] or 0
            pp = Postpago.objects.filter(
                cliente=request.user, activo=True, saldo__lt=0
            ).aggregate(t=Sum('saldo'))['t'] or 0
            saldos_usuario = {
                'fondos': float(fondos),
                'bonos': float(bonos),
                'postpago': float(abs(pp)),
                'total': float(fondos + bonos),
            }
        except Exception:
            pass

    # ── Rol del usuario (para CTAs adaptativos) ──
    rol_actual = 'visitante'
    if request.user.is_authenticated:
        if request.user.is_superuser:
            rol_actual = 'superadmin'
        else:
            r = request.user.roles.filter(activo=True).first()
            rol_actual = r.tipo if r else 'cliente'

    context = {
        'fecha_actual': ahora,
        'user_authenticated': request.user.is_authenticated,
        'rol_actual': rol_actual,
        **stats,
        'sorteos_hoy': sorteos_hoy[:12],
        'proximo_sorteo': proximo_sorteo,
        'ultimos_resultados': ultimos_resultados,
        'premios_recientes': premios_recientes,
        'top_ganadores_hoy': top_ganadores_hoy,
        'saldos_usuario': saldos_usuario,
    }
    return render(request, 'publico/home_v2.html', context)


# ═══════════════════════════════════════════════════════════════
#  HOME V3 — Broadcast Live (Light-first, Studio palette)
# ═══════════════════════════════════════════════════════════════
def home_v3(request):
    from django.db.models import Sum, Count
    from sorteos.utils import get_sorteos_hoy

    stats = _calcular_estadisticas()
    ahora = timezone.now()
    hoy = timezone.localdate()

    # Sorteos del día
    try:
        sorteos_hoy, _ = get_sorteos_hoy(hoy)
    except Exception:
        sorteos_hoy = []

    proximo_sorteo = None
    for s in sorteos_hoy:
        if getattr(s, 'estado_actual', None) == 'abierto':
            proximo_sorteo = s
            break

    # Últimos resultados
    ultimos_resultados = []
    try:
        from resultados.models import Resultado
        ultimos_resultados = list(
            Resultado.objects.select_related('sorteo').order_by('-fecha', '-hora')[:8]
        )
    except Exception:
        pass

    # Premios recientes (live feed real)
    premios_recientes = []
    try:
        from resultados.models import Premio
        premios_recientes = list(
            Premio.objects.select_related('jugada__usuario', 'jugada__sorteo').order_by('-creado_en')[:12]
        )
    except Exception:
        pass

    # Saldos del usuario
    saldos_usuario = None
    if request.user.is_authenticated:
        try:
            from roles.models import Fondo, Bono, Postpago
            fondos = Fondo.objects.filter(usuario=request.user, activo=True).aggregate(t=Sum('monto'))['t'] or 0
            bonos = Bono.objects.filter(usuario=request.user, estado='activo').aggregate(t=Sum('saldo_restante'))['t'] or 0
            pp = Postpago.objects.filter(cliente=request.user, activo=True, saldo__lt=0).aggregate(t=Sum('saldo'))['t'] or 0
            saldos_usuario = {
                'fondos': float(fondos), 'bonos': float(bonos),
                'postpago': float(abs(pp)), 'total': float(fondos + bonos),
            }
        except Exception:
            pass

    context = {
        'fecha_actual': ahora,
        'user_authenticated': request.user.is_authenticated,
        **stats,
        'sorteos_hoy': sorteos_hoy[:12],
        'proximo_sorteo': proximo_sorteo,
        'ultimos_resultados': ultimos_resultados,
        'premios_recientes': premios_recientes,
        'saldos_usuario': saldos_usuario,
    }
    return render(request, 'publico/home_v2.html', context)

# ═══════════════════════════════════════════════════════════════
#  SITE VERSION — para auto-recarga de clientes autenticados
# ═══════════════════════════════════════════════════════════════
def site_version(request):
    """
    Devuelve la versión actual del sitio. Los clientes autenticados
    pollan este endpoint y, si la versión cambia, recargan la página.
    """
    from pathlib import Path
    from django.conf import settings
    from django.http import JsonResponse

    v_file = Path(settings.BASE_DIR) / 'LottoBooM' / 'site_version.txt'
    try:
        v = v_file.read_text().strip() or '0'
    except Exception:
        v = '0'
    return JsonResponse({'version': v})
