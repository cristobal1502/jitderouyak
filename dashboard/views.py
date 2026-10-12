from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render

from . import permisos as P

# Slugs válidos de los mantenedores (deben coincidir con crud.js y con las pestañas)
ENTIDADES_ADMIN = ['delegaciones', 'roles', 'usuarios', 'items', 'tipos-atencion', 'sub-atenciones']
ENTIDADES_USUARIOS = {'roles', 'usuarios'}  # el resto usa el permiso "Administrar catálogos"


@login_required
def dashboard(request):
    return render(request, 'dashboard/dashboard.html')


@login_required
def agenda(request):
    return render(request, 'dashboard/agenda.html')


@login_required
def casos_sociales(request):
    return render(request, 'dashboard/casos_sociales.html')


@login_required
def busqueda(request):
    return render(request, 'dashboard/busqueda.html')


@login_required
def ingreso_atencion(request):
    return render(request, 'dashboard/ingreso_atencion.html')


@login_required
def configuraciones(request):
    perfil = P.perfil_de(request.user)
    return render(request, 'dashboard/configuraciones.html', {
        'p_nombre': P.nombre_visible(request.user),
        'p_correo': request.user.email,
        'p_cargo': perfil.rol.nombre if perfil else 'Superusuario',
        'p_telefono': perfil.telefono if perfil else '',
        'pref_vencidos': perfil.pref_vencidos if perfil else True,
        'pref_evidencias': perfil.pref_evidencias if perfil else True,
        'pref_resumen': perfil.pref_resumen if perfil else False,
    })


@login_required
def administracion(request, entidad):
    """Una sola vista para los 6 CRUD: la plantilla y crud.js se adaptan a 'entidad'."""
    if entidad not in ENTIDADES_ADMIN:
        raise Http404('Mantenedor no encontrado')
    permiso = P.PERM_USUARIOS if entidad in ENTIDADES_USUARIOS else P.PERM_CATALOGOS
    if not P.tiene_permiso(request.user, permiso):
        raise PermissionDenied
    return render(request, 'dashboard/crud.html', {'entidad': entidad})
