import threading
import os
from django.core.management import call_command
from django.utils import timezone

class ActualizadorResultadosMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ignorar archivos estáticos y el panel de admin para no molestar
        if not request.path.startswith('/static/') and not request.path.startswith('/media/') and not request.path.startswith('/admin/'):
            self.verificar_actualizacion()
        return self.get_response(request)

    def verificar_actualizacion(self):
        archivo_lock = '/tmp/ultima_actualizacion_loteria.txt'
        necesita_actualizar = True

        # Candado de 5 minutos para no saturar GitHub
        if os.path.exists(archivo_lock):
            ultima_mod = os.path.getmtime(archivo_lock)
            if timezone.now().timestamp() - ultima_mod < 300:
                necesita_actualizar = False

        if necesita_actualizar:
            with open(archivo_lock, 'w') as f:
                f.write(str(timezone.now()))

            def actualizar():
                try:
                    call_command('load_results')
                except Exception as e:
                    print(f"Error en actualización dinámica: {e}")

            # Hilo en segundo plano
            threading.Thread(target=actualizar).start()