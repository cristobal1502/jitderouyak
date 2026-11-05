"""Permisos y alcance según el rol del usuario.

Los permisos son textos guardados en Rol.permisos. Deben coincidir con las
opciones que muestra el mantenedor de Roles (OPC_PERMISOS en crud.js).
"""
from .models import Delegacion, Perfil

PERMISOS = [
    'Ver panel',
    'Registrar actividades',
    'Validar evidencias',
    'Gestionar agenda',
    'Gestionar usuarios',
    'Administrar catálogos',
    'Exportar informes',
]
PERM_USUARIOS = 'Gestionar usuarios'
PERM_CATALOGOS = 'Administrar catálogos'
PERM_REGISTRAR = 'Registrar actividades'
PERM_VALIDAR = 'Validar evidencias'
PERM_AGENDA = 'Gestionar agenda'
PERM_EXPORTAR = 'Exportar informes'

ALCANCE_TODAS = 'Todas las delegaciones'
ALCANCE_DELEGACION = 'Delegación'
ALCANCE_PROPIO = 'Propio'


def perfil_de(user):
    """Perfil del usuario o None (p. ej. un superusuario creado por consola)."""
    if not user.is_authenticated:
        return None
    try:
        return user.perfil
    except Perfil.DoesNotExist:
        return None


def tiene_permiso(user, permiso):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    perfil = perfil_de(user)
    return bool(perfil and permiso in (perfil.rol.permisos or []))


def alcance_de(user):
    if user.is_superuser:
        return ALCANCE_TODAS
    perfil = perfil_de(user)
    return perfil.rol.alcance if perfil else ALCANCE_PROPIO


def delegaciones_de(user):
    """Delegaciones sobre las que el usuario puede operar (según su alcance)."""
    if alcance_de(user) == ALCANCE_TODAS:
        return Delegacion.objects.all()
    perfil = perfil_de(user)
    return perfil.delegaciones.all() if perfil else Delegacion.objects.none()


def nombre_visible(user):
    return user.get_full_name().strip() or user.first_name or user.username


def iniciales(user):
    partes = nombre_visible(user).split()
    letras = ''.join(p[0] for p in partes[:2])
    return (letras or user.username[:2]).upper()


# Perfiles de dashboard. Se deducen de los permisos del rol (no del nombre), así
# cualquier rol nuevo que se cree en Administración cae en el panel que le corresponde.
DASH_ADMINISTRADOR = 'administrador'   # acceso total: gestiona usuarios
DASH_SUPERVISOR = 'supervisor'         # permisos intermedios: supervisa / administra catálogos / valida
DASH_ADMINISTRATIVO = 'administrativo' # permisos mínimos: solo registra


def tipo_dashboard(user):
    if user.is_superuser or tiene_permiso(user, PERM_USUARIOS):
        return DASH_ADMINISTRADOR
    if any(tiene_permiso(user, p) for p in (PERM_CATALOGOS, PERM_VALIDAR, PERM_AGENDA, PERM_EXPORTAR)):
        return DASH_SUPERVISOR
    return DASH_ADMINISTRATIVO
