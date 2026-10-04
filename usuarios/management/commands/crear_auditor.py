"""
Comando para crear un auditor asignado a un banco específico.

Uso:
    python manage.py crear_auditor --username=auditor_x --password=Pass123! --banco=Seider
    python manage.py crear_auditor --username=auditor_x --banco=3
    python manage.py crear_auditor --username=auditor_x --password=Pass123! --banco=Seider --email=correo@x.com
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction

from roles.models import Rol


class Command(BaseCommand):
    help = 'Crea un usuario auditor y lo asigna a un banco'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True,
                            help='Nombre de usuario del auditor')
        parser.add_argument('--password', type=str, default=None,
                            help='Contraseña (opcional — si no se pasa, el usuario no podrá entrar hasta que se le asigne una)')
        parser.add_argument('--email', type=str, default='',
                            help='Email del auditor (opcional)')
        parser.add_argument('--banco', type=str, required=True,
                            help='Username o ID del banco al que se asigna')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        banco_ref = options['banco']

        # 1. Resolver el banco
        banco = None
        if banco_ref.isdigit():
            banco = User.objects.filter(id=int(banco_ref)).first()
        else:
            banco = User.objects.filter(username=banco_ref).first()

        if not banco:
            raise CommandError(f'No se encontró el banco "{banco_ref}"')

        # Validar que sea banco
        if not banco.roles.filter(tipo='banco', activo=True).exists():
            raise CommandError(f'El usuario "{banco.username}" no tiene rol de banco activo')

        with transaction.atomic():
            # 2. Crear o recuperar el usuario
            auditor, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'is_active': True,
                }
            )

            if created:
                if password:
                    auditor.set_password(password)
                    auditor.save()
                self.stdout.write(self.style.SUCCESS(f'✅ Usuario creado: {username}'))
            else:
                self.stdout.write(self.style.WARNING(f'ℹ️  Usuario ya existía: {username}'))
                if password:
                    auditor.set_password(password)
                    auditor.save()
                    self.stdout.write(self.style.SUCCESS(f'   Contraseña actualizada'))

            # 3. Verificar que no tenga otro rol
            if auditor.roles.exists():
                roles_actuales = list(auditor.roles.values_list('tipo', flat=True))
                self.stdout.write(self.style.WARNING(
                    f'⚠️  El usuario ya tiene roles: {roles_actuales}'
                ))

            # 4. Crear o actualizar el rol de auditor
            rol, rol_created = Rol.objects.get_or_create(
                usuario=auditor,
                tipo='auditor',
                defaults={
                    'activo': True,
                    'banco_asignado': banco,
                }
            )

            if rol_created:
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Rol auditor creado para {username}'
                ))
            else:
                rol.activo = True
                rol.banco_asignado = banco
                rol.save()
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Rol auditor actualizado para {username}'
                ))

        # Resumen
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('═' * 50))
        self.stdout.write(self.style.SUCCESS('✅ Auditor configurado'))
        self.stdout.write(self.style.SUCCESS('═' * 50))
        self.stdout.write(f'  Username:  {auditor.username}')
        self.stdout.write(f'  Email:     {auditor.email or "(sin email)"}')
        self.stdout.write(f'  Banco:     {banco.username} (id={banco.id})')
        self.stdout.write(f'  Activo:    {auditor.is_active}')
        if password:
            self.stdout.write(f'  Password:  {password}')
        self.stdout.write('')
