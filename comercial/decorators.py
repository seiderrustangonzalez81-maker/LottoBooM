from django.contrib.auth.decorators import user_passes_test
from roles.models import Rol


def comercial_required(view_func):
    """Decorador para vistas exclusivas del rol comercial"""
    def check_comercial(user):
        return user.is_authenticated and (
            user.is_superuser or
            Rol.objects.filter(usuario=user, tipo="comercial", activo=True).exists()
        )
    return user_passes_test(check_comercial)(view_func)