from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from . import permisos as P
from .api import atenciones_visibles, casos_visibles
from .models import (
    CasoSocial, Delegacion, GestionSocial, ItemMeta, Perfil, Rol, SubAtencion, TipoAtencion,
)

# Slugs válidos de los mantenedores (deben coincidir con crud.js y con las pestañas)
ENTIDADES_ADMIN = ['delegaciones', 'roles', 'usuarios', 'items', 'tipos-atencion', 'sub-atenciones']
ENTIDADES_USUARIOS = {'roles', 'usuarios'}  # el resto usa el permiso "Administrar catálogos"

# slug → (título, descripción, modelo para contar registros)
MANTENEDORES = {
    'usuarios': ('Usuarios', 'Crear, editar y asignar rol a las personas del sistema.', Perfil),
    'roles': ('Roles y permisos', 'Definir qué puede hacer cada perfil y su alcance.', Rol),
    'delegaciones': ('Delegaciones', 'Sedes territoriales donde se registra la gestión.', Delegacion),
    'items': ('Ítems y metas', 'Ítems de medición del período.', ItemMeta),
    'tipos-atencion': ('Tipos de atención', 'Catálogo de tipos de gestión.', TipoAtencion),
    'sub-atenciones': ('Sub atenciones', 'Detalle de cada tipo de atención.', SubAtencion),
}

PERFILES_TXT = {
    P.DASH_ADMINISTRADOR: ('Dashboard Administrador', 'Visión global del sistema, usuarios y todos los mantenedores.'),
    P.DASH_SUPERVISOR: ('Dashboard Supervisor', 'Información operacional de tus delegaciones y los mantenedores que tienes autorizados.'),
    P.DASH_ADMINISTRATIVO: ('Mi panel', 'Tu trabajo del día: registra atenciones y revisa lo que has ingresado.'),
}


def _barras(consulta, clave, total):
    """[{'nombre','n','pct','ancho'}] ordenado de mayor a menor, para barras de distribución."""
    filas = list(consulta.order_by().values(clave).annotate(n=Count('id')).order_by('-n', clave))
    mayor = max((f['n'] for f in filas), default=0)
    return [{
        'nombre': f[clave], 'n': f['n'],
        'pct': round(f['n'] * 100 / total) if total else 0,
        'ancho': round(f['n'] * 100 / mayor) if mayor else 0,
    } for f in filas]


def _accesos_mantenedores(user):
    """Mantenedores a los que el usuario tiene acceso (con la cantidad de registros)."""
    accesos = []
    for slug in ENTIDADES_ADMIN:
        permiso = P.PERM_USUARIOS if slug in ENTIDADES_USUARIOS else P.PERM_CATALOGOS
        if not P.tiene_permiso(user, permiso):
            continue
        titulo, descripcion, modelo = MANTENEDORES[slug]
        accesos.append({'titulo': titulo, 'descripcion': descripcion, 'n': modelo.objects.count(),
                        'url': reverse('administracion', args=[slug])})
    return accesos


def contexto_dashboard(user):
    """Cifras reales del panel según el alcance del rol (mismas reglas que la API)."""
    tipo = P.tipo_dashboard(user)
    atenciones = atenciones_visibles(user)
    casos = CasoSocial.objects.filter(pk__in=casos_visibles(user).values('pk'))
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)

    total_aten = atenciones.count()
    total_casos = casos.count()
    casos_completos = casos.annotate(n=Count('gestiones')).filter(n__gte=CasoSocial.MAX_GESTIONES).count()
    gestiones = GestionSocial.objects.filter(caso__in=casos)

    titulo, subtitulo = PERFILES_TXT[tipo]
    ctx = {
        'perfil_dashboard': tipo,
        'dash_titulo': titulo,
        'dash_subtitulo': subtitulo,
        'es_propio': P.alcance_de(user) == P.ALCANCE_PROPIO,
        'total_atenciones': total_aten,
        'atenciones_mes': atenciones.filter(fecha__gte=inicio_mes).count(),
        'atenciones_semana': atenciones.filter(fecha__gte=hoy - timedelta(days=6)).count(),
        'total_casos': total_casos,
        'casos_seguimiento': total_casos - casos_completos,
        'casos_completos': casos_completos,
        'total_gestiones': gestiones.count(),
        'ultimas_atenciones': list(atenciones[:6]),
        'ultimos_casos': list(casos.select_related('delegacion').annotate(n=Count('gestiones'))[:5]),
        'por_tipo': _barras(atenciones, 'tipo__nombre', total_aten),
        'puede_registrar': P.tiene_permiso(user, P.PERM_REGISTRAR),
        'mes_actual': hoy.strftime('%m/%Y'),
    }

    if tipo == P.DASH_ADMINISTRADOR:
        usuarios = Perfil.objects.select_related('user', 'rol')
        ctx.update({
            'usuarios_activos': usuarios.filter(user__is_active=True).count(),
            'usuarios_inactivos': usuarios.filter(user__is_active=False).count(),
            'delegaciones_activas': Delegacion.objects.filter(activo=True).count(),
            'por_rol': [{'nombre': r.nombre, 'n': r.n} for r in
                        Rol.objects.annotate(n=Count('perfiles')).order_by('-n', 'nombre')],
            'por_delegacion': _barras(atenciones, 'delegacion__nombre', total_aten),
            'accesos': _accesos_mantenedores(user),
            'ultimos_usuarios': list(usuarios.order_by('-pk')[:5]),
        })
    elif tipo == P.DASH_SUPERVISOR:
        mis_delegaciones = P.delegaciones_de(user)
        ctx.update({
            'por_delegacion': _barras(atenciones, 'delegacion__nombre', total_aten),
            'accesos': _accesos_mantenedores(user),
            'equipo': list(Perfil.objects.filter(user__is_active=True, delegaciones__in=mis_delegaciones)
                           .select_related('user', 'rol').distinct().order_by('pk')[:8]),
            'delegaciones_a_cargo': mis_delegaciones.count(),
        })
    return ctx


@login_required
def dashboard(request):
    return render(request, 'dashboard/dashboard.html', contexto_dashboard(request.user))


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
