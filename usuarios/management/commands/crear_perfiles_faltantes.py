from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from usuarios.models import Rol

User = get_user_model()

ROLES_OFICIALES = [
    "cliente",
    "comercial",
    "banco",
    "superadmin",
    "auditor",
]

class Command(BaseCommand):
    help = "Asigna roles oficiales a los usuarios según parámetros o reglas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--usuario",
            type=str,
            help="Username del usuario al que se le asignarán los roles."
        )
        parser.add_argument(
            "--rol",
            type=str,
            help="Rol específico a asignar (cliente, comercial, banco, superadmin, auditor)."
        )

    def handle(self, *args, **kwargs):
        username = kwargs.get("usuario")
        rol_especifico = kwargs.get("rol")

        # Caso 1: Asignar un rol específico a un usuario
        if username and rol_especifico:
            if rol_especifico not in ROLES_OFICIALES:
                self.stdout.write(self.style.ERROR(f"Rol inválido: {rol_especifico}"))
                return

            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Usuario '{username}' no existe."))
                return

            rol, creado = Rol.objects.get_or_create(usuario=user, nombre=rol_especifico)
            if creado:
                self.stdout.write(self.style.SUCCESS(f"Rol '{rol_especifico}' asignado a {username}."))
            else:
                self.stdout.write(self.style.WARNING(f"{username} ya tenía el rol '{rol_especifico}'."))
            return

        # Caso 2: Asignar todos los roles oficiales a todos los usuarios (modo superadmin)
        if not username and not rol_especifico:
            creados = 0
            existentes = 0

            for user in User.objects.all():
                for rol in ROLES_OFICIALES:
                    obj, creado = Rol.objects.get_or_create(usuario=user, nombre=rol)
                    if creado:
                        creados += 1
                    else:
                        existentes += 1

            self.stdout.write(self.style.SUCCESS(
                f"Roles creados: {creados} | Roles ya existentes: {existentes}"
            ))
            return

        self.stdout.write(self.style.WARNING("No se ejecutó ninguna acción."))
