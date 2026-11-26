"""Manejador de excepciones propio de la API REST (/api/v1/).

Todas las respuestas de error tienen el mismo formato, sin trazas internas:

    {"error": "<caso>", "campo": "<campo o null>", "detalle": "<texto>"}

- Los errores de negocio (dashboard.api.ErrorApi) se convierten directamente con su status,
  así la API REST y la API web responden los mismos casos ("campo_vacio", "rut_invalido", ...).
- Los errores propios de DRF (401, 403, 404, 405, 429...) se traducen al mismo formato.
- Cualquier error inesperado responde 500 genérico y se registra en el log del servidor.
"""
import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.http import Http404
from rest_framework import exceptions as drf
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from dashboard.api import ErrorApi

log = logging.getLogger('sgrApi')

# Casos de negocio que en la API REST son un conflicto con lo ya guardado (409) y no un dato mal escrito.
CASOS_CONFLICTO = {'duplicado'}


def cuerpo_error(caso, campo=None, detalle=''):
    return {'error': caso, 'campo': campo, 'detalle': detalle}


def _primer_mensaje(detalle):
    """Primer texto de un detalle de DRF (puede venir como lista o diccionario anidado)."""
    if isinstance(detalle, dict):
        for valor in detalle.values():
            return _primer_mensaje(valor)
        return ''
    if isinstance(detalle, (list, tuple)):
        return _primer_mensaje(detalle[0]) if detalle else ''
    return str(detalle)


def _desde_validacion(exc):
    """ValidationError de un serializer → campo con el primer error y su mensaje."""
    detalle = exc.detail
    campo = None
    if isinstance(detalle, dict) and detalle:
        campo = next(iter(detalle))
        if campo == 'non_field_errors':
            campo = None
    return cuerpo_error('datos_invalidos', campo, _primer_mensaje(detalle))


def manejador_excepciones(exc, context):
    # 1) Reglas de negocio del sistema (las mismas de la web).
    if isinstance(exc, ErrorApi):
        estado = status.HTTP_409_CONFLICT if exc.caso in CASOS_CONFLICTO else exc.status
        return Response(cuerpo_error(exc.caso, exc.campo, exc.detalle), status=estado)

    # 2) Errores de base de datos que significan "conflicto con datos existentes".
    if isinstance(exc, ProtectedError):
        return Response(cuerpo_error('en_uso', None, 'El registro está siendo usado por otros registros.'),
                        status=status.HTTP_409_CONFLICT)
    if isinstance(exc, IntegrityError):
        return Response(cuerpo_error('conflicto', None, 'Los datos chocan con un registro existente.'),
                        status=status.HTTP_409_CONFLICT)

    # 3) Excepciones de Django que DRF también entiende.
    if isinstance(exc, Http404):
        exc = drf.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = drf.PermissionDenied()

    respuesta = exception_handler(exc, context)
    if respuesta is None:
        # 4) Error no previsto: 500 sin detalles internos (la traza queda solo en el log).
        log.exception('Error no controlado en la API REST')
        return Response(cuerpo_error('error_interno', None, 'Ocurrió un error inesperado. Intenta nuevamente.'),
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if isinstance(exc, drf.ValidationError):
        cuerpo = _desde_validacion(exc)
    elif isinstance(exc, (drf.NotAuthenticated, drf.AuthenticationFailed)):
        # Incluye InvalidToken de simplejwt (token vencido, mal formado o en lista negra).
        codigo = exc.get_codes()
        if isinstance(codigo, dict):  # InvalidToken trae {"detail": ..., "code": ..., "messages": ...}
            codigo = codigo.get('code', '')
        codigo = str(codigo[0] if isinstance(codigo, list) and codigo else codigo)
        if codigo in ('token_not_valid', 'user_not_found', 'user_inactive'):
            cuerpo = cuerpo_error('token_invalido', None, 'El token no es válido o ya expiró.')
        elif codigo == 'no_active_account':
            cuerpo = cuerpo_error('credenciales_invalidas', None, 'Usuario o contraseña incorrectos.')
        else:
            cuerpo = cuerpo_error('no_autenticado', None, 'Debes enviar un token de acceso válido.')
        respuesta.status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, drf.PermissionDenied):
        cuerpo = cuerpo_error('prohibido', None, 'Tu rol no tiene permiso para esta acción.')
    elif isinstance(exc, drf.NotFound):
        cuerpo = cuerpo_error('no_encontrado', None, 'El recurso solicitado no existe.')
    elif isinstance(exc, drf.MethodNotAllowed):
        cuerpo = cuerpo_error('metodo_no_permitido', None, _primer_mensaje(exc.detail))
    elif isinstance(exc, drf.Throttled):
        cuerpo = cuerpo_error('demasiadas_solicitudes', None,
                              f'Espera {exc.wait or 0:.0f} segundos antes de reintentar.')
    elif isinstance(exc, drf.ParseError):
        cuerpo = cuerpo_error('json_invalido', None, 'El cuerpo de la solicitud no es un JSON válido.')
    elif isinstance(exc, drf.UnsupportedMediaType):
        cuerpo = cuerpo_error('formato_no_soportado', None, 'Envía los datos como application/json.')
    else:
        cuerpo = cuerpo_error(getattr(exc, 'default_code', 'error'), None, _primer_mensaje(exc.detail))

    respuesta.data = cuerpo
    return respuesta
