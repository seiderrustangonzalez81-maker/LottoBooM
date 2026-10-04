# usuarios/admin.py
# -*- coding: utf-8 -*-
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Sum
from decimal import Decimal

from usuarios.models import Perfil
from roles.models import Fondo, Bono
from jugadas.models import Boleta


# ══════════════════════════════════════════════════════════════
# ACCIONES MASIVAS
# ══════════════════════════════════════════════════════════════

@admin.action(description="🚫 Desactivar usuarios (soft delete)")
def desactivar_usuarios(modeladmin, request, queryset):
    total = queryset.update(is_active=False)
    messages.success(
        request,
        f"✅ {total} usuario(s) desactivado(s). No podrán iniciar sesión, "
        f"pero su historial queda intacto."
    )


@admin.action(description="✅ Reactivar usuarios")
def reactivar_usuarios(modeladmin, request, queryset):
    total = queryset.update(is_active=True)
    messages.success(request, f"✅ {total} usuario(s) reactivado(s).")


@admin.action(description="🔒 Resetear contraseña a temporal (LottoBooM2026!)")
def resetear_password_temporal(modeladmin, request, queryset):
    TEMPORAL = 'LottoBooM2026!'
    for u in queryset:
        u.set_password(TEMPORAL)
        u.save()
    messages.success(
        request,
        f"🔒 {queryset.count()} usuario(s) con contraseña temporal: {TEMPORAL}"
    )


@admin.action(description="💵 Ver saldo consolidado")
def ver_saldo_consolidado(modeladmin, request, queryset):
    lineas = []
    for u in queryset:
        fondos = Fondo.objects.filter(usuario=u, activo=True).aggregate(t=Sum('monto'))['t'] or Decimal('0.00')
        bonos = sum(b.saldo_restante for b in Bono.objects.filter(usuario=u, estado='activo'))
        boletas = Boleta.objects.filter(usuario=u).count()
        lineas.append(f"{u.username}: ${fondos + bonos:.2f} ({boletas} boletas)")
    messages.info(request, " | ".join(lineas[:10]))


# ══════════════════════════════════════════════════════════════
# INLINE DE PERFIL (fk_name='usuario' por las 2 FKs a User)
# ══════════════════════════════════════════════════════════════

class PerfilInline(admin.StackedInline):
    model = Perfil
    fk_name = 'usuario'   # ← CRÍTICO: hay 2 FKs a User, hay que decir cuál
    can_delete = False
    extra = 0
    fields = ('telefono', 'direccion', 'fecha_nacimiento', 'codigo_referido', 'activo')
    readonly_fields = ('codigo_referido',)
    verbose_name = 'Perfil'
    verbose_name_plural = 'Perfil'


# ══════════════════════════════════════════════════════════════
# USER ADMIN
# ══════════════════════════════════════════════════════════════

class UserAdmin(DjangoUserAdmin):
    inlines = (PerfilInline,)
    list_display = (
        'username', 'email', 'is_active', 'is_staff',
        'rol_badge', 'saldo_display', 'last_login_short', 'date_joined_short'
    )
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'roles__tipo', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'perfil__telefono')
    ordering = ('-date_joined',)
    list_per_page = 50
    actions = (
        desactivar_usuarios,
        reactivar_usuarios,
        resetear_password_temporal,
        ver_saldo_consolidado,
    )
    readonly_fields = ('last_login', 'date_joined', 'saldo_total_display', 'boletas_count')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Datos personales', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas importantes', {'fields': ('last_login', 'date_joined')}),
        ('Resumen de cuenta', {'fields': ('saldo_total_display', 'boletas_count')}),
    )

    def has_delete_permission(self, request, obj=None):
        return False   # Bloquear borrado duro

    def rol_badge(self, obj):
        if obj.is_superuser:
            return format_html('<span style="background:#7c3aed;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">SUPERADMIN</span>')
        rol = obj.roles.filter(activo=True).first()
        if not rol:
            return '—'
        colores = {
            'superadmin': '#7c3aed',
            'banco': '#0891b2',
            'comercial': '#d97706',
            'cliente': '#059669',
        }
        color = colores.get(rol.tipo, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;text-transform:uppercase;">{}</span>',
            color, rol.tipo
        )
    rol_badge.short_description = 'Rol'

    def saldo_display(self, obj):
        # FIX_SAFE_DISPLAY_V2: mark_safe sin format_html (inmune a SafeString)
        try:
            fondos_raw = Fondo.objects.filter(usuario=obj, activo=True).aggregate(t=Sum('monto'))['t']
            bonos_raw = sum(b.saldo_restante for b in Bono.objects.filter(usuario=obj, estado='activo'))
            total = float(str(fondos_raw or 0).replace('$', '').replace(',', '')) + \
                    float(str(bonos_raw or 0).replace('$', '').replace(',', ''))
        except Exception:
            total = 0.0
        color = '#059669' if total > 0 else '#6b7280'
        monto_str = f'{total:.2f}'
        return mark_safe(f'<strong style="color:{color}">${monto_str}</strong>')
    saldo_display.short_description = 'Saldo'

    def last_login_short(self, obj):
        if not obj.last_login:
            return '—'
        return obj.last_login.strftime('%d/%m %H:%M')
    last_login_short.short_description = 'Último login'

    def date_joined_short(self, obj):
        return obj.date_joined.strftime('%d/%m/%Y')
    date_joined_short.short_description = 'Registro'

    def saldo_total_display(self, obj):
        # FIX_SAFE_TOTAL_V2: conversión explícita, sin f-string sobre SafeString
        if not obj.pk:
            return '—'
        try:
            fondos_raw = Fondo.objects.filter(usuario=obj, activo=True).aggregate(t=Sum('monto'))['t']
            bonos_raw = sum(b.saldo_restante for b in Bono.objects.filter(usuario=obj, estado='activo'))
            f_val = float(str(fondos_raw or 0).replace('$', '').replace(',', ''))
            b_val = float(str(bonos_raw or 0).replace('$', '').replace(',', ''))
        except Exception:
            f_val, b_val = 0.0, 0.0
        total = f_val + b_val
        return f'${f_val:.2f} fondos + ${b_val:.2f} bonos = ${total:.2f}'
    saldo_total_display.short_description = 'Saldo consolidado'

    def boletas_count(self, obj):
        if not obj.pk:
            return '—'
        count = Boleta.objects.filter(usuario=obj).count()
        url = reverse('admin:jugadas_boleta_changelist') + f'?usuario__id__exact={obj.pk}'
        return format_html('<a href="{}">{} boletas</a>', url, count)
    boletas_count.short_description = 'Boletas'


# ══════════════════════════════════════════════════════════════
# PERFIL ADMIN
# ══════════════════════════════════════════════════════════════

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'telefono', 'codigo_referido', 'activo', 'creado_en')
    list_filter = ('activo', 'creado_en')
    search_fields = ('usuario__username', 'usuario__email', 'telefono', 'codigo_referido')
    raw_id_fields = ('usuario', 'referido_por')
    readonly_fields = ('codigo_referido', 'creado_en', 'actualizado_en')
    list_per_page = 50


# ══════════════════════════════════════════════════════════════
# REGISTRAR USER ADMIN
# ══════════════════════════════════════════════════════════════

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, UserAdmin)

# ═══════════════════════════════════════════════════════════════════════
# ACCIONES PARA AUDITORES
# ═══════════════════════════════════════════════════════════════════════

@admin.action(description="🔍 Convertir en auditor (requiere elegir banco)")
def convertir_en_auditor(modeladmin, request, queryset):
    """
    Convierte los usuarios seleccionados en auditores.
    Requiere que el usuario ya tenga asignado un banco vía Subordinación
    o que se le asigne manualmente después desde Roles.
    """
    from roles.models import Rol, Subordinacion

    creados = 0
    ya_auditores = 0
    sin_banco = 0

    for user in queryset:
        # Verificar si ya es auditor
        if Rol.objects.filter(usuario=user, tipo='auditor', activo=True).exists():
            ya_auditores += 1
            continue

        # Buscar un banco al que asignarlo
        banco = None

        # Opción 1: ¿es subordinado de un banco?
        sub = Subordinacion.objects.filter(subordinado=user, activo=True).first()
        if sub and sub.jefe.roles.filter(tipo='banco', activo=True).exists():
            banco = sub.jefe

        # Opción 2: ¿tiene un rol de banco_asignado?
        if not banco:
            rol_banco = user.roles.filter(banco_asignado__isnull=False).first()
            if rol_banco:
                banco = rol_banco.banco_asignado

        if not banco:
            sin_banco += 1
            continue

        Rol.objects.get_or_create(
            usuario=user,
            tipo='auditor',
            defaults={'activo': True, 'banco_asignado': banco}
        )
        creados += 1

    # Mensaje
    msg = f"✅ {creados} auditor(es) creado(s)."
    if ya_auditores:
        msg += f" {ya_auditores} ya eran auditores."
    if sin_banco:
        msg += f" ⚠️ {sin_banco} sin banco asignado (no convertidos)."

    if creados > 0:
        messages.success(request, msg)
    elif sin_banco > 0:
        messages.warning(request, msg)
    else:
        messages.info(request, msg)


# Registrar la acción en el UserAdmin
if hasattr(admin.site._registry.get(User), 'actions'):
    UserAdminClass = type(admin.site._registry[User])
    # Añadir a la lista existente
    admin.site._registry[User].actions = tuple(
        list(admin.site._registry[User].actions or []) + [convertir_en_auditor]
    )
