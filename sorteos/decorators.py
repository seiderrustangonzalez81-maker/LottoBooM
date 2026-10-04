from django.contrib.auth.decorators import user_passes_test
from .models import Rol


def superadmin_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and (
            u.is_superuser or Rol.objects.filter(usuario=u, tipo="superadmin", activo=True).exists()
        )
    )(view)


def banco_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and Rol.objects.filter(usuario=u, tipo="banco", activo=True).exists()
    )(view)


def comercial_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and Rol.objects.filter(usuario=u, tipo="comercial", activo=True).exists()
    )(view)


def cliente_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and Rol.objects.filter(usuario=u, tipo="cliente", activo=True).exists()
    )(view)


def auditor_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and Rol.objects.filter(usuario=u, tipo="auditor", activo=True).exists()
    )(view)


def gestor_required(view):
    """Cualquier usuario con rol de banco, comercial o superadmin."""
    return user_passes_test(
        lambda u: u.is_authenticated and (
            u.is_superuser or
            Rol.objects.filter(usuario=u, tipo__in=["superadmin", "banco", "comercial"], activo=True).exists()
        )
    )(view)