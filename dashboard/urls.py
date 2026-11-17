from django.urls import path

from . import api, views

urlpatterns = [
    # Pantallas
    path('', views.dashboard, name='dashboard'),
    path('agenda/', views.agenda, name='agenda'),
    path('busqueda/', views.busqueda, name='busqueda'),
    path('busqueda/imprimir/', views.busqueda_imprimir, name='busqueda_imprimir'),
    path('organizaciones/', views.organizaciones, name='organizaciones'),
    path('matriz/', views.matriz, name='matriz'),
    path('delegacion/', views.cambiar_delegacion, name='cambiar_delegacion'),
    path('ingreso-atencion/', views.ingreso_atencion, name='ingreso_atencion'),
    path('configuraciones/', views.configuraciones, name='configuraciones'),
    path('administracion/<slug:entidad>/', views.administracion, name='administracion'),

    # API JSON (las rutas fijas van antes que <slug:entidad>)
    path('api/', api.raiz, name='api_raiz'),
    path('api/yo/', api.yo, name='api_yo'),
    path('api/yo/password/', api.cambiar_password, name='api_yo_password'),
    path('api/atenciones/', api.atenciones, name='api_atenciones'),
    path('api/atenciones/<int:pk>/ejecutar/', api.ejecutar_atencion, name='api_ejecutar_atencion'),
    path('api/atenciones/<int:pk>/etapa/', api.mover_etapa, name='api_mover_etapa'),
    path('api/tubo/', api.tubo, name='api_tubo'),
    path('api/organizaciones/por-rut/', api.organizaciones_rut, name='api_organizaciones_rut'),
    path('api/matriz/', api.matriz_equipo, name='api_matriz'),
    path('api/ausencias/', api.ausencias, name='api_ausencias'),
    path('api/ausencias/<int:pk>/', api.ausencia_detalle, name='api_ausencia_detalle'),
    path('api/felicitaciones/', api.felicitaciones, name='api_felicitaciones'),
    path('api/reclamos/', api.reclamos, name='api_reclamos'),
    path('api/reclamos/<int:pk>/', api.reclamo_detalle, name='api_reclamo_detalle'),
    path('api/opciones-atencion/', api.opciones_atencion, name='api_opciones_atencion'),
    path('api/busqueda/', api.busqueda, name='api_busqueda'),
    path('api/busqueda/opciones/', api.opciones_busqueda, name='api_busqueda_opciones'),
    path('api/busqueda/exportar/', api.exportar_busqueda, name='api_busqueda_exportar'),
    path('api/usuarios/<int:pk>/reiniciar-password/', api.reiniciar_password, name='api_reiniciar_password'),
    path('api/<slug:entidad>/', api.lista, name='api_lista'),
    path('api/<slug:entidad>/<int:pk>/', api.detalle, name='api_detalle'),
]
