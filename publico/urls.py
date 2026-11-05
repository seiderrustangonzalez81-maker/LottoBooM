from django.urls import path
from . import views
from . import landing as landing_mod

app_name = 'publico'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/version/', views.api_version, name='api_version'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    path('landing/', landing_mod.landing, name='landing'),
    path('api/estadisticas/', views.api_estadisticas, name='api_estadisticas'),
    path('api/site-version/', views.site_version, name='site_version'),
    path('faq/', views.faq_view, name='faq'),
    path('contacto/', views.contacto_view, name='contacto'),
    path('promociones/', views.promociones_view, name='promociones'),
    path('charada/', views.charada_view, name='charada'),
    path('inicio-v3/', views.home_v3, name='home_v3'),
]