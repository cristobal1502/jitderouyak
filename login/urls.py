from django.urls import path

from . import views

# Rutas de la app login (inclúyelas en el urls.py del proyecto como ya lo tienes):
urlpatterns = [
    path('', views.login_view, name='login'),
    path('salir/', views.logout_view, name='logout'),
    path('olvide-password/', views.forgot_password_view, name='forgot_password'),
    path('validar-codigo/', views.validar_codigo_view, name='validar_codigo'),
    path('validar-codigo/reenviar/', views.reenviar_codigo_view, name='reenviar_codigo'),
    path('nueva-password/', views.nueva_password_view, name='nueva_password'),
]
