"""
WSGI config for LottoBooM project.
Fija TZ antes de importar Django para que date.today() use America/Havana.
SECRET_KEY y DEBUG se leen del .env desde settings.py.
"""

import os
import sys
import time

os.environ['TZ'] = 'America/Havana'
time.tzset()

path = '/home/LottoBooM'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'LottoBooM.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
