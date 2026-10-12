from django.urls import path

from . import api, views

urlpatterns = [
    # Pantallas
    path('', views.dashboard, name='dashboard'),
    path('agenda/', views.agenda, name='agenda'),
    path('casos_sociales/', views.casos_sociales, name='casos_sociales'),
    path('busqueda/', views.busqueda, name='busqueda'),
    path('ingreso-atencion/', views.ingreso_atencion, name='ingreso_atencion'),
    path('configuraciones/', views.configuraciones, name='configuraciones'),
    path('administracion/<slug:entidad>/', views.administracion, name='administracion'),

    # API JSON (las rutas fijas van antes que <slug:entidad>)
    path('api/', api.raiz, name='api_raiz'),
    path('api/yo/', api.yo, name='api_yo'),
    path('api/yo/password/', api.cambiar_password, name='api_yo_password'),
    path('api/atenciones/', api.atenciones, name='api_atenciones'),
    path('api/opciones-atencion/', api.opciones_atencion, name='api_opciones_atencion'),
    path('api/usuarios/<int:pk>/reiniciar-password/', api.reiniciar_password, name='api_reiniciar_password'),
    path('api/<slug:entidad>/', api.lista, name='api_lista'),
    path('api/<slug:entidad>/<int:pk>/', api.detalle, name='api_detalle'),
]
