"""Permisos de la API REST.

Se apoyan en las mismas reglas de la web (dashboard/permisos.py), para que un rol
pueda hacer exactamente lo mismo en ambas:

- Sin token válido → 401 (lo resuelve la autenticación JWT antes de llegar aquí).
- Con token pero sin el permiso del rol → 403.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from dashboard import permisos as P
from dashboard.api import puede_gestionar_equipo


def es_administrador(user):
    """Superusuario o rol con «Gestionar usuarios» (el perfil Administrador del sistema).
    Solo él ve los datos sensibles: RUT, teléfonos, nombre del reclamante, etc."""
    return bool(user and user.is_authenticated
                and (user.is_superuser or P.tipo_dashboard(user) == P.DASH_ADMINISTRADOR))


class PermisoDelRol(BasePermission):
    """Lectura: cualquier usuario autenticado (o el permiso 'permiso_lectura' de la vista).
    Escritura (POST, PUT, DELETE): el permiso 'permiso_escritura' de la vista.

    El permiso puede ser un texto o una tupla de textos (basta con tener uno),
    igual que en dashboard.permisos.tiene_permiso.
    """
    message = 'Tu rol no tiene permiso para esta acción.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            permiso = getattr(view, 'permiso_lectura', None)
        else:
            permiso = getattr(view, 'permiso_escritura', None)
        return permiso is None or P.tiene_permiso(user, permiso)


class SoloDelegadoEscribe(BasePermission):
    """Reclamos: todos los autenticados pueden consultar (cada uno ve lo que le corresponde),
    pero registrar, editar o eliminar es exclusivo del Delegado (o del superusuario)."""
    message = 'Solo el Delegado de la delegación puede registrar o modificar reclamos.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or puede_gestionar_equipo(user)
