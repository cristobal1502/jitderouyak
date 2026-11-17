"""API JSON que usa el front (fetch). Todas las rutas exigen sesión iniciada.

  GET/POST   api/<entidad>/            listar / crear
  PUT/DELETE api/<entidad>/<id>/       editar / eliminar
  POST       api/usuarios/<id>/reiniciar-password/
  GET/POST   api/atenciones/           listar (según alcance) / registrar
  GET        api/opciones-atencion/    catálogos activos para el formulario de atención
  GET        api/busqueda/             búsqueda avanzada de atenciones (filtros + paginación)
  GET        api/busqueda/opciones/    valores de los filtros según el alcance del rol
  GET        api/busqueda/exportar/    los mismos resultados en Excel (.xlsx), requiere "Exportar informes"
  GET/PUT    api/yo/                   perfil propio y preferencias
  POST       api/yo/password/          cambio de contraseña propio

Los errores de negocio responden {"error": <caso>, "campo": <campo>, "detalle": <texto>}
y el front los traduce a un popup de SweetAlert2 (un case por situación).
"""
import json
import re
from datetime import date, timedelta
import unicodedata
from functools import wraps

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from login.utils import enviar_correo_seguro, generar_password_temporal, validar_password

from . import matriz as M
from . import permisos as P
from .models import (
    Atencion, Ausencia, Delegacion, Felicitacion, ItemMeta,
    OrganizacionComunitaria, Perfil, Rol, SubAtencion, TipoAtencion,
)

CORREO_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
TELEFONO_RE = re.compile(r'^[0-9+()\s-]{0,30}$')


def telefono_valido(telefono):
    """Solo números, espacios y + ( ) -, con 8 a 15 dígitos."""
    return bool(TELEFONO_RE.fullmatch(telefono)) and 8 <= len(re.sub(r'\D', '', telefono)) <= 15


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
        if o.casos.exists():
            usos.append(f'{o.casos.count()} caso(s) social(es)')
        if o.organizaciones.exists():
            usos.append(f'{o.organizaciones.count()} organización(es) comunitaria(s)')
        return usos


class CatalogoSimple(ConCodigo):
    """Catálogo con código, nombre, descripción y estado."""
    permiso_escritura = P.PERM_CATALOGOS

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


class ItemsRecurso(CatalogoSimple):
    slug = 'items'
    modelo = ItemMeta
    prefijo = 'ITM'

    def serializar(self, o):
        return {**super().serializar(o), 'metaTrimestral': o.meta_trimestral}

    def validar(self, datos, instancia, request):
        valores = super().validar(datos, instancia, request)
        meta = datos.get('metaTrimestral')
        if meta in (None, ''):
            raise ErrorApi('campo_vacio', 'metaTrimestral')
        try:
            meta = int(meta)
        except (TypeError, ValueError):
            raise ErrorApi('numero_invalido', 'metaTrimestral')
        if not 1 <= meta <= 1500:
            raise ErrorApi('numero_invalido', 'metaTrimestral')
        valores['meta_trimestral'] = meta
        return valores

    def usos(self, o):
        n = o.atenciones.count()
        return [f'{n} atención(es)'] if n else []


class TiposRecurso(CatalogoSimple):
    slug = 'tipos-atencion'
    modelo = TipoAtencion
    prefijo = 'TAT'

    def usos(self, o):
        usos = []
        if o.subatenciones.exists():
            usos.append(f'{o.subatenciones.count()} sub atención(es)')
        if o.atenciones.exists():
            usos.append(f'{o.atenciones.count()} atención(es)')
        if o.gestiones.exists():
            usos.append(f'{o.gestiones.count()} gestión(es) social(es)')
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
        usos = []
        n = perfil.user.atenciones_a_cargo.count()
        if n:
            usos.append(f'{n} atención(es) a su cargo')
        g = perfil.user.gestiones_atendidas.count()
        if g:
            usos.append(f'{g} gestión(es) social(es)')
        return usos

    def puede_eliminar(self, perfil, request):
        if perfil.pk == request.user.pk:
            raise ErrorApi('auto_eliminar')

    def borrar(self, perfil, request):
        perfil.user.delete()  # elimina también el Perfil (CASCADE)


def leer_directiva(datos):
    """Presidente, tesorero y secretario: nombre y RUT obligatorios, y tres RUT distintos.
    El campo del error se informa como 'directiva.<cargo>.<nombre|rut>'."""
    directiva = datos.get('directiva')
    if not isinstance(directiva, dict):
        directiva = {}
    valores, ruts = {}, {}
    for cargo, _ in OrganizacionComunitaria.CARGOS:
        persona = directiva.get(cargo) if isinstance(directiva.get(cargo), dict) else {}
        nombre = persona.get('nombre')
        nombre = nombre.strip() if isinstance(nombre, str) else ''
        if not nombre:
            raise ErrorApi('campo_vacio', f'directiva.{cargo}.nombre')
        if len(nombre) > 150:
            raise ErrorApi('texto_largo', f'directiva.{cargo}.nombre', '150')
        if not re.search(r'[^\W\d_]', nombre):
            raise ErrorApi('nombre_invalido', f'directiva.{cargo}.nombre')
        rut_txt = persona.get('rut') if isinstance(persona.get('rut'), str) else ''
        if not rut_txt.strip():
            raise ErrorApi('campo_vacio', f'directiva.{cargo}.rut')
        rut = validar_rut(rut_txt, f'directiva.{cargo}.rut')
        if rut in ruts.values():
            raise ErrorApi('rut_repetido', f'directiva.{cargo}.rut')
        ruts[cargo] = rut
        valores[f'{cargo}_nombre'] = nombre
        valores[f'{cargo}_rut'] = rut
    return valores


def organizaciones_por_rut(rut):
    """Organizaciones activas donde esa persona es parte de la directiva, con su cargo."""
    filtro = Q(presidente_rut=rut) | Q(tesorero_rut=rut) | Q(secretario_rut=rut)
    resultado = []
    for o in OrganizacionComunitaria.objects.filter(filtro, activo=True).select_related('delegacion'):
        for cargo, etiqueta in OrganizacionComunitaria.CARGOS:
            if getattr(o, f'{cargo}_rut') == rut:
                resultado.append({'id': o.pk, 'codigo': o.codigo, 'nombre': o.nombre, 'cargo': etiqueta,
                                  'personaNombre': getattr(o, f'{cargo}_nombre'),
                                  'delegacionId': o.delegacion_id, 'delegacionNombre': o.delegacion.nombre,
                                  'verificacion': o.verificacion})
    return resultado


class OrganizacionesRecurso(ConCodigo):
    slug = 'organizaciones'
    modelo = OrganizacionComunitaria
    permiso_escritura = (P.PERM_CATALOGOS, P.PERM_ORGANIZACIONES)
    prefijo = 'ORG'

    def consulta(self):
        return OrganizacionComunitaria.objects.select_related('delegacion')

    def serializar(self, o):
        return {'id': o.pk, 'codigo': o.codigo, 'nombre': o.nombre, 'tipo': o.tipo,
                'subcategoria': o.subcategoria, 'delegacionId': o.delegacion_id, 'sector': o.sector,
                'directiva': {cargo: {'nombre': getattr(o, f'{cargo}_nombre'), 'rut': getattr(o, f'{cargo}_rut')}
                              for cargo, _ in OrganizacionComunitaria.CARGOS},
                'telefono': o.telefono, 'verificacion': o.verificacion, 'estado': estado_txt(o.activo)}

    def validar(self, datos, instancia, request):
        tipo = datos.get('tipo')
        if not tipo:
            raise ErrorApi('campo_vacio', 'tipo')
        if tipo not in dict(OrganizacionComunitaria.TIPOS):
            raise ErrorApi('referencia_invalida', 'tipo')

        subcategoria = (datos.get('subcategoria') or '').strip()
        if tipo == OrganizacionComunitaria.FUNCIONAL:
            if not subcategoria:
                raise ErrorApi('campo_vacio', 'subcategoria')
            if subcategoria not in OrganizacionComunitaria.SUBCATEGORIAS:
                raise ErrorApi('referencia_invalida', 'subcategoria')
        else:
            subcategoria = ''  # las juntas de vecinos (territoriales) no tienen subfamilia

        delegacion = leer_id(datos, 'delegacionId', Delegacion)
        if not P.delegaciones_de(request.user).filter(pk=delegacion.pk).exists():
            raise ErrorApi('prohibido', 'delegacionId', status=403)

        telefono = (datos.get('telefono') or '').strip()
        if telefono and not telefono_valido(telefono):
            raise ErrorApi('telefono_invalido', 'telefono')

        verificacion = datos.get('verificacion') or OrganizacionComunitaria.PENDIENTE
        if verificacion not in dict(OrganizacionComunitaria.VERIFICACIONES):
            raise ErrorApi('referencia_invalida', 'verificacion')

        directiva = leer_directiva(datos)

        return {
            **directiva,
            'codigo': self.codigo_validado(datos, instancia),
            'nombre': leer_texto(datos, 'nombre', 150),
            'tipo': tipo,
            'subcategoria': subcategoria,
            'delegacion': delegacion,
            'sector': leer_texto(datos, 'sector', 120),
            'telefono': telefono,
            'verificacion': verificacion,
            'activo': leer_estado(datos),
        }

    def puede_eliminar(self, obj, request):
        if not P.delegaciones_de(request.user).filter(pk=obj.delegacion_id).exists():
            raise ErrorApi('prohibido', status=403)

    def actualizar(self, obj, valores, request):
        self.puede_eliminar(obj, request)  # solo organizaciones de sus delegaciones
        return super().actualizar(obj, valores, request)


RECURSOS = {r.slug: r for r in (
    DelegacionesRecurso(), RolesRecurso(), UsuariosRecurso(),
    ItemsRecurso(), TiposRecurso(), SubAtencionesRecurso(), OrganizacionesRecurso(),
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
        'id': a.pk, 'codigo': a.codigo, 'solicitante': a.solicitante, 'rut': a.rut, 'telefono': a.telefono,
        'clasificacion': a.clasificacion,
        'itemId': a.item_id, 'itemNombre': a.item.nombre if a.item_id else '',
        'estado': a.estado, 'ejecutadaEl': a.ejecutada_el.isoformat() if a.ejecutada_el else None,
        'puntaje': a.puntaje, 'topeAlcanzado': a.tope_alcanzado,
        'tipoId': a.tipo_id, 'tipoNombre': a.tipo.nombre,
        'subId': a.subatencion_id, 'subNombre': a.subatencion.nombre,
        'descripcion': a.descripcion,
        'delegacionId': a.delegacion_id, 'delegacionNombre': a.delegacion.nombre,
        'responsableId': a.responsable_id, 'responsableNombre': P.nombre_visible(a.responsable),
        'fecha': a.fecha.isoformat(),
        'beneficiario': a.beneficiario,
        'organizacionId': a.organizacion_id,
        'organizacionNombre': a.organizacion.nombre if a.organizacion_id else '',
        'etapa': a.etapa,
        'fechaCompromiso': a.fecha_compromiso.isoformat() if a.fecha_compromiso else None,
        'vencido': esta_vencida(a),
    }


def esta_vencida(a, hoy=None):
    """Una actividad no realizada cuyo plazo ya pasó."""
    hoy = hoy or timezone.localdate()
    return a.etapa != Atencion.REALIZADO and a.fecha_compromiso is not None and a.fecha_compromiso < hoy


def atenciones_visibles(user):
    qs = Atencion.objects.select_related('tipo', 'subatencion', 'delegacion', 'responsable', 'item', 'organizacion')
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
        'items': [{'id': i.pk, 'nombre': i.nombre} for i in ItemMeta.objects.filter(activo=True)],
        'delegaciones': [{'id': d.pk, 'nombre': d.nombre} for d in delegaciones],
        'responsables': responsables,
        'fechaMinima': primera_fecha_abierta().isoformat(),
        'maxPorDia': Atencion.MAX_POR_DIA,
        'plazoDias': Atencion.PLAZO_DIAS,
        'organizaciones': [{'id': o.pk, 'nombre': o.nombre, 'delegacionId': o.delegacion_id, 'tipo': o.tipo}
                           for o in OrganizacionComunitaria.objects.filter(activo=True, delegacion__in=ids)
                           .order_by('nombre')],
    })


@api_login_requerido
@con_errores
@require_http_methods(['GET'])
def organizaciones_rut(request):
    """Al escribir el RUT del vecino: ¿es dirigente de alguna organización? Devuelve el RUT
    formateado y las organizaciones (con su cargo) donde aparece en la directiva."""
    texto = (request.GET.get('rut') or '').strip()
    if not texto:
        raise ErrorApi('campo_vacio', 'rut')
    rut = validar_rut(texto)
    return JsonResponse({'rut': rut, 'organizaciones': organizaciones_por_rut(rut)})


def limite_ingreso(fecha):
    """Último día en que se puede ingresar una actividad de esa fecha: el lunes siguiente
    a su semana. Desde el martes la semana anterior queda cerrada."""
    return fecha - timedelta(days=fecha.weekday()) + timedelta(days=7)


def primera_fecha_abierta(hoy=None):
    """Fecha más antigua que todavía se puede ingresar hoy."""
    hoy = hoy or timezone.localdate()
    lunes = hoy - timedelta(days=hoy.weekday())
    return lunes - timedelta(days=7) if hoy.weekday() == 0 else lunes


def validar_rut(texto, key='rut'):
    """Devuelve el RUT con formato 12.345.678-9 o lanza ErrorApi('rut_invalido') (módulo 11)."""
    limpio = re.sub(r'[.\s-]', '', str(texto or '')).upper()
    if not re.fullmatch(r'\d{7,8}[\dK]', limpio):
        raise ErrorApi('rut_invalido', key)
    cuerpo, dv = limpio[:-1], limpio[-1]
    suma = sum(int(d) * f for d, f in zip(reversed(cuerpo), (2, 3, 4, 5, 6, 7) * 2))
    resto = 11 - suma % 11
    esperado = '0' if resto == 11 else 'K' if resto == 10 else str(resto)
    if dv != esperado:
        raise ErrorApi('rut_invalido', key)
    return f'{int(cuerpo):,}'.replace(',', '.') + '-' + dv


def leer_telefono(datos, key='telefono'):
    telefono = datos.get(key)
    telefono = telefono.strip() if isinstance(telefono, str) else ''
    if not telefono:
        raise ErrorApi('campo_vacio', key)
    if not telefono_valido(telefono):
        raise ErrorApi('telefono_invalido', key)
    return telefono


def _normalizar_nombre(texto):
    sin_tildes = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
    return ' '.join(sin_tildes.lower().split())


def solicitante_es_delegado(solicitante, delegacion):
    """True si el solicitante coincide con el nombre de un Delegado de esa delegación."""
    buscado = _normalizar_nombre(solicitante)
    for perfil in delegacion.perfiles.select_related('user', 'rol'):
        if P.es_delegado(perfil.user) and _normalizar_nombre(P.nombre_visible(perfil.user)) == buscado:
            return True
    return False


def _validar_atencion(datos, user):
    solicitante = leer_texto(datos, 'solicitante', 150)
    if not re.search(r'[^\W\d_]', solicitante):  # al menos una letra: no vale un número o símbolo suelto
        raise ErrorApi('nombre_invalido', 'solicitante')
    rut = (datos.get('rut') or '').strip() if isinstance(datos.get('rut'), str) else ''
    rut = validar_rut(rut) if rut else ''
    telefono = leer_telefono(datos)

    tipo = leer_id(datos, 'tipoId', TipoAtencion)
    if not tipo.activo:
        raise ErrorApi('referencia_invalida', 'tipoId')

    sub = leer_id(datos, 'subId', SubAtencion)
    if not sub.activo:
        raise ErrorApi('referencia_invalida', 'subId')
    if sub.tipo_id != tipo.pk:
        raise ErrorApi('sub_no_corresponde', 'subId')

    item = leer_id(datos, 'itemId', ItemMeta)
    if not item.activo:
        raise ErrorApi('referencia_invalida', 'itemId')

    estado = datos.get('estado') or Atencion.EJECUTADA
    if estado not in dict(Atencion.ESTADOS):
        raise ErrorApi('referencia_invalida', 'estado')

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
    hoy = timezone.localdate()
    if fecha > hoy:
        raise ErrorApi('fecha_futura', 'fecha')
    if hoy > limite_ingreso(fecha):
        raise ErrorApi('semana_cerrada', 'fecha', limite_ingreso(fecha).isoformat())

    if Atencion.objects.filter(responsable=responsable, fecha=fecha).count() >= Atencion.MAX_POR_DIA:
        raise ErrorApi('limite_diario', 'fecha', str(Atencion.MAX_POR_DIA))

    es_delegado = datos.get('solicitanteEsDelegado') is True or solicitante_es_delegado(solicitante, delegacion)
    clasificacion = Atencion.OTRA_GESTION if es_delegado else Atencion.CIUDADANA

    beneficiario = datos.get('beneficiario') or Atencion.PERSONA
    if beneficiario not in dict(Atencion.BENEFICIARIOS):
        raise ErrorApi('referencia_invalida', 'beneficiario')
    organizacion = None
    if beneficiario == Atencion.ORGANIZACION:
        organizacion = leer_id(datos, 'organizacionId', OrganizacionComunitaria)
        if not organizacion.activo:
            raise ErrorApi('referencia_invalida', 'organizacionId')

    plazo_txt = datos.get('fechaCompromiso')
    if plazo_txt:
        try:
            plazo = date.fromisoformat(str(plazo_txt))
        except ValueError:
            raise ErrorApi('fecha_invalida', 'fechaCompromiso')
        if plazo < fecha:
            raise ErrorApi('plazo_anterior', 'fechaCompromiso')
    else:
        plazo = fecha + timedelta(days=Atencion.PLAZO_DIAS)

    return {'solicitante': solicitante, 'rut': rut, 'telefono': telefono, 'tipo': tipo, 'subatencion': sub,
            'item': item, 'estado': estado, 'ejecutada_el': fecha if estado == Atencion.EJECUTADA else None,
            'etapa': Atencion.REALIZADO if estado == Atencion.EJECUTADA else Atencion.INGRESADO,
            'fecha_compromiso': plazo, 'beneficiario': beneficiario, 'organizacion': organizacion,
            'descripcion': descripcion, 'delegacion': delegacion, 'responsable': responsable,
            'fecha': fecha, 'clasificacion': clasificacion}


@api_login_requerido
@con_errores
@require_http_methods(['GET', 'POST'])
def atenciones(request):
    if request.method == 'GET':
        return JsonResponse([serializar_atencion(a) for a in atenciones_visibles(request.user)], safe=False)

    exigir(request, P.PERM_REGISTRAR)
    valores = _validar_atencion(leer_json(request), request.user)
    atencion = alerta = None
    for _ in range(3):  # reintento por si dos personas toman el mismo correlativo a la vez
        try:
            with transaction.atomic():
                atencion = Atencion(codigo=siguiente_codigo(Atencion, 'AT'), creado_por=request.user, **valores)
                alerta = M.asignar_puntaje(atencion)
                atencion.save()
            break
        except IntegrityError:
            atencion = None
            continue
    if atencion is None:
        raise ErrorApi('duplicado', 'codigo')
    return JsonResponse({**serializar_atencion(atencion), 'alerta': alerta}, status=201)


def _fecha_ejecucion(texto, atencion):
    hoy = timezone.localdate()
    try:
        dia = date.fromisoformat(str(texto or hoy.isoformat()))
    except ValueError:
        raise ErrorApi('fecha_invalida', 'fecha')
    if dia > hoy:
        raise ErrorApi('fecha_futura', 'fecha')
    if dia < atencion.fecha:
        raise ErrorApi('ejecucion_anterior', 'fecha', atencion.fecha.isoformat())
    if hoy > limite_ingreso(dia):
        raise ErrorApi('semana_cerrada', 'fecha', limite_ingreso(dia).isoformat())
    return dia


def marcar_ejecutada(pk, dia):
    """Pasa una actividad a Ejecutada / Realizado y calcula su puntaje. Bloquea la fila mientras tanto."""
    with transaction.atomic():
        atencion = Atencion.objects.select_for_update().select_related('item', 'responsable').get(pk=pk)
        if atencion.estado == Atencion.EJECUTADA:
            raise ErrorApi('ya_ejecutada', status=409)
        atencion.estado = Atencion.EJECUTADA
        atencion.etapa = Atencion.REALIZADO
        atencion.ejecutada_el = dia
        alerta = M.asignar_puntaje(atencion)
        atencion.save(update_fields=['estado', 'etapa', 'ejecutada_el', 'puntaje', 'tope_alcanzado'])
    return alerta


@api_login_requerido
@con_errores
@require_http_methods(['POST'])
def ejecutar_atencion(request, pk):
    """Marca como ejecutada una actividad registrada en preparación. Desde ahí puede sumar puntaje."""
    exigir(request, P.PERM_REGISTRAR)
    atencion = atenciones_visibles(request.user).filter(pk=pk).first()
    if atencion is None:
        raise ErrorApi('no_encontrado', status=404)
    if atencion.estado == Atencion.EJECUTADA:
        raise ErrorApi('ya_ejecutada', status=409)
    dia = _fecha_ejecucion(leer_json(request).get('fecha'), atencion)
    alerta = marcar_ejecutada(pk, dia)
    return JsonResponse({**serializar_atencion(atenciones_visibles(request.user).get(pk=pk)), 'alerta': alerta})


# ---------------------------------------------------------- tubo de trabajo
def puede_mover_tubo(user):
    return P.tiene_permiso(user, (P.PERM_REGISTRAR, P.PERM_AGENDA))


@api_login_requerido
@con_errores
@require_http_methods(['GET'])
def tubo(request):
    """Actividades del tubo según el alcance del rol. Filtros: delegacion, responsable, etapa
    (incluye 'Vencido') y q. Devuelve también el conteo por etapa."""
    user, params = request.user, request.GET
    qs = atenciones_visibles(user)
    delegacion = _leer_pk(params, 'delegacion')
    if delegacion is not None:
        if not P.delegaciones_de(user).filter(pk=delegacion).exists():
            raise ErrorApi('prohibido', 'delegacion', status=403)
        qs = qs.filter(delegacion_id=delegacion)
    responsable = _leer_pk(params, 'responsable')
    if responsable is not None:
        qs = qs.filter(responsable_id=responsable)
    q = (params.get('q') or '').strip()
    for palabra in q.split()[:6]:
        qs = qs.filter(Q(codigo__icontains=palabra) | Q(solicitante__icontains=palabra)
                       | Q(descripcion__icontains=palabra) | Q(organizacion__nombre__icontains=palabra))

    hoy = timezone.localdate()
    todas = list(qs.order_by('fecha_compromiso', 'fecha', 'id')[:1000])
    conteo = {e: 0 for e, _ in Atencion.ETAPAS}
    conteo['Vencido'] = 0
    for a in todas:
        conteo[a.etapa] += 1
        if esta_vencida(a, hoy):
            conteo['Vencido'] += 1

    etapa = (params.get('etapa') or '').strip()
    if etapa == 'Vencido':
        todas = [a for a in todas if esta_vencida(a, hoy)]
    elif etapa:
        if etapa not in dict(Atencion.ETAPAS):
            raise ErrorApi('referencia_invalida', 'etapa')
        todas = [a for a in todas if a.etapa == etapa]

    responsables = (User.objects.filter(pk__in=atenciones_visibles(user).values('responsable'))
                    .order_by('first_name', 'last_name', 'username'))
    return JsonResponse({
        'actividades': [serializar_atencion(a) for a in todas],
        'conteo': {**conteo, 'Total': sum(conteo[e] for e, _ in Atencion.ETAPAS)},
        'etapas': [e for e, _ in Atencion.ETAPAS],
        'responsables': [{'id': u.pk, 'nombre': P.nombre_visible(u)} for u in responsables],
        'delegaciones': [{'id': d.pk, 'nombre': d.nombre} for d in P.delegaciones_de(user).order_by('nombre')],
        'puedeMover': puede_mover_tubo(user),
    })


@api_login_requerido
@con_errores
@require_http_methods(['POST'])
def mover_etapa(request, pk):
    """Mueve una actividad entre las etapas del tubo. Llevarla a «Realizado» la marca como
    ejecutada (y suma su punto si corresponde). Una actividad realizada ya no se puede devolver."""
    if not puede_mover_tubo(request.user):
        raise ErrorApi('prohibido', status=403)
    atencion = atenciones_visibles(request.user).filter(pk=pk).first()
    if atencion is None:
        raise ErrorApi('no_encontrado', status=404)
    datos = leer_json(request)
    etapa = datos.get('etapa')
    if etapa not in dict(Atencion.ETAPAS):
        raise ErrorApi('referencia_invalida', 'etapa')
    if atencion.etapa == Atencion.REALIZADO:
        raise ErrorApi('ya_realizada', 'etapa', status=409)

    alerta = None
    if etapa == Atencion.REALIZADO:
        dia = _fecha_ejecucion(datos.get('fecha'), atencion)
        alerta = marcar_ejecutada(pk, dia)
    elif etapa != atencion.etapa:
        Atencion.objects.filter(pk=pk).update(etapa=etapa)
    return JsonResponse({**serializar_atencion(atenciones_visibles(request.user).get(pk=pk)), 'alerta': alerta})


# ---------------------------------------------------------- búsqueda avanzada
BUSQUEDA_POR_PAGINA = 10
BUSQUEDA_MAX_POR_PAGINA = 100
BUSQUEDA_MAX_EXPORTAR = 5000


def _leer_pk(params, key):
    valor = (params.get(key) or '').strip()
    if not valor:
        return None
    try:
        return int(valor)
    except ValueError:
        raise ErrorApi('referencia_invalida', key)


def _leer_fecha(params, key):
    valor = (params.get(key) or '').strip()
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise ErrorApi('fecha_invalida', key)


def filtrar_busqueda(user, params):
    """Atenciones visibles para el usuario que cumplen los filtros de la query string.
    Parámetros (todos opcionales): delegacion, funcionario, tipo, sub (ids), clasificacion, desde, hasta
    (AAAA-MM-DD) y q (palabras clave en código, solicitante, descripción, tipo y sub atención)."""
    qs = atenciones_visibles(user)

    delegacion = _leer_pk(params, 'delegacion')
    if delegacion is not None:
        if not P.delegaciones_de(user).filter(pk=delegacion).exists():
            raise ErrorApi('prohibido', 'delegacion', status=403)
        qs = qs.filter(delegacion_id=delegacion)

    funcionario = _leer_pk(params, 'funcionario')
    if funcionario is not None:
        qs = qs.filter(responsable_id=funcionario)

    tipo = _leer_pk(params, 'tipo')
    if tipo is not None:
        if not TipoAtencion.objects.filter(pk=tipo).exists():
            raise ErrorApi('referencia_invalida', 'tipo')
        qs = qs.filter(tipo_id=tipo)

    sub = _leer_pk(params, 'sub')
    if sub is not None:
        sub_obj = SubAtencion.objects.filter(pk=sub).first()
        if sub_obj is None:
            raise ErrorApi('referencia_invalida', 'sub')
        if tipo is not None and sub_obj.tipo_id != tipo:
            raise ErrorApi('sub_no_corresponde', 'sub')
        qs = qs.filter(subatencion_id=sub)

    desde, hasta = _leer_fecha(params, 'desde'), _leer_fecha(params, 'hasta')
    if desde and hasta and desde > hasta:
        raise ErrorApi('rango_invalido', 'desde')
    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)

    item = _leer_pk(params, 'item')
    if item is not None:
        if not ItemMeta.objects.filter(pk=item).exists():
            raise ErrorApi('referencia_invalida', 'item')
        qs = qs.filter(item_id=item)

    estado = (params.get('estado') or '').strip()
    if estado:
        if estado not in dict(Atencion.ESTADOS):
            raise ErrorApi('referencia_invalida', 'estado')
        qs = qs.filter(estado=estado)

    clasificacion = (params.get('clasificacion') or '').strip()
    if clasificacion:
        if clasificacion not in dict(Atencion.CLASIFICACIONES):
            raise ErrorApi('referencia_invalida', 'clasificacion')
        qs = qs.filter(clasificacion=clasificacion)

    q = (params.get('q') or '').strip()
    if len(q) > 100:
        raise ErrorApi('texto_largo', 'q', '100')
    for palabra in q.split():
        qs = qs.filter(Q(codigo__icontains=palabra) | Q(solicitante__icontains=palabra)
                       | Q(telefono__icontains=palabra) | Q(rut__icontains=palabra)
                       | Q(organizacion__nombre__icontains=palabra)
                       | Q(descripcion__icontains=palabra) | Q(tipo__nombre__icontains=palabra)
                       | Q(subatencion__nombre__icontains=palabra))

    return qs.order_by('-fecha', '-id')


@api_login_requerido
@con_errores
@require_http_methods(['GET'])
def busqueda(request):
    qs = filtrar_busqueda(request.user, request.GET)
    try:
        pagina = max(1, int(request.GET.get('pagina') or 1))
        por_pagina = int(request.GET.get('por_pagina') or BUSQUEDA_POR_PAGINA)
    except ValueError:
        raise ErrorApi('referencia_invalida', 'pagina')
    por_pagina = min(max(1, por_pagina), BUSQUEDA_MAX_POR_PAGINA)

    total = qs.count()
    paginas = max(1, -(-total // por_pagina))
    pagina = min(pagina, paginas)
    inicio = (pagina - 1) * por_pagina
    return JsonResponse({
        'total': total, 'pagina': pagina, 'paginas': paginas, 'porPagina': por_pagina,
        'resultados': [serializar_atencion(a) for a in qs[inicio:inicio + por_pagina]],
    })


@api_login_requerido
@con_errores
@require_http_methods(['GET'])
def opciones_busqueda(request):
    """Valores para los filtros. Incluye registros inactivos: sirven para buscar el historial."""
    user = request.user
    responsables = (User.objects.filter(pk__in=atenciones_visibles(user).values('responsable'))
                    .order_by('first_name', 'last_name', 'username'))
    fechas = atenciones_visibles(user).order_by().values_list('fecha__year', flat=True).distinct()
    return JsonResponse({
        'delegaciones': [{'id': d.pk, 'nombre': d.nombre} for d in P.delegaciones_de(user).order_by('nombre')],
        'funcionarios': [{'id': u.pk, 'nombre': P.nombre_visible(u)} for u in responsables],
        'tipos': [{'id': t.pk, 'nombre': t.nombre} for t in TipoAtencion.objects.order_by('nombre')],
        'subatenciones': [{'id': s.pk, 'nombre': s.nombre, 'tipoId': s.tipo_id}
                          for s in SubAtencion.objects.order_by('nombre')],
        'anios': sorted(set(fechas) | {timezone.localdate().year}, reverse=True),
        'clasificaciones': [c for c, _ in Atencion.CLASIFICACIONES],
        'items': [{'id': i.pk, 'nombre': i.nombre} for i in ItemMeta.objects.order_by('nombre')],
        'estados': [e for e, _ in Atencion.ESTADOS],
        'puedeExportar': P.tiene_permiso(user, P.PERM_EXPORTAR),
    })


COLUMNAS_EXPORTAR = ['Código', 'Fecha', 'Funcionario', 'Delegación', 'Tipo de atención',
                     'Sub atención', 'Solicitante', 'RUT', 'Teléfono', 'Organización', 'Clasificación', 'Ítem / meta', 'Estado',
                     'Puntaje', 'Descripción']


def filas_exportar(qs):
    for a in qs[:BUSQUEDA_MAX_EXPORTAR]:
        yield [a.codigo, a.fecha, P.nombre_visible(a.responsable), a.delegacion.nombre,
               a.tipo.nombre, a.subatencion.nombre, a.solicitante, a.rut, a.telefono,
               a.organizacion.nombre if a.organizacion_id else '', a.clasificacion,
               a.item.nombre if a.item_id else '', a.estado, a.puntaje, a.descripcion]


@api_login_requerido
@con_errores
@require_http_methods(['GET'])
def exportar_busqueda(request):
    exigir(request, P.PERM_EXPORTAR)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    qs = filtrar_busqueda(request.user, request.GET)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Atenciones'
    ws.append(COLUMNAS_EXPORTAR)
    for celda in ws[1]:
        celda.font = Font(bold=True, color='FFFFFF')
        celda.fill = PatternFill('solid', fgColor='C41230')
    for fila in filas_exportar(qs):
        ws.append(fila)
    for celda in ws['B'][1:]:
        celda.number_format = 'DD/MM/YYYY'
    for i, ancho in enumerate([10, 12, 22, 20, 22, 26, 28, 13, 16, 28, 20, 24, 14, 9, 60], start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f'attachment; filename="busqueda_atenciones_{timezone.localdate():%Y%m%d}.xlsx"'
    wb.save(resp)
    return resp


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
        if telefono and not telefono_valido(telefono):
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


# ------------------------------------------------------------------ matriz SGR
def puede_gestionar_equipo(user):
    """Ausencias y felicitaciones: exclusivo del Delegado (y del superusuario)."""
    return user.is_superuser or P.es_delegado(user)


def equipo_de(delegacion):
    """Funcionarios activos de la delegación que registran actividades. Se excluyen los
    administradores del sistema (rol con «Gestionar usuarios»): no son parte del equipo territorial."""
    candidatos = (User.objects.filter(is_active=True, perfil__delegaciones=delegacion)
                  .select_related('perfil__rol').distinct().order_by('first_name', 'last_name', 'username'))
    ids = [u.pk for u in candidatos
           if P.PERM_REGISTRAR in (u.perfil.rol.permisos or []) and P.PERM_USUARIOS not in (u.perfil.rol.permisos or [])]
    return candidatos.filter(pk__in=ids)


def _leer_trimestre(texto):
    """'2026-Q4' → (2026, 4). Sin valor: el trimestre actual."""
    if not texto:
        return M.trimestre_de(timezone.localdate())
    m = re.fullmatch(r'(\d{4})-Q([1-4])', texto.strip().upper())
    if not m:
        raise ErrorApi('fecha_invalida', 'trimestre')
    return int(m.group(1)), int(m.group(2))


def trimestres_disponibles():
    """Trimestres para el selector: desde el de la actividad más antigua hasta el actual."""
    hoy = timezone.localdate()
    primera = Atencion.objects.order_by('fecha').values_list('fecha', flat=True).first() or hoy
    lista = []
    anio, q = M.trimestre_de(hoy)
    inicio = min(M.trimestre_de(primera), (hoy.year, 1))  # al menos todo el año en curso
    while (anio, q) >= inicio and len(lista) < 20:
        desde, hasta = M.rango_trimestre(anio, q)
        lista.append({'valor': f'{anio}-Q{q}', 'nombre': M.nombre_trimestre(anio, q),
                      'desde': desde.isoformat(), 'hasta': hasta.isoformat()})
        anio, q = M.trimestre_anterior(anio, q)
    return lista


def _delegacion_de_equipo(user, pk, exigir_delegado=False):
    delegacion = P.delegaciones_de(user).filter(pk=pk).first()
    if delegacion is None:
        raise ErrorApi('prohibido', 'delegacionId', status=403)
    if exigir_delegado and not puede_gestionar_equipo(user):
        raise ErrorApi('solo_delegado', status=403)
    return delegacion


def serializar_ausencia(a):
    return {'id': a.pk, 'funcionarioId': a.funcionario_id, 'funcionario': P.nombre_visible(a.funcionario),
            'tipo': a.tipo, 'desde': a.desde.isoformat(), 'hasta': a.hasta.isoformat(),
            'observacion': a.observacion}


def serializar_felicitacion(f):
    return {'id': f.pk, 'funcionarioId': f.funcionario_id, 'funcionario': P.nombre_visible(f.funcionario),
            'delegacionId': f.delegacion_id, 'fecha': f.fecha.isoformat(), 'emisor': f.emisor,
            'motivo': f.motivo, 'respaldoTipo': f.respaldo_tipo, 'respaldoReferencia': f.respaldo_referencia,
            'registradaPor': P.nombre_visible(f.registrada_por) if f.registrada_por else ''}


@api_login_requerido
@con_errores
@require_http_methods(['GET'])
def matriz_equipo(request):
    """Avance de la matriz SGR del equipo de una delegación en un trimestre, con el sobrante
    que llega del trimestre anterior."""
    user = request.user
    delegaciones = list(P.delegaciones_de(user).filter(activo=True).order_by('nombre'))
    if not delegaciones:
        raise ErrorApi('sin_delegacion', status=403)
    pk = _leer_pk(request.GET, 'delegacion')
    delegacion = _delegacion_de_equipo(user, pk) if pk is not None else delegaciones[0]
    anio, q = _leer_trimestre(request.GET.get('trimestre'))
    desde, hasta = M.rango_trimestre(anio, q)
    hoy = timezone.localdate()

    items = list(ItemMeta.objects.filter(activo=True))
    miembros = list(equipo_de(delegacion))
    ausencias = list(Ausencia.objects.filter(funcionario__in=miembros, desde__lte=hasta, hasta__gte=desde)
                     .select_related('funcionario'))
    felicitaciones = list(Felicitacion.objects.filter(delegacion=delegacion, fecha__range=(desde, hasta))
                          .select_related('funcionario', 'registrada_por'))

    equipo = []
    por_item = {i.pk: {'itemId': i.pk, 'item': i.nombre, 'puntos': 0, 'arrastre': 0.0, 'total': 0.0, 'meta': 0.0}
                for i in items}
    for u in miembros:
        propias = [a for a in ausencias if a.funcionario_id == u.pk]
        factor, filas = M.resumen_funcionario(u, anio, q, items, propias)
        pts = sum(f['puntos'] for f in filas)
        extra = sum(f['arrastre'] for f in filas)
        meta = sum(f['meta'] for f in filas)
        valor = M.cumplimiento(pts + extra, meta) if filas else 0
        for f in filas:
            fila = por_item[f['itemId']]
            fila['puntos'] += f['puntos']
            fila['arrastre'] += f['arrastre']
            fila['total'] += f['total']
            fila['meta'] += f['meta']
        equipo.append({
            'id': u.pk, 'nombre': P.nombre_visible(u), 'cargo': u.perfil.rol.nombre,
            'disponibilidad': round(factor * 100),
            'diasAusente': M.dias_ausente(u, desde, hasta, propias),
            'ausenteHoy': any(a.desde <= hoy <= a.hasta for a in propias),
            'puntos': pts, 'arrastre': round(extra, 1), 'total': round(pts + extra, 1),
            'meta': round(meta, 1), 'cumplimiento': round(valor * 100),
            'semaforo': M.semaforo(valor), 'items': filas,
            'felicitaciones': sum(1 for f in felicitaciones if f.funcionario_id == u.pk),
        })

    items_equipo = []
    for fila in por_item.values():
        valor = M.cumplimiento(fila['total'], fila['meta'])
        items_equipo.append({**fila, 'arrastre': round(fila['arrastre'], 1), 'total': round(fila['total'], 1),
                             'meta': round(fila['meta'], 1), 'cumplimiento': round(valor * 100),
                             'semaforo': M.semaforo(valor)})

    total_pts = sum(f['puntos'] for f in items_equipo)
    total_arrastre = sum(f['arrastre'] for f in items_equipo)
    total_meta = sum(f['meta'] for f in items_equipo)
    avance = M.cumplimiento(total_pts + total_arrastre, total_meta) if items_equipo else 0
    pcts = [m['cumplimiento'] for m in equipo]
    brecha = (max(pcts) - min(pcts)) if pcts else 0
    return JsonResponse({
        'delegacion': {'id': delegacion.pk, 'nombre': delegacion.nombre},
        'delegaciones': [{'id': d.pk, 'nombre': d.nombre} for d in delegaciones],
        'trimestre': f'{anio}-Q{q}',
        'trimestreNombre': M.nombre_trimestre(anio, q),
        'trimestreAnterior': M.nombre_trimestre(*M.trimestre_anterior(anio, q)),
        'desde': desde.isoformat(), 'hasta': hasta.isoformat(),
        'trimestres': trimestres_disponibles(),
        'grupo': {
            'puntos': total_pts, 'arrastre': round(total_arrastre, 1),
            'total': round(total_pts + total_arrastre, 1),
            'meta': round(total_meta, 1), 'cumplimiento': round(avance * 100),
            'semaforo': M.semaforo(avance), 'brecha': brecha,
            'equilibrado': bool(pcts) and brecha <= 30 and min(pcts) >= M.AMARILLO * 100,
            'conteo': {c: sum(1 for m in equipo if m['semaforo'] == c) for c in ('verde', 'amarillo', 'rojo')},
        },
        'items': items_equipo,
        'equipo': equipo,
        'ausencias': [serializar_ausencia(a) for a in ausencias],
        'felicitaciones': [serializar_felicitacion(f) for f in felicitaciones],
        'puedeGestionar': puede_gestionar_equipo(user),
        'tiposAusencia': Ausencia.TIPOS,
        'tiposRespaldo': Felicitacion.RESPALDOS,
        'tope': round(M.TOPE * 100),
    })


def _leer_fecha_campo(datos, key):
    valor = datos.get(key)
    if not valor:
        raise ErrorApi('campo_vacio', key)
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise ErrorApi('fecha_invalida', key)


def _miembro(datos, delegacion):
    funcionario = leer_id(datos, 'funcionarioId', User)
    if not equipo_de(delegacion).filter(pk=funcionario.pk).exists():
        raise ErrorApi('referencia_invalida', 'funcionarioId')
    return funcionario


@api_login_requerido
@con_errores
@require_http_methods(['POST'])
def ausencias(request):
    datos = leer_json(request)
    delegacion = _delegacion_de_equipo(request.user, leer_id(datos, 'delegacionId', Delegacion).pk,
                                       exigir_delegado=True)
    funcionario = _miembro(datos, delegacion)
    tipo = datos.get('tipo')
    if not tipo:
        raise ErrorApi('campo_vacio', 'tipo')
    if tipo not in Ausencia.TIPOS:
        raise ErrorApi('referencia_invalida', 'tipo')
    desde = _leer_fecha_campo(datos, 'desde')
    hasta = _leer_fecha_campo(datos, 'hasta')
    if hasta < desde:
        raise ErrorApi('rango_invalido', 'hasta')
    if (hasta - desde).days > 366:
        raise ErrorApi('rango_invalido', 'hasta')
    if Ausencia.objects.filter(funcionario=funcionario, desde__lte=hasta, hasta__gte=desde).exists():
        raise ErrorApi('ausencia_traslapada', 'desde')
    observacion = (datos.get('observacion') or '').strip()
    if len(observacion) > 200:
        raise ErrorApi('texto_largo', 'observacion', '200')
    a = Ausencia.objects.create(funcionario=funcionario, tipo=tipo, desde=desde, hasta=hasta,
                                observacion=observacion, registrada_por=request.user)
    return JsonResponse(serializar_ausencia(a), status=201)


@api_login_requerido
@con_errores
@require_http_methods(['DELETE'])
def ausencia_detalle(request, pk):
    if not puede_gestionar_equipo(request.user):
        raise ErrorApi('solo_delegado', status=403)
    a = Ausencia.objects.filter(pk=pk, funcionario__perfil__delegaciones__in=P.delegaciones_de(request.user)).first()
    if a is None:
        raise ErrorApi('no_encontrado', status=404)
    a.delete()
    return JsonResponse({'ok': True})


RESPALDO_INFORMAL_RE = re.compile(r'whats|wsp|wasap|telegram|chat|instagram|facebook|messenger|sms', re.I)


@api_login_requerido
@con_errores
@require_http_methods(['POST'])
def felicitaciones(request):
    datos = leer_json(request)
    delegacion = _delegacion_de_equipo(request.user, leer_id(datos, 'delegacionId', Delegacion).pk,
                                       exigir_delegado=True)
    funcionario = _miembro(datos, delegacion)
    fecha = _leer_fecha_campo(datos, 'fecha')
    if fecha > timezone.localdate():
        raise ErrorApi('fecha_futura', 'fecha')
    emisor = leer_texto(datos, 'emisor', 150)
    motivo = leer_texto(datos, 'motivo')
    respaldo_tipo = datos.get('respaldoTipo')
    if not respaldo_tipo:
        raise ErrorApi('campo_vacio', 'respaldoTipo')
    if respaldo_tipo not in Felicitacion.RESPALDOS:
        raise ErrorApi('respaldo_informal', 'respaldoTipo')
    referencia = leer_texto(datos, 'respaldoReferencia', 120)
    if len(referencia) < 4:
        raise ErrorApi('campo_vacio', 'respaldoReferencia')
    if RESPALDO_INFORMAL_RE.search(referencia):
        raise ErrorApi('respaldo_informal', 'respaldoReferencia')
    f = Felicitacion.objects.create(funcionario=funcionario, delegacion=delegacion, fecha=fecha, emisor=emisor,
                                    motivo=motivo, respaldo_tipo=respaldo_tipo, respaldo_referencia=referencia,
                                    registrada_por=request.user)
    return JsonResponse(serializar_felicitacion(f), status=201)
