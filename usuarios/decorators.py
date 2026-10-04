from django.contrib.auth.decorators import user_passes_test
from roles.models import Rol


def superadmin_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and Rol.objects.filter(usuario=u, tipo="superadmin").exists()
    )(view)


def banco_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and Rol.objects.filter(usuario=u, tipo="banco").exists()
    )(view)


def comercial_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and Rol.objects.filter(usuario=u, tipo="comercial").exists()
    )(view)


def cliente_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and Rol.objects.filter(usuario=u, tipo="cliente").exists()
    )(view)


def auditor_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and Rol.objects.filter(usuario=u, tipo="auditor").exists()
    )(view)