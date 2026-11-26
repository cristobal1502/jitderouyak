"""Vistas de la API REST /api/v1/ (Django REST Framework).

Cada recurso es un ModelViewSet que expone solo GET, POST, PUT y DELETE (PATCH queda
deshabilitado con http_method_names y responde 405):

    GET    /api/v1/<recurso>/        listar (paginado)            200
    POST   /api/v1/<recurso>/        crear                         201
    GET    /api/v1/<recurso>/<id>/   detalle                       200
    PUT    /api/v1/<recurso>/<id>/   reemplazar                    200
    DELETE /api/v1/<recurso>/<id>/   eliminar                      204

Reparto del trabajo (2 personas):
    Persona 1: DelegacionViewSet, TipoAtencionViewSet  + transacción AtencionViewSet
    Persona 2: ItemMetaViewSet, OrganizacionViewSet    + transacción ReclamoViewSet
"""
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView, TokenRefreshView

from dashboard import api as reglas
from dashboard import permisos as P
from dashboard.models import Atencion, Reclamo

from . import serializers as S
from .permissions import PermisoDelRol, SoloDelegadoEscribe, es_administrador

METODOS = ['get', 'post', 'put', 'delete', 'head', 'options']  # sin PATCH


class Paginacion(PageNumberPagination):
    """?page=2&tamano=50 (máximo 100 por página)."""
    page_size = 20
    page_size_query_param = 'tamano'
    max_page_size = 100


# ====================================================== documentación (Swagger)
def _error(descripcion, *ejemplos):
    """Respuesta de error documentada con uno o más ejemplos (caso, campo, detalle)."""
    return OpenApiResponse(S.ErrorSerializer, description=descripcion, examples=[
        OpenApiExample(caso, value={'error': caso, 'campo': campo, 'detalle': detalle}, response_only=True)
        for caso, campo, detalle in ejemplos])


E401 = _error('Sin token, o token inválido / expirado.',
              ('no_autenticado', None, 'Debes enviar un token de acceso válido.'),
              ('token_invalido', None, 'El token no es válido o ya expiró.'))
E403 = _error('Tu rol no tiene el permiso necesario.',
              ('prohibido', None, 'Tu rol no tiene permiso para esta acción.'))
E404 = _error('No existe, o tu rol no puede verlo.',
              ('no_encontrado', None, 'El recurso solicitado no existe.'))
E409_EN_USO = _error('No se puede eliminar porque otros registros lo usan, o el código ya existe.',
                     ('en_uso', None, '3 atención(es)'), ('duplicado', 'codigo', ''))
E409_DUPLICADO = _error('El código ya existe.', ('duplicado', 'codigo', ''))


def documentar(tag, singular, plural, serializer, entrada, salida, errores_400, extra=None,
               nota_lectura='', nota_escritura='', e409_borrar=E409_EN_USO):
    """Arma la documentación de las 5 acciones de un ViewSet (summary, description, respuestas y ejemplos)."""
    extra = extra or {}
    ej_entrada = OpenApiExample('Ejemplo', value=entrada, request_only=True)
    ej_salida = OpenApiExample('Ejemplo', value=salida, response_only=True)
    e400 = _error('Datos inválidos (mismas reglas que la aplicación web).', *errores_400)
    borrar = {204: OpenApiResponse(description='Eliminado, sin contenido.'), 401: E401, 403: E403, 404: E404}
    if e409_borrar is not None:
        borrar[409] = e409_borrar
    return extend_schema_view(
        list=extend_schema(tags=[tag], summary=f'Listar {plural}',
                           description=f'Lista paginada de {plural}. {nota_lectura}',
                           responses={200: serializer, 401: E401, 403: E403}, examples=[ej_salida],
                           **extra.get('list', {})),
        retrieve=extend_schema(tags=[tag], summary=f'Ver {singular}', description=nota_lectura,
                               responses={200: serializer, 401: E401, 403: E403, 404: E404},
                               examples=[ej_salida]),
        create=extend_schema(tags=[tag], summary=f'Crear {singular}', description=nota_escritura,
                             request=serializer, examples=[ej_entrada, ej_salida],
                             responses={201: serializer, 400: e400, 401: E401, 403: E403,
                                        409: E409_DUPLICADO}),
        update=extend_schema(tags=[tag], summary=f'Reemplazar {singular} (PUT)',
                             description=f'Se envían todos los campos. {nota_escritura}',
                             request=serializer, examples=[ej_entrada, ej_salida],
                             responses={200: serializer, 400: e400, 401: E401, 403: E403, 404: E404,
                                        409: extra.get('e409_update', E409_DUPLICADO)}),
        destroy=extend_schema(tags=[tag], summary=f'Eliminar {singular}',
                              description=extra.get('nota_borrar', ''),
                              responses=borrar),
    )


NOTA_SENSIBLE = ('El administrador recibe la vista completa; el resto de los roles recibe la vista básica, '
                 'sin datos sensibles (RUT, teléfonos). Los campos sensibles se pueden enviar, pero no se leen.')


# ====================================================== base de los ViewSets
class BaseViewSet(viewsets.ModelViewSet):
    http_method_names = METODOS
    permission_classes = [IsAuthenticated, PermisoDelRol]
    pagination_class = Paginacion
    lookup_value_regex = r'\d+'  # los id son números
    permiso_lectura = None     # None = cualquier usuario autenticado
    permiso_escritura = None
    serializer_completo = None
    serializer_basico = None   # None = el mismo para todos

    def get_serializer_class(self):
        """Serializer según el perfil: completo para el administrador, básico para el resto."""
        if (self.serializer_basico is None or getattr(self, 'swagger_fake_view', False)
                or es_administrador(self.request.user)):
            return self.serializer_completo
        return self.serializer_basico


class RecursoViewSet(BaseViewSet):
    """Mantenedores que reutilizan un Recurso de dashboard/api.py (consulta, usos y borrado)."""
    recurso = None

    def get_queryset(self):
        return self.recurso.consulta()

    def perform_destroy(self, obj):
        self.recurso.puede_eliminar(obj, self.request)   # p. ej. organización de otra delegación → 403
        usos = self.recurso.usos(obj)
        if usos:
            raise reglas.ErrorApi('en_uso', detalle=' y '.join(usos), status=409)
        self.recurso.borrar(obj, self.request)  # si igual choca con un PROTECT → 409 en el manejador


# ====================================================== PERSONA 1
@documentar(
    'Delegaciones', 'una delegación', 'delegaciones', S.DelegacionSerializer,
    entrada={'codigo': 'DEL-005', 'nombre': 'La Herradura', 'direccion': 'Av. Costanera 100',
             'comuna': 'Coquimbo', 'estado': 'Activo'},
    salida={'id': 5, 'codigo': 'DEL-005', 'nombre': 'La Herradura', 'direccion': 'Av. Costanera 100',
            'comuna': 'Coquimbo', 'estado': 'Activo'},
    errores_400=[('campo_vacio', 'nombre', ''), ('texto_largo', 'comuna', '80')],
    nota_lectura='Cualquier usuario autenticado.',
    nota_escritura='Requiere el permiso «Administrar catálogos».',
    extra={'nota_borrar': 'Responde 409 si tiene usuarios, atenciones u organizaciones asociadas.'},
)
class DelegacionViewSet(RecursoViewSet):
    """Mantenedor de delegaciones territoriales."""
    recurso = reglas.RECURSOS['delegaciones']
    serializer_completo = S.DelegacionSerializer
    permiso_escritura = P.PERM_CATALOGOS


@documentar(
    'Tipos de atención', 'un tipo de atención', 'tipos de atención', S.TipoAtencionSerializer,
    entrada={'nombre': 'Orientación legal', 'descripcion': 'Orientación sobre trámites y derechos.',
             'estado': 'Activo'},
    salida={'id': 5, 'codigo': 'TAT-005', 'nombre': 'Orientación legal',
            'descripcion': 'Orientación sobre trámites y derechos.', 'estado': 'Activo'},
    errores_400=[('campo_vacio', 'descripcion', ''), ('referencia_invalida', 'estado', '')],
    nota_lectura='Cualquier usuario autenticado.',
    nota_escritura='Requiere el permiso «Administrar catálogos». Si no se envía código se genera TAT-00N.',
    extra={'nota_borrar': 'Responde 409 si tiene sub atenciones o atenciones asociadas.'},
)
class TipoAtencionViewSet(RecursoViewSet):
    """Mantenedor de tipos de atención."""
    recurso = reglas.RECURSOS['tipos-atencion']
    serializer_completo = S.TipoAtencionSerializer
    permiso_escritura = P.PERM_CATALOGOS


EJ_ATENCION = {'solicitante': 'Rosa Álvarez', 'rut': '10.234.567-3', 'telefono': '+56 9 6001 4001',
               'tipoId': 1, 'subId': 1, 'itemId': 1, 'estado': 'Ejecutada',
               'descripcion': 'Orientación para postular al subsidio municipal.',
               'delegacionId': 1, 'responsableId': 2, 'fecha': '2026-11-26'}


@documentar(
    'Atenciones', 'una atención', 'atenciones', S.AtencionSerializer,
    entrada=EJ_ATENCION,
    salida={'id': 12, 'codigo': 'AT-012', **{k: v for k, v in EJ_ATENCION.items()},
            'clasificacion': 'Atención ciudadana', 'tipoNombre': 'Atención inicial', 'subNombre': 'Ficha FIBE',
            'itemNombre': 'Atención social', 'delegacionNombre': 'Coquimbo Centro',
            'responsableNombre': 'Juan Pérez', 'beneficiario': 'Persona natural', 'organizacionId': None,
            'organizacionNombre': '', 'fechaCompromiso': '2026-12-03', 'etapa': 'Realizado',
            'ejecutadaEl': '2026-11-26', 'puntaje': 1, 'topeAlcanzado': False, 'vencido': False,
            'alerta': None},
    errores_400=[('telefono_invalido', 'telefono', ''), ('sub_no_corresponde', 'subId', ''),
                 ('fecha_futura', 'fecha', ''), ('limite_diario', 'fecha', '7'),
                 ('semana_cerrada', 'fecha', '2026-11-16')],
    nota_lectura=('Según el alcance del rol: «Propio» ve las suyas, «Delegación» las de sus delegaciones y '
                  '«Todas las delegaciones» todas. ' + NOTA_SENSIBLE),
    nota_escritura=('Requiere «Registrar actividades». Máximo 7 actividades por funcionario al día, y solo '
                    'fechas de semanas abiertas (hasta el lunes siguiente). El puntaje (tope 120% del ítem) '
                    'se calcula solo. Al editar: no se puede devolver una Ejecutada a Preparación (409) ni '
                    'editar una de semana cerrada (409).'),
    extra={'nota_borrar': 'Solo si su semana no está cerrada (409 en otro caso).',
           'e409_update': _error('Semana cerrada, o se intentó devolver una Ejecutada a Preparación.',
                                 ('semana_cerrada', 'fecha', '2026-11-16'),
                                 ('ya_ejecutada', 'estado', 'Una actividad ejecutada no puede volver a Preparación.'))},
    e409_borrar=_error('La semana de la actividad ya está cerrada.', ('semana_cerrada', 'fecha', '2026-11-16')),
)
class AtencionViewSet(BaseViewSet):
    """Transacción: registro de atenciones / actividades (suman puntaje a la Matriz SGR)."""
    serializer_completo = S.AtencionSerializer
    serializer_basico = S.AtencionBasicaSerializer
    permiso_escritura = P.PERM_REGISTRAR

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):  # generación del esquema (sin usuario real)
            return Atencion.objects.none()
        return reglas.atenciones_visibles(self.request.user)

    def perform_destroy(self, atencion):
        limite = reglas.limite_ingreso(atencion.fecha)
        if timezone.localdate() > limite:
            raise reglas.ErrorApi('semana_cerrada', 'fecha', limite.isoformat(), status=409)
        atencion.delete()


# ====================================================== PERSONA 2
@documentar(
    'Ítems y metas', 'un ítem', 'ítems y metas', S.ItemMetaSerializer,
    entrada={'nombre': 'Visitas a dirigentes', 'descripcion': 'Reuniones con juntas de vecinos.',
             'metaTrimestral': 30, 'estado': 'Activo'},
    salida={'id': 5, 'codigo': 'ITM-005', 'nombre': 'Visitas a dirigentes',
            'descripcion': 'Reuniones con juntas de vecinos.', 'metaTrimestral': 30, 'estado': 'Activo'},
    errores_400=[('campo_vacio', 'metaTrimestral', ''), ('numero_invalido', 'metaTrimestral', '')],
    nota_lectura='Cualquier usuario autenticado.',
    nota_escritura='Requiere «Administrar catálogos». La meta trimestral va de 1 a 1500.',
    extra={'nota_borrar': 'Responde 409 si hay atenciones que suman a este ítem.'},
)
class ItemMetaViewSet(RecursoViewSet):
    """Mantenedor de ítems de la Matriz SGR con su meta trimestral."""
    recurso = reglas.RECURSOS['items']
    serializer_completo = S.ItemMetaSerializer
    permiso_escritura = P.PERM_CATALOGOS


EJ_DIRECTIVA = {'presidente': {'nombre': 'Rosa Álvarez', 'rut': '10.234.567-3', 'telefono': '+56 9 6001 4001'},
                'tesorero': {'nombre': 'Pedro Contreras', 'rut': '11.345.678-7', 'telefono': '+56 9 6002 4002'},
                'secretario': {'nombre': 'Lucía Rivas', 'rut': '12.456.789-0', 'telefono': '+56 9 6003 4003'}}
EJ_ORGANIZACION = {'nombre': 'Club Deportivo El Faro', 'tipo': 'Funcional',
                   'subcategoria': 'Organización Deportiva', 'delegacionId': 1, 'sector': 'Coquimbo Centro',
                   'directiva': EJ_DIRECTIVA, 'telefono': '+56 9 5555 7777',
                   'verificacion': 'Pendiente de revisión', 'estado': 'Activo'}


@documentar(
    'Organizaciones comunitarias', 'una organización', 'organizaciones comunitarias', S.OrganizacionSerializer,
    entrada=EJ_ORGANIZACION,
    salida={'id': 7, 'codigo': 'ORG-007', **EJ_ORGANIZACION, 'delegacionNombre': 'Coquimbo Centro'},
    errores_400=[('rut_invalido', 'directiva.presidente.rut', ''), ('rut_repetido', 'directiva.tesorero.rut', ''),
                 ('campo_vacio', 'subcategoria', '')],
    nota_lectura='Cualquier usuario autenticado. ' + NOTA_SENSIBLE +
                 ' En la vista básica la directiva muestra solo los nombres.',
    nota_escritura=('Requiere «Administrar catálogos» o «Gestionar organizaciones», y solo en tus delegaciones '
                    '(403 en otro caso). La directiva exige nombre, RUT válido y teléfono para los 3 cargos.'),
    extra={'nota_borrar': 'Solo organizaciones de tus delegaciones.'},
)
class OrganizacionViewSet(RecursoViewSet):
    """Mantenedor de organizaciones comunitarias (juntas de vecinos y funcionales)."""
    recurso = reglas.RECURSOS['organizaciones']
    serializer_completo = S.OrganizacionSerializer
    serializer_basico = S.OrganizacionBasicaSerializer
    permiso_escritura = (P.PERM_CATALOGOS, P.PERM_ORGANIZACIONES)


EJ_RECLAMO = {'delegacionId': 1, 'funcionarioId': 2, 'itemId': 2, 'fecha': '2026-11-20',
              'reclamante': 'Vecino del sector', 'motivo': 'No se presentó a la visita acordada.',
              'respaldoTipo': 'Carta firmada', 'respaldoReferencia': 'Carta folio 2026-200', 'puntos': 1}


@documentar(
    'Reclamos', 'un reclamo', 'reclamos', S.ReclamoSerializer,
    entrada=EJ_RECLAMO,
    salida={'id': 3, **EJ_RECLAMO, 'funcionario': 'Juan Pérez', 'item': 'Operativos en terreno',
            'registradoPor': 'María Rojas'},
    errores_400=[('respaldo_informal', 'respaldoReferencia', ''), ('numero_invalido', 'puntos', ''),
                 ('referencia_invalida', 'funcionarioId', '')],
    nota_lectura=('El Delegado ve los reclamos de sus delegaciones; el administrador ve todos; el resto solo '
                  've los reclamos en su contra, sin el nombre del reclamante ni la referencia del respaldo.'),
    nota_escritura=('Solo el Delegado (403 para el resto), en sus delegaciones y contra un funcionario de su '
                    'equipo. Descuenta de 1 a 5 puntos del ítem en el trimestre de la fecha. Exige respaldo '
                    'formal: carta, correo formal, oficio o libro (no chats).'),
    extra={'nota_borrar': 'Solo el Delegado. Al eliminar el reclamo se devuelven los puntos descontados.'},
    e409_borrar=None,
)
class ReclamoViewSet(BaseViewSet):
    """Transacción: reclamos contra funcionarios (descuentan puntos de la Matriz SGR)."""
    serializer_completo = S.ReclamoSerializer
    serializer_basico = S.ReclamoBasicoSerializer
    permission_classes = [IsAuthenticated, SoloDelegadoEscribe]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Reclamo.objects.none()
        user = self.request.user
        qs = Reclamo.objects.select_related('funcionario', 'item', 'registrado_por', 'delegacion')
        if reglas.puede_gestionar_equipo(user):
            return qs.filter(delegacion__in=P.delegaciones_de(user))
        if es_administrador(user):
            return qs
        return qs.filter(funcionario=user)

    def get_serializer_class(self):
        if (getattr(self, 'swagger_fake_view', False) or es_administrador(self.request.user)
                or reglas.puede_gestionar_equipo(self.request.user)):
            return self.serializer_completo
        return self.serializer_basico



# ====================================================== sesión y utilidades
@extend_schema(tags=['Sesión'], summary='¿Quién soy?',
               description='Usuario del token, su rol, alcance, permisos y si ve como administrador.',
               responses={200: S.YoSerializer, 401: E401},
               examples=[OpenApiExample('Funcionario', response_only=True, value={
                   'id': 2, 'usuario': 'juan.perez', 'nombre': 'Juan Pérez', 'rol': 'Funcionario',
                   'perfil': 'administrativo', 'alcance': 'Propio', 'permisos': ['Ver panel', 'Registrar actividades'],
                   'delegaciones': [{'id': 1, 'nombre': 'Coquimbo Centro'}],
                   'esAdministrador': False, 'esDelegado': False})])
class YoView(APIView):
    def get(self, request):
        user = request.user
        perfil = P.perfil_de(user)
        datos = {
            'id': user.pk, 'usuario': user.username, 'nombre': P.nombre_visible(user),
            'rol': perfil.rol.nombre if perfil else ('Superusuario' if user.is_superuser else None),
            'perfil': P.tipo_dashboard(user), 'alcance': P.alcance_de(user),
            'permisos': list(P.PERMISOS) if user.is_superuser else (list(perfil.rol.permisos) if perfil else []),
            'delegaciones': [{'id': d.pk, 'nombre': d.nombre} for d in P.delegaciones_de(user).order_by('codigo')],
            'esAdministrador': es_administrador(user),
            'esDelegado': reglas.puede_gestionar_equipo(user),
        }
        return Response(S.YoSerializer(datos).data)


CREDENCIALES = OpenApiExample('Usuario demo', request_only=True,
                              value={'username': 'juan.perez', 'password': 'Demo1234!'})
E401_LOGIN = _error('Usuario o contraseña incorrectos (o cuenta inactiva).',
                    ('credenciales_invalidas', None, 'Usuario o contraseña incorrectos.'))
E429 = _error('Demasiados intentos: se limita el número de solicitudes por minuto.',
              ('demasiadas_solicitudes', None, 'Espera 42 segundos antes de reintentar.'))


@extend_schema(tags=['Autenticación'], summary='Obtener token (login)',
               description=('Entrega un token de acceso (15 minutos) y uno de refresco (1 día). '
                            'Copia el valor de "access" y pégalo en el botón Authorize.'),
               examples=[CREDENCIALES, OpenApiExample('Tokens', response_only=True,
                                                      value={'refresh': 'eyJhbGciOi...', 'access': 'eyJhbGciOi...'})],
               responses={200: OpenApiResponse(description='Par de tokens JWT.'), 400: _error(
                   'Falta usuario o contraseña.', ('datos_invalidos', 'username', 'Este campo es requerido.')),
                   401: E401_LOGIN, 429: E429})
class TokenObtenerView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token'


@extend_schema(tags=['Autenticación'], summary='Renovar token',
               description=('Entrega un nuevo token de acceso. Con rotación activada también entrega un refresh '
                            'nuevo y el anterior queda en lista negra (no se puede volver a usar).'),
               responses={200: OpenApiResponse(description='Nuevo par de tokens.'), 401: E401, 429: E429})
class TokenRenovarView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token'


@extend_schema(tags=['Autenticación'], summary='Cerrar sesión (logout)',
               description='Pone el token de refresco en lista negra: ya no sirve para renovar el acceso.',
               examples=[OpenApiExample('Logout', request_only=True, value={'refresh': 'eyJhbGciOi...'})],
               responses={204: OpenApiResponse(description='Sesión cerrada.'), 401: E401})
class LogoutView(TokenBlacklistView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token'

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)  # lanza 401 si el refresh no es válido
        return Response(status=status.HTTP_204_NO_CONTENT)


class RutaNoEncontrada(APIView):
    """Cualquier ruta inexistente bajo /api/v1/ responde 404 en JSON (y no la página HTML de Django)."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []
    schema = None  # no aparece en Swagger

    def responder(self, request, *args, **kwargs):
        raise NotFound()

    get = post = put = patch = delete = head = options = responder

