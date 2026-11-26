"""Rutas de la API REST. Se montan en /api/v1/ desde sgr/urls.py.

    POST /api/v1/token/              login: usuario + contraseña → access + refresh
    POST /api/v1/token/refresh/      renovar el access con el refresh
    POST /api/v1/logout/             invalidar el refresh (lista negra)
    GET  /api/v1/yo/                 quién soy y qué rol tengo
    GET  /api/v1/schema/             esquema OpenAPI 3 (YAML; ?format=json para JSON)
    GET  /api/v1/docs/               Swagger UI (botón Authorize → Bearer <access>)
    /api/v1/delegaciones/  tipos-atencion/  atenciones/       (Persona 1)
    /api/v1/items/         organizaciones/  reclamos/         (Persona 2)
"""
from django.urls import path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'sgrApi'


class Router(DefaultRouter):
    include_root_view = False  # la raíz /api/v1/ la documenta Swagger


router = Router(trailing_slash='/?')  # acepta la ruta con o sin "/" final
# Persona 1
router.register('delegaciones', views.DelegacionViewSet, basename='delegacion')
router.register('tipos-atencion', views.TipoAtencionViewSet, basename='tipo-atencion')
router.register('atenciones', views.AtencionViewSet, basename='atencion')
# Persona 2
router.register('items', views.ItemMetaViewSet, basename='item')
router.register('organizaciones', views.OrganizacionViewSet, basename='organizacion')
router.register('reclamos', views.ReclamoViewSet, basename='reclamo')

urlpatterns = [
    path('token/', views.TokenObtenerView.as_view(), name='token'),
    path('token/refresh/', views.TokenRenovarView.as_view(), name='token_refresh'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('yo/', views.YoView.as_view(), name='yo'),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='sgrApi:schema'), name='docs'),
    *router.urls,
    re_path(r'^.*$', views.RutaNoEncontrada.as_view(), name='no_encontrada'),  # siempre al final
]
