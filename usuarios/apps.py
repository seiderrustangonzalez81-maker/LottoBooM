from django.apps import AppConfig

class UsuariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usuarios'
    verbose_name = 'Usuarios'

    def ready(self):
        from django.contrib import admin
        from django.contrib.auth.models import User
        from .models import Perfil
        from .admin import UserAdmin, PerfilAdmin

        # Desregistrar si ya están registrados
        try:
            admin.site.unregister(User)
        except:
            pass
        try:
            admin.site.unregister(Perfil)
        except:
            pass

        # Registrar con nuestras clases
        admin.site.register(User, UserAdmin)
        admin.site.register(Perfil, PerfilAdmin)