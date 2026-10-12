"""API JSON que usa el front (fetch). Todas las rutas exigen sesión iniciada.

  GET/POST   api/<entidad>/            listar / crear
  PUT/DELETE api/<entidad>/<id>/       editar / eliminar
  POST       api/usuarios/<id>/reiniciar-password/
  GET/POST   api/atenciones/           listar (según alcance) / registrar
  GET        api/opciones-atencion/    catálogos activos para el formulario de atención
  GET/PUT    api/yo/                   perfil propio y preferencias
  POST       api/yo/password/          cambio de contraseña propio

Los errores de negocio responden {"error": <caso>, "campo": <campo>, "detalle": <texto>}
y el front los traduce a un popup de SweetAlert2 (un case por situación).
"""
import json
import re
from datetime import date
from functools import wraps

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from login.utils import enviar_correo_seguro, generar_password_temporal, validar_password

from . import permisos as P
from .models import (
    Atencion, Delegacion, ItemMeta, Perfil, Rol, SubAtencion, TipoAtencion,
)

CORREO_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
TELEFONO_RE = re.compile(r'^[0-9+()\s-]{0,30}$')


class ErrorApi(Exception):
    def __init__(self, caso, campo=None, detalle='', status=400):
        super().__init__(caso)
        self.caso = caso
        self.campo = campo
        self.detalle = detalle
        self.status = status


# ---------------------------------------------------------------- utilidades
def estado_txt(activo):
    return 'Activo' if activo else 'Inactivo'


def leer_texto(datos, key, maximo=None):
    valor = datos.get(key)
    valor = valor.strip() if isinstance(valor, str) else ''
    if not valor:
        raise ErrorApi('campo_vacio', key)
    if maximo and len(valor) > maximo:
        raise ErrorApi('texto_largo', key, str(maximo))
    return valor


def leer_estado(datos):
    valor = datos.get('estado', 'Activo')
    if valor not in ('Activo', 'Inactivo'):
        raise ErrorApi('referencia_invalida', 'estado')
    return valor == 'Activo'


def leer_id(datos, key, modelo):
    valor = datos.get(key)
    if valor in (None, ''):
        raise ErrorApi('campo_vacio', key)
    try:
        pk = int(valor)
    except (TypeError, ValueError):
        raise ErrorApi('referencia_invalida', key)
    obj = modelo.objects.filter(pk=pk).first()
    if obj is None:
        raise ErrorApi('referencia_invalida', key)
    return obj


def leer_ids(datos, key, modelo):
    valor = datos.get(key)
    if not isinstance(valor, list) or not valor:
        raise ErrorApi('sin_seleccion', key)
    try:
        ids = {int(x) for x in valor}
    except (TypeError, ValueError):
        raise ErrorApi('referencia_invalida', key)
    objs = list(modelo.objects.filter(pk__in=ids))
    if len(objs) != len(ids):
        raise ErrorApi('referencia_invalida', key)
    return objs


def verificar_unico(qs, campo_modelo, valor, instancia, key):
    qs = qs.filter(**{f'{campo_modelo}__iexact': valor})
    if instancia is not None:
        qs = qs.exclude(pk=instancia.pk)
    if qs.exists():
        raise ErrorApi('duplicado', key)


def siguiente_codigo(modelo, prefijo):
    mayor = 0
    for codigo in modelo.objects.values_list('codigo', flat=True):
        digitos = re.sub(r'\D', '', codigo)
        if digitos:
            mayor = max(mayor, int(digitos))
    return f'{prefijo}-{mayor + 1:03d}'


def exigir(request, permiso):
    if permiso and not P.tiene_permiso(request.user, permiso):
        raise ErrorApi('prohibido', status=403)


# ------------------------------------------------------------------ recursos
class Recurso:
    slug = ''
    modelo = None
    permiso_lectura = None       # None = cualquier usuario con sesión
    permiso_escritura = None

    def consulta(self):
        return self.modelo.objects.all()

    def obtener(self, pk):
        return self.consulta().filter(pk=pk).first()

    def serializar(self, obj):
        raise NotImplementedError

    def validar(self, datos, instancia, request):
        raise NotImplementedError

    def crear(self, valores, request):
        return self.modelo.objects.create(**valores)

    def actualizar(self, obj, valores, request):
        for campo, valor in valores.items():
            setattr(obj, campo, valor)
        obj.save()
        return obj

    def usos(self, obj):
        return []

    def puede_eliminar(self, obj, request):
        pass

    def borrar(self, obj, request):
        obj.delete()


class ConCodigo(Recurso):
    prefijo = ''

    def codigo_validado(self, datos, instancia):
        codigo = str(datos.get('codigo') or '').strip()
        if not codigo:
            if instancia is None:
                return siguiente_codigo(self.modelo, self.prefijo)
            raise ErrorApi('campo_vacio', 'codigo')
        if len(codigo) > 20:
            raise ErrorApi('texto_largo', 'codigo', '20')
        verificar_unico(self.modelo.objects.all(), 'codigo', codigo, instancia, 'codigo')
        return codigo


class DelegacionesRecurso(ConCodigo):
    slug = 'delegaciones'
    modelo = Delegacion
    permiso_escritura = P.PERM_CATALOGOS
    prefijo = 'DEL'

    def serializar(self, o):
        return {'id': o.pk, 'codigo': o.codigo, 'nombre': o.nombre, 'direccion': o.direccion,
                'comuna': o.comuna, 'estado': estado_txt(o.activo)}

    def validar(self, datos, instancia, request):
        return {
            'codigo': self.codigo_validado(datos, instancia),
            'nombre': leer_texto(datos, 'nombre', 120),
            'direccion': leer_texto(datos, 'direccion', 200),
            'comuna': leer_texto(datos, 'comuna', 80),
            'activo': leer_estado(datos),
        }

    def usos(self, o):
        usos = []
        if o.perfiles.exists():
            usos.append(f'{o.perfiles.count()} usuario(s)')
        if o.atenciones.exists():
            usos.append(f'{o.atenciones.count()} atención(es)')
        return usos


class ItemsRecurso(ConCodigo):
    slug = 'items'
    modelo = ItemMeta
    permiso_escritura = P.PERM_CATALOGOS
    prefijo = 'ITM'

    def serializar(self, o):
        return {'id': o.pk, 'codigo': o.codigo, 'nombre': o.nombre,
                'descripcion': o.descripcion, 'estado': estado_txt(o.activo)}

    def validar(self, datos, instancia, request):
        return {
            'codigo': self.codigo_validado(datos, instancia),
            'nombre': leer_texto(datos, 'nombre', 120),
            'descripcion': leer_texto(datos, 'descripcion'),
            'activo': leer_estado(datos),
        }


class TiposRecurso(ItemsRecurso):
    slug = 'tipos-atencion'
    modelo = TipoAtencion
    prefijo = 'TAT'

    def usos(self, o):
        usos = []
        if o.subatenciones.exists():
            usos.append(f'{o.subatenciones.count()} sub atención(es)')
        if o.atenciones.exists():
            usos.append(f'{o.atenciones.count()} atención(es)')
        return usos


class SubAtencionesRecurso(ConCodigo):
    slug = 'sub-atenciones'
    modelo = SubAtencion
    permiso_escritura = P.PERM_CATALOGOS
    prefijo = 'SUB'

    def serializar(self, o):
        return {'id': o.pk, 'codigo': o.codigo, 'nombre': o.nombre, 'tipoId': o.tipo_id,
                'estado': estado_txt(o.activo)}

    def validar(self, datos, instancia, request):
        return {
            'codigo': self.codigo_validado(datos, instancia),
            'nombre': leer_texto(datos, 'nombre', 120),
            'tipo': leer_id(datos, 'tipoId', TipoAtencion),
            'activo': leer_estado(datos),
        }

    def usos(self, o):
        n = o.atenciones.count()
        return [f'{n} atención(es)'] if n else []


class RolesRecurso(Recurso):
    slug = 'roles'
    modelo = Rol
    permiso_lectura = P.PERM_USUARIOS
    permiso_escritura = P.PERM_USUARIOS

    def serializar(self, o):
        return {'id': o.pk, 'nombre': o.nombre, 'descripcion': o.descripcion,
                'permisos': o.permisos, 'alcance': o.alcance}

    def validar(self, datos, instancia, request):
        nombre = leer_texto(datos, 'nombre', 80)
        verificar_unico(Rol.objects.all(), 'nombre', nombre, instancia, 'nombre')
        descripcion = leer_texto(datos, 'descripcion')

        permisos = datos.get('permisos')
        if not isinstance(permisos, list) or not permisos:
            raise ErrorApi('sin_seleccion', 'permisos')
        if any(p not in P.PERMISOS for p in permisos):
            raise ErrorApi('referencia_invalida', 'permisos')
        permisos = [p for p in P.PERMISOS if p in permisos]  # sin repetidos y en orden fijo

        alcance = datos.get('alcance')
        if not alcance:
            raise ErrorApi('campo_vacio', 'alcance')
        if alcance not in dict(Rol.ALCANCES):
            raise ErrorApi('referencia_invalida', 'alcance')
        return {'nombre': nombre, 'descripcion': descripcion, 'permisos': permisos, 'alcance': alcance}

    def actualizar(self, obj, valores, request):
        # Evita que un administrador se quite a sí mismo el acceso a Usuarios y Roles.
        perfil = P.perfil_de(request.user)
        if (perfil and perfil.rol_id == obj.pk and not request.user.is_superuser
                and P.PERM_USUARIOS not in valores['permisos']):
            raise ErrorApi('auto_rol', 'permisos')
        return super().actualizar(obj, valores, request)

    def usos(self, o):
        n = o.perfiles.count()
        return [f'{n} usuario(s)'] if n else []


class UsuariosRecurso(Recurso):
    slug = 'usuarios'
    modelo = Perfil
    permiso_lectura = P.PERM_USUARIOS
    permiso_escritura = P.PERM_USUARIOS

    def consulta(self):
        return (Perfil.objects.select_related('user', 'rol')
                .prefetch_related('delegaciones').order_by('pk'))

    def serializar(self, perfil):
        u = perfil.user
        return {
            'id': perfil.pk,
            'nombre': P.nombre_visible(u),
            'correo': u.email,
            'usuario': u.username,
            'rolId': perfil.rol_id,
            'delegaciones': sorted(d.pk for d in perfil.delegaciones.all()),
            'estado': estado_txt(u.is_active),
        }

    def validar(self, datos, instancia, request):
        nombre = leer_texto(datos, 'nombre', 150)
        correo = leer_texto(datos, 'correo', 254)
        if not CORREO_RE.match(correo):
            raise ErrorApi('correo_invalido', 'correo')
        yo_mismo = instancia.user if instancia is not None else None
        qs = User.objects.all()
        if yo_mismo is not None:
            qs = qs.exclude(pk=yo_mismo.pk)
        if qs.filter(email__iexact=correo).exists():
            raise ErrorApi('duplicado', 'correo')
        return {
            'nombre': nombre,
            'correo': correo,
            'rol': leer_id(datos, 'rolId', Rol),
            'delegaciones': leer_ids(datos, 'delegaciones', Delegacion),
            'activo': leer_estado(datos),
        }

    @staticmethod
    def _username_libre(correo):
        base = re.sub(r'[^\w.@+-]', '', correo.split('@')[0]).lower()[:140] or 'usuario'
        candidato, n = base, 1
        while User.objects.filter(username__iexact=candidato).exists():
            n += 1
            candidato = f'{base}{n}'
        return candidato

    def crear(self, valores, request):
        password = generar_password_temporal()
        username = self._username_libre(valores['correo'])
        with transaction.atomic():
            user = User.objects.create_user(
                username=username, email=valores['correo'], password=password,
                first_name=valores['nombre'], is_active=valores['activo'])
            perfil = Perfil.objects.create(user=user, rol=valores['rol'])
            perfil.delegaciones.set(valores['delegaciones'])
        enviar_correo_seguro(
            'Tu cuenta en SGR Municipal',
            f'Hola {valores["nombre"]},\n\nSe creó tu cuenta en SGR Municipal.\n'
            f'Usuario: {username}\nContraseña temporal: {password}\n\n'
            'Te recomendamos cambiarla en Configuraciones al ingresar.',
            valores['correo'])
        perfil.extra_respuesta = {'passwordTemporal': password, 'usuario': username}
        return perfil

    def actualizar(self, perfil, valores, request):
        user = perfil.user
        if user.pk == request.user.pk:
            if not valores['activo']:
                raise ErrorApi('auto_desactivar', 'estado')
            if not request.user.is_superuser and P.PERM_USUARIOS not in valores['rol'].permisos:
                raise ErrorApi('auto_rol', 'rolId')
        with transaction.atomic():
            user.first_name = valores['nombre']
            user.last_name = ''
            user.email = valores['correo']
            user.is_active = valores['activo']
            user.save()
            perfil.rol = valores['rol']
            perfil.save()
            perfil.delegaciones.set(valores['delegaciones'])
        return perfil

    def usos(self, perfil):
        n = perfil.user.atenciones_a_cargo.count()
        return [f'{n} atención(es) a su cargo'] if n else []

    def puede_eliminar(self, perfil, request):
        if perfil.pk == request.user.pk:
            raise ErrorApi('auto_eliminar')

    def borrar(self, perfil, request):
        perfil.user.delete()  # elimina también el Perfil (CASCADE)


RECURSOS = {r.slug: r for r in (
    DelegacionesRecurso(), RolesRecurso(), UsuariosRecurso(),
    ItemsRecurso(), TiposRecurso(), SubAtencionesRecurso(),
)}


# ------------------------------------------------------------ infraestructura
def api_login_requerido(vista):
    @wraps(vista)
    def interno(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'no_autenticado'}, status=401)
        return vista(request, *args, **kwargs)
    return interno


def leer_json(request):
    try:
        datos = json.loads(request.body or b'{}')
    except ValueError:
        raise ErrorApi('json_invalido')
    if not isinstance(datos, dict):
        raise ErrorApi('json_invalido')
    return datos


def respuesta_error(e):
    return JsonResponse({'error': e.caso, 'campo': e.campo, 'detalle': e.detalle}, status=e.status)


def con_errores(vista):
    """Convierte ErrorApi en respuesta JSON."""
    @wraps(vista)
    def interno(request, *args, **kwargs):
        try:
            return vista(request, *args, **kwargs)
        except ErrorApi as e:
            return respuesta_error(e)
    return interno


def cuerpo_de(recurso, obj):
    cuerpo = recurso.serializar(obj)
    cuerpo.update(getattr(obj, 'extra_respuesta', {}))
    return cuerpo


# ---------------------------------------------------------------------- vistas
@api_login_requerido
def raiz(request):
    return JsonResponse({'ok': True})


@api_login_requerido
@con_errores
@require_http_methods(['GET', 'POST'])
def lista(request, entidad):
    recurso = RECURSOS.get(entidad)
    if recurso is None:
        raise ErrorApi('no_encontrado', status=404)

    if request.method == 'GET':
        exigir(request, recurso.permiso_lectura)
        return JsonResponse([recurso.serializar(o) for o in recurso.consulta()], safe=False)

    exigir(request, recurso.permiso_escritura)
    valores = recurso.validar(leer_json(request), None, request)
    try:
        obj = recurso.crear(valores, request)
    except IntegrityError:
        raise ErrorApi('duplicado', 'codigo')
    return JsonResponse(cuerpo_de(recurso, obj), status=201)


@api_login_requerido
@con_errores
@require_http_methods(['PUT', 'DELETE'])
def detalle(request, entidad, pk):
    recurso = RECURSOS.get(entidad)
    if recurso is None:
        raise ErrorApi('no_encontrado', status=404)
    exigir(request, recurso.permiso_escritura)
    obj = recurso.obtener(pk)
    if obj is None:
        raise ErrorApi('no_encontrado', status=404)

    if request.method == 'PUT':
        valores = recurso.validar(leer_json(request), obj, request)
        try:
            obj = recurso.actualizar(obj, valores, request)
        except IntegrityError:
            raise ErrorApi('duplicado', 'codigo')
        return JsonResponse(cuerpo_de(recurso, obj))

    recurso.puede_eliminar(obj, request)
    usos = recurso.usos(obj)
    if usos:
        raise ErrorApi('en_uso', detalle=' y '.join(usos), status=409)
    try:
        recurso.borrar(obj, request)
    except ProtectedError:
        raise ErrorApi('en_uso', detalle='otros registros', status=409)
    return JsonResponse({'ok': True})


@api_login_requerido
@con_errores
@require_http_methods(['POST'])
def reiniciar_password(request, pk):
    exigir(request, P.PERM_USUARIOS)
    perfil = RECURSOS['usuarios'].obtener(pk)
    if perfil is None:
        raise ErrorApi('no_encontrado', status=404)
    if perfil.pk == request.user.pk:
        raise ErrorApi('auto_reiniciar')
    password = generar_password_temporal()
    perfil.user.set_password(password)
    perfil.user.save()
    enviar_correo_seguro(
        'Restablecimiento de contraseña — SGR Municipal',
        f'Hola {P.nombre_visible(perfil.user)},\n\nTu contraseña fue restablecida por un administrador.\n'
        f'Usuario: {perfil.user.username}\nContraseña temporal: {password}\n\n'
        'Te recomendamos cambiarla en Configuraciones al ingresar.',
        perfil.user.email)
    return JsonResponse({'passwordTemporal': password, 'usuario': perfil.user.username})


# ------------------------------------------------------------------ atenciones
def serializar_atencion(a):
    return {
        'id': a.pk, 'codigo': a.codigo, 'solicitante': a.solicitante,
        'tipoId': a.tipo_id, 'tipoNombre': a.tipo.nombre,
        'subId': a.subatencion_id, 'subNombre': a.subatencion.nombre,
        'descripcion': a.descripcion,
        'delegacionId': a.delegacion_id, 'delegacionNombre': a.delegacion.nombre,
        'responsableId': a.responsable_id, 'responsableNombre': P.nombre_visible(a.responsable),
        'fecha': a.fecha.isoformat(),
    }


def atenciones_visibles(user):
    qs = Atencion.objects.select_related('tipo', 'subatencion', 'delegacion', 'responsable')
    alcance = P.alcance_de(user)
    if alcance == P.ALCANCE_TODAS:
        return qs
    if alcance == P.ALCANCE_DELEGACION:
        return qs.filter(delegacion__in=P.delegaciones_de(user))
    return qs.filter(Q(responsable=user) | Q(creado_por=user))


def responsables_posibles(user, delegaciones_ids):
    """Perfiles activos que pertenecen a alguna de las delegaciones indicadas.
    Con alcance 'Propio' solo puede elegirse a sí mismo."""
    qs = (Perfil.objects.filter(user__is_active=True, delegaciones__in=delegaciones_ids)
          .select_related('user').prefetch_related('delegaciones').distinct().order_by('pk'))
    if P.alcance_de(user) == P.ALCANCE_PROPIO:
        qs = qs.filter(pk=user.pk)
    return qs


@api_login_requerido
@con_errores
@require_http_methods(['GET'])
def opciones_atencion(request):
    delegaciones = list(P.delegaciones_de(request.user).filter(activo=True))
    ids = [d.pk for d in delegaciones]
    responsables = [{
        'id': p.pk, 'nombre': P.nombre_visible(p.user),
        'delegaciones': sorted(d.pk for d in p.delegaciones.all() if d.pk in ids),
    } for p in responsables_posibles(request.user, ids)]
    return JsonResponse({
        'tipos': [{'id': t.pk, 'nombre': t.nombre} for t in TipoAtencion.objects.filter(activo=True)],
        'subatenciones': [{'id': s.pk, 'nombre': s.nombre, 'tipoId': s.tipo_id}
                          for s in SubAtencion.objects.filter(activo=True)],
        'delegaciones': [{'id': d.pk, 'nombre': d.nombre} for d in delegaciones],
        'responsables': responsables,
    })


def _validar_atencion(datos, user):
    solicitante = leer_texto(datos, 'solicitante', 150)

    tipo = leer_id(datos, 'tipoId', TipoAtencion)
    if not tipo.activo:
        raise ErrorApi('referencia_invalida', 'tipoId')

    sub = leer_id(datos, 'subId', SubAtencion)
    if not sub.activo:
        raise ErrorApi('referencia_invalida', 'subId')
    if sub.tipo_id != tipo.pk:
        raise ErrorApi('sub_no_corresponde', 'subId')

    descripcion = datos.get('descripcion')
    descripcion = descripcion.strip() if isinstance(descripcion, str) else ''
    if len(descripcion) < 10:
        raise ErrorApi('descripcion_corta', 'descripcion')

    delegacion = leer_id(datos, 'delegacionId', Delegacion)
    if not delegacion.activo:
        raise ErrorApi('referencia_invalida', 'delegacionId')
    if not P.delegaciones_de(user).filter(pk=delegacion.pk).exists():
        raise ErrorApi('prohibido', 'delegacionId', status=403)

    responsable = leer_id(datos, 'responsableId', User)
    if not responsables_posibles(user, [delegacion.pk]).filter(pk=responsable.pk).exists():
        raise ErrorApi('responsable_invalido', 'responsableId')

    fecha_txt = datos.get('fecha')
    if not fecha_txt:
        raise ErrorApi('campo_vacio', 'fecha')
    try:
        fecha = date.fromisoformat(str(fecha_txt))
    except ValueError:
        raise ErrorApi('fecha_invalida', 'fecha')
    if fecha > timezone.localdate():
        raise ErrorApi('fecha_futura', 'fecha')

    return {'solicitante': solicitante, 'tipo': tipo, 'subatencion': sub, 'descripcion': descripcion,
            'delegacion': delegacion, 'responsable': responsable, 'fecha': fecha}


@api_login_requerido
@con_errores
@require_http_methods(['GET', 'POST'])
def atenciones(request):
    if request.method == 'GET':
        return JsonResponse([serializar_atencion(a) for a in atenciones_visibles(request.user)], safe=False)

    exigir(request, P.PERM_REGISTRAR)
    valores = _validar_atencion(leer_json(request), request.user)
    atencion = None
    for _ in range(3):  # reintento por si dos personas toman el mismo correlativo a la vez
        try:
            with transaction.atomic():
                atencion = Atencion.objects.create(
                    codigo=siguiente_codigo(Atencion, 'AT'), creado_por=request.user, **valores)
            break
        except IntegrityError:
            continue
    if atencion is None:
        raise ErrorApi('duplicado', 'codigo')
    return JsonResponse(serializar_atencion(atencion), status=201)


# ------------------------------------------------------------------ perfil propio
def serializar_yo(user):
    perfil = P.perfil_de(user)
    return {
        'nombre': P.nombre_visible(user),
        'correo': user.email,
        'usuario': user.username,
        'cargo': perfil.rol.nombre if perfil else 'Superusuario',
        'telefono': perfil.telefono if perfil else '',
        'prefVencidos': perfil.pref_vencidos if perfil else True,
        'prefEvidencias': perfil.pref_evidencias if perfil else True,
        'prefResumen': perfil.pref_resumen if perfil else False,
    }


@api_login_requerido
@con_errores
@require_http_methods(['GET', 'PUT'])
def yo(request):
    user = request.user
    if request.method == 'GET':
        return JsonResponse(serializar_yo(user))

    datos = leer_json(request)
    perfil = P.perfil_de(user)

    cambios_user = {}
    if 'nombre' in datos:
        cambios_user['first_name'] = leer_texto(datos, 'nombre', 150)
    if 'correo' in datos:
        correo = leer_texto(datos, 'correo', 254)
        if not CORREO_RE.match(correo):
            raise ErrorApi('correo_invalido', 'correo')
        if User.objects.filter(email__iexact=correo).exclude(pk=user.pk).exists():
            raise ErrorApi('duplicado', 'correo')
        cambios_user['email'] = correo

    cambios_perfil = {}
    if 'telefono' in datos and (perfil is not None or datos['telefono']):
        telefono = str(datos['telefono'] or '').strip()
        if not TELEFONO_RE.match(telefono):
            raise ErrorApi('telefono_invalido', 'telefono')
        cambios_perfil['telefono'] = telefono
    for clave, campo in (('prefVencidos', 'pref_vencidos'), ('prefEvidencias', 'pref_evidencias'),
                         ('prefResumen', 'pref_resumen')):
        if clave in datos:
            if not isinstance(datos[clave], bool):
                raise ErrorApi('referencia_invalida', clave)
            cambios_perfil[campo] = datos[clave]
    if cambios_perfil and perfil is None:
        raise ErrorApi('sin_perfil')

    with transaction.atomic():
        if cambios_user:
            for campo, valor in cambios_user.items():
                setattr(user, campo, valor)
            if 'first_name' in cambios_user:
                user.last_name = ''
            user.save()
        if cambios_perfil:
            for campo, valor in cambios_perfil.items():
                setattr(perfil, campo, valor)
            perfil.save()
    return JsonResponse(serializar_yo(user))


@api_login_requerido
@con_errores
@require_http_methods(['POST'])
def cambiar_password(request):
    datos = leer_json(request)
    actual = datos.get('actual') or ''
    nueva = datos.get('nueva') or ''
    if not actual:
        raise ErrorApi('actual_vacia', 'actual')
    if not request.user.check_password(actual):
        raise ErrorApi('actual_incorrecta', 'actual')
    caso = validar_password(nueva)
    if caso:
        raise ErrorApi(caso, 'nueva')
    if nueva == actual:
        raise ErrorApi('igual_a_actual', 'nueva')
    request.user.set_password(nueva)
    request.user.save()
    update_session_auth_hash(request, request.user)  # mantiene la sesión abierta
    return JsonResponse({'ok': True})
