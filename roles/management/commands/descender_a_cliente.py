# -*- coding: utf-8 -*-
"""
Descender usuarios a rol cliente.

Uso:
    python manage.py descender_a_cliente Seider Shadows1
    python manage.py descender_a_cliente Seider --dry-run
    python manage.py descender_a_cliente Seider --yes     # sin confirmación

Soporta descender desde: superadmin, banco, comercial, auditor.
Aplica la misma lógica que roles.views.ascender_usuario (rama cliente).
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from roles.models import (
    Rol, Subordinacion, RecursoAsignado, LimiteApuesta, DosisPago,
    SuscripcionBanco, Fondo, Bono, Notificacion,
)


class Command(BaseCommand):
    help = 'Descender usuarios a cliente'

    def add_arguments(self, parser):
        parser.add_argument('usernames', nargs='+', type=str)
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostrar qué haría sin modificar nada')
        parser.add_argument('--yes', action='store_true',
                            help='No pedir confirmación')

    # ─────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        usernames = options['usernames']
        dry = options['dry_run']
        skip_confirm = options['yes']

        # ─── Validar usuarios ───
        users = []
        for un in usernames:
            try:
                u = User.objects.get(username=un)
                users.append(u)
            except User.DoesNotExist:
                self.stderr.write(f'  ❌ Usuario no encontrado: {un}')
                return

        # ─── Mostrar estado actual ───
        self.stdout.write('═' * 62)
        self.stdout.write('  Descender a cliente')
        self.stdout.write('═' * 62)
        self.stdout.write('')
        for u in users:
            rol_activo = u.roles.filter(activo=True).exclude(tipo='cliente').first()
            if rol_activo:
                tipo = rol_activo.tipo
            else:
                rol_cliente = u.roles.filter(tipo='cliente', activo=True).first()
                tipo = 'cliente' if rol_cliente else '— sin rol —'
            self.stdout.write(f'  {u.username:<20} · rol actual: {tipo}')
        self.stdout.write('')

        # ─── ¿Alguno ya es cliente? ───
        todos_ya_clientes = all(
            u.roles.filter(tipo='cliente', activo=True).exists() and
            not u.roles.filter(activo=True).exclude(tipo='cliente').exists()
            for u in users
        )
        if todos_ya_clientes:
            self.stdout.write('  ⏩ Todos ya son cliente. Nada que hacer.')
            return

        if dry:
            self.stdout.write('[DRY-RUN] Nada se modificó.')
            return

        if not skip_confirm:
            self.stdout.write('⚠️  ¿Ejecutar de verdad? Escribe "si" para confirmar: ', ending='')
            self.stdout.flush()
            resp = input().strip().lower()
            if resp != 'si':
                self.stdout.write('❌ Cancelado.')
                return

        # ─── Aplicar ───
        self.stdout.write('')
        self.stdout.write('═══ Aplicando descensos ═══')
        for u in users:
            self._descender(u)

    # ─────────────────────────────────────────────────────────
    def _descender(self, u):
        from roles.views import (
            ajustar_fondos_al_descender,
            reasignar_comerciales_al_descender_banco,
            anular_bonos_usuario,
        )

        with transaction.atomic():
            rol_actual = u.roles.filter(activo=True).exclude(tipo='cliente').first()
            if not rol_actual:
                self.stdout.write(f'  ⏩ {u.username} ya es cliente')
                return

            tipo_actual = rol_actual.tipo
            self.stdout.write(f'  🔄 {u.username}: {tipo_actual} → cliente')

            # ── Si es BANCO: propagar a sus comerciales + limpiar suscripción ──
            if tipo_actual == 'banco':
                try:
                    reasignar_comerciales_al_descender_banco(u)
                    self.stdout.write(f'     ↳ comerciales reasignados')
                except Exception as e:
                    self.stdout.write(f'     ⚠️  error reasignando comerciales: {e}')

                n_sus = SuscripcionBanco.objects.filter(banco=u).delete()[0]
                n_rec = RecursoAsignado.objects.filter(banco=u).delete()[0]
                self.stdout.write(f'     ↳ suscripción eliminada ({n_sus}) · recursos ({n_rec})')

            # ── Si es COMERCIAL: liberar del banco + limpiar recursos ──
            elif tipo_actual == 'comercial':
                Subordinacion.objects.filter(subordinado=u, activo=True).delete()
                Rol.objects.filter(usuario=u, tipo='comercial', activo=True).update(banco_asignado=None)
                n_rec = RecursoAsignado.objects.filter(comercial=u).delete()[0]
                n_lim = LimiteApuesta.objects.filter(comercial=u).delete()[0]
                n_dos = DosisPago.objects.filter(comercial=u).delete()[0]
                self.stdout.write(f'     ↳ recursos ({n_rec}) · límites ({n_lim}) · dosis ({n_dos})')

            # ── Desactivar todos los roles actuales excepto cliente ──
            n_roles_off = Rol.objects.filter(usuario=u, activo=True).exclude(tipo='cliente').update(activo=False)

            # ── Crear/activar rol cliente ──
            rol_cliente, created = Rol.objects.update_or_create(
                usuario=u,
                tipo='cliente',
                defaults={'activo': True, 'fondo': 0, 'banco_asignado': None},
            )

            # ── Fondos a negativos ──
            fondos = Fondo.objects.filter(usuario=u, activo=True)
            n_fondos = 0
            for f in fondos:
                if f.monto > 0:
                    f.monto = -f.monto
                    f.save(update_fields=['monto'])
                    n_fondos += 1

            # ── Anular bonos ──
            try:
                anular_bonos_usuario(u)
                n_bonos = Bono.objects.filter(usuario=u, estado='activo').count()
            except Exception:
                n_bonos = 0

            # ── Notificación ──
            try:
                Notificacion.objects.create(
                    usuario=u,
                    tipo='info',
                    mensaje=(
                        '⚠️ Has sido descendido a Cliente. '
                        'Tus fondos son modulares (negativos) y se anularán con recargas.'
                    ),
                    datos={
                        'tipo_cambio': 'descenso_cliente',
                        'fecha': timezone.now().isoformat(),
                        'origen': 'script_cli',
                        'rol_anterior': tipo_actual,
                    },
                    leido=False,
                    prioridad='alta',
                    categoria='sistema',
                )
            except Exception:
                pass

            self.stdout.write(
                f'     ✅ hecho · roles_off={n_roles_off} · '
                f'fondos_negados={n_fondos} · bonos_anulados={n_bonos} · '
                f'cliente_creado={"sí" if created else "reutilizado"}'
            )
