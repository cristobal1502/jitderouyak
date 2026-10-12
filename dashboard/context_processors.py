from .permisos import (
    ALCANCE_TODAS, PERM_CATALOGOS, PERM_REGISTRAR, PERM_USUARIOS,
    alcance_de, delegaciones_de, iniciales, nombre_visible, perfil_de, tiene_permiso,
)


def sgr(request):
    """Variables disponibles en todas las plantillas (barra superior y menú)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}

    perfil = perfil_de(user)
    puede_usuarios = tiene_permiso(user, PERM_USUARIOS)
    puede_catalogos = tiene_permiso(user, PERM_CATALOGOS)

    if alcance_de(user) == ALCANCE_TODAS:
        delegacion = 'Todas las delegaciones'
    else:
        nombres = [d.nombre for d in delegaciones_de(user)]
        delegacion = ', '.join(nombres) if nombres else 'Sin delegación'

    if user.is_superuser and perfil is None:
        rol = 'Superusuario'
    else:
        rol = perfil.rol.nombre if perfil else 'Sin rol'

    return {
        'sgr_nombre': nombre_visible(user),
        'sgr_iniciales': iniciales(user),
        'sgr_rol': rol,
        'sgr_delegacion': delegacion,
        'sgr_puede_usuarios': puede_usuarios,
        'sgr_puede_catalogos': puede_catalogos,
        'sgr_puede_admin': puede_usuarios or puede_catalogos,
        'sgr_admin_inicial': 'delegaciones' if puede_catalogos else 'usuarios',
        'sgr_puede_registrar': tiene_permiso(user, PERM_REGISTRAR),
    }
