from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone

from . import matriz as M
from . import permisos as P
from .api import BUSQUEDA_MAX_EXPORTAR, ErrorApi, atenciones_visibles, filtrar_busqueda
from .models import (
    Atencion, Delegacion, ItemMeta, OrganizacionComunitaria, Perfil, Rol, SubAtencion, TipoAtencion,
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


def contexto_dashboard(user, delegacion=None):
    """Cifras reales del panel según el alcance del rol (mismas reglas que la API).
    Con una delegación elegida en la barra superior, todo se limita a esa delegación."""
    tipo = P.tipo_dashboard(user)
    atenciones = atenciones_visibles(user)
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)

    organizaciones = OrganizacionComunitaria.objects.filter(activo=True)
    if P.alcance_de(user) != P.ALCANCE_TODAS:
        organizaciones = organizaciones.filter(delegacion__in=P.delegaciones_de(user))
    if delegacion is not None:
        atenciones = atenciones.filter(delegacion=delegacion)
        organizaciones = organizaciones.filter(delegacion=delegacion)
    total_aten = atenciones.count()

    titulo, subtitulo = PERFILES_TXT[tipo]
    ctx = {
        'perfil_dashboard': tipo,
        'dash_titulo': titulo,
        'dash_subtitulo': subtitulo,
        'es_propio': P.alcance_de(user) == P.ALCANCE_PROPIO,
        'total_atenciones': total_aten,
        'atenciones_mes': atenciones.filter(fecha__gte=inicio_mes).count(),
        'atenciones_semana': atenciones.filter(fecha__gte=hoy - timedelta(days=6)).count(),
        'puntos_trimestre': atenciones.filter(ejecutada_el__gte=M.rango_trimestre(*M.trimestre_de(hoy))[0])
                            .aggregate(t=Sum('puntaje'))['t'] or 0,
        'trimestre_actual': M.nombre_trimestre(*M.trimestre_de(hoy)),
        'en_preparacion': atenciones.filter(estado=Atencion.PREPARACION).count(),
        'total_organizaciones': organizaciones.count(),
        'organizaciones_pendientes': organizaciones.exclude(verificacion=OrganizacionComunitaria.VERIFICADO).count(),
        'ultimas_atenciones': list(atenciones[:6]),
        'por_tipo': _barras(atenciones, 'tipo__nombre', total_aten),
        'puede_registrar': P.tiene_permiso(user, P.PERM_REGISTRAR),
        'mes_actual': hoy.strftime('%m/%Y'),
        'delegacion_activa': delegacion,
    }

    if tipo == P.DASH_ADMINISTRADOR:
        usuarios = Perfil.objects.select_related('user', 'rol')
        if delegacion is not None:
            usuarios = usuarios.filter(delegaciones=delegacion).distinct()
        ctx.update({
            'usuarios_activos': usuarios.filter(user__is_active=True).count(),
            'usuarios_inactivos': usuarios.filter(user__is_active=False).count(),
            'delegaciones_activas': Delegacion.objects.filter(activo=True).count(),
            'por_rol': [{'nombre': r.nombre, 'n': r.n} for r in
                        Rol.objects.annotate(n=Count('perfiles', filter=Q(perfiles__in=usuarios), distinct=True))
                        .filter(n__gt=0).order_by('-n', 'nombre')],
            'por_delegacion': _barras(atenciones, 'delegacion__nombre', total_aten),
            'accesos': _accesos_mantenedores(user),
            'ultimos_usuarios': list(usuarios.order_by('-pk')[:5]),
        })
    elif tipo == P.DASH_SUPERVISOR:
        mis_delegaciones = P.delegaciones_de(user)
        if delegacion is not None:
            mis_delegaciones = mis_delegaciones.filter(pk=delegacion.pk)
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
    return render(request, 'dashboard/dashboard.html',
                  contexto_dashboard(request.user, P.delegacion_activa(request)))


@login_required
@require_POST
def cambiar_delegacion(request):
    """Selector de la barra superior: guarda en la sesión la delegación elegida ('' = todas)."""
    valor = request.POST.get('delegacion', '').strip()
    if valor and valor.isdigit() and P.delegaciones_de(request.user).filter(pk=int(valor), activo=True).exists():
        request.session[P.SESION_DELEGACION] = int(valor)
    else:
        request.session.pop(P.SESION_DELEGACION, None)
    destino = request.POST.get('next') or reverse('dashboard')
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        destino = reverse('dashboard')
    return redirect(destino)


@login_required
def agenda(request):
    return render(request, 'dashboard/agenda.html')


@login_required
def busqueda(request):
    return render(request, 'dashboard/busqueda.html')


@login_required
def busqueda_imprimir(request):
    """Versión imprimible de los resultados filtrados (el navegador la guarda como PDF)."""
    if not P.tiene_permiso(request.user, P.PERM_EXPORTAR):
        raise PermissionDenied
    try:
        qs = filtrar_busqueda(request.user, request.GET)
    except ErrorApi as e:
        if e.status == 403:
            raise PermissionDenied
        qs = atenciones_visibles(request.user).none()
    total = qs.count()
    return render(request, 'dashboard/busqueda_imprimir.html', {
        'resultados': list(qs[:BUSQUEDA_MAX_EXPORTAR]),
        'total': total,
        'recortado': total > BUSQUEDA_MAX_EXPORTAR,
        'generado': timezone.localtime(),
    })


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


@login_required
def organizaciones(request):
    """Registro de organizaciones comunitarias: todos lo consultan; lo editan quienes
    tienen «Administrar catálogos» o «Gestionar organizaciones»."""
    return render(request, 'dashboard/crud.html', {
        'entidad': 'organizaciones',
        'solo_lectura': not P.tiene_permiso(request.user, (P.PERM_CATALOGOS, P.PERM_ORGANIZACIONES)),
    })


@login_required
def matriz(request):
    """Vista de equipo de la Matriz SGR (datos por API)."""
    return render(request, 'dashboard/matriz.html')
