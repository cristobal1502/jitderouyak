"""Serializers de la API REST.

Cómo funcionan (importante para entender la API):

1. SALIDA: los campos declarados en cada serializer definen el JSON que se responde
   (mismos nombres camelCase que la API web: tipoId, subId, delegacionId, estado "Activo"...).
   Swagger también usa estos campos para documentar la API.

2. ENTRADA: la validación NO se reescribe aquí. 'to_internal_value' llama a las mismas
   funciones de dashboard/api.py que usa la web (Recurso.validar, _validar_atencion,
   validar_reclamo). Así hay una sola fuente de verdad: si una regla cambia, cambia en ambas.
   Esas funciones lanzan ErrorApi, que sgrApi/excepciones.py convierte en JSON con su status.

3. DATOS SENSIBLES: cada recurso tiene un serializer COMPLETO (administrador) y uno BÁSICO
   (resto de los usuarios). En el básico, el RUT y los teléfonos son write_only: el funcionario
   los puede ENVIAR al registrar, pero nunca los LEE en las respuestas. La vista elige cuál usar
   en get_serializer_class().
"""
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from dashboard import api as reglas
from dashboard import matriz as M
from dashboard import permisos as P
from dashboard.models import Atencion, Felicitacion, OrganizacionComunitaria, Reclamo

ESTADOS = ['Activo', 'Inactivo']


class EstadoField(serializers.ChoiceField):
    """Muestra el booleano 'activo' del modelo como "Activo" / "Inactivo"."""

    def __init__(self, **kwargs):
        kwargs.setdefault('source', 'activo')
        kwargs.setdefault('required', False)
        kwargs.setdefault('help_text', 'Activo o Inactivo (por defecto Activo).')
        super().__init__(choices=ESTADOS, **kwargs)

    def to_representation(self, value):
        return reglas.estado_txt(value)


class ErrorSerializer(serializers.Serializer):
    """Formato uniforme de todas las respuestas de error (solo para la documentación)."""
    error = serializers.CharField(help_text='Código del caso, p. ej. "campo_vacio", "prohibido", "en_uso".')
    campo = serializers.CharField(allow_null=True, help_text='Campo que provocó el error, o null.')
    detalle = serializers.CharField(help_text='Explicación o dato adicional.')


class ReglasDeNegocioSerializer(serializers.Serializer):
    """Base: la validación de entrada la hacen las reglas de dashboard/api.py."""

    @property
    def usuario(self):
        return self.context['request'].user

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise reglas.ErrorApi('json_invalido', detalle='Se esperaba un objeto JSON.')
        return self.validar_negocio(data)

    def validar_negocio(self, datos):
        raise NotImplementedError


class RecursoSerializer(ReglasDeNegocioSerializer):
    """Para los mantenedores que ya existen como 'Recurso' en dashboard/api.py
    (Delegaciones, Tipos de atención, Ítems y Organizaciones): reutiliza su
    validar / crear / actualizar."""
    recurso = None  # instancia de dashboard.api.Recurso

    def validar_negocio(self, datos):
        return self.recurso.validar(datos, self.instance, self.context['request'])

    def create(self, validated_data):
        try:
            return self.recurso.crear(validated_data, self.context['request'])
        except IntegrityError:
            raise reglas.ErrorApi('duplicado', 'codigo', status=409)

    def update(self, instance, validated_data):
        try:
            return self.recurso.actualizar(instance, validated_data, self.context['request'])
        except IntegrityError:
            raise reglas.ErrorApi('duplicado', 'codigo', status=409)


# ======================================================== PERSONA 1: mantenedores
class DelegacionSerializer(RecursoSerializer):
    recurso = reglas.RECURSOS['delegaciones']

    id = serializers.IntegerField(read_only=True)
    codigo = serializers.CharField(required=False, max_length=20,
                                   help_text='Opcional al crear: si se omite se genera DEL-00N.')
    nombre = serializers.CharField(max_length=120)
    direccion = serializers.CharField(max_length=200)
    comuna = serializers.CharField(max_length=80)
    estado = EstadoField()


class TipoAtencionSerializer(RecursoSerializer):
    recurso = reglas.RECURSOS['tipos-atencion']

    id = serializers.IntegerField(read_only=True)
    codigo = serializers.CharField(required=False, max_length=20,
                                   help_text='Opcional al crear: si se omite se genera TAT-00N.')
    nombre = serializers.CharField(max_length=120)
    descripcion = serializers.CharField()
    estado = EstadoField()


# ======================================================== PERSONA 2: mantenedores
class ItemMetaSerializer(RecursoSerializer):
    recurso = reglas.RECURSOS['items']

    id = serializers.IntegerField(read_only=True)
    codigo = serializers.CharField(required=False, max_length=20,
                                   help_text='Opcional al crear: si se omite se genera ITM-00N.')
    nombre = serializers.CharField(max_length=120)
    descripcion = serializers.CharField()
    metaTrimestral = serializers.IntegerField(source='meta_trimestral', min_value=1, max_value=1500,
                                              help_text='Puntos esperados por funcionario en el trimestre.')
    estado = EstadoField()


class PersonaDirectivaSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    rut = serializers.CharField(max_length=12, help_text='Con dígito verificador, p. ej. 12.345.678-5.')
    telefono = serializers.CharField(max_length=30)


class PersonaDirectivaBasicaSerializer(PersonaDirectivaSerializer):
    # Sensibles: se pueden enviar, pero no se muestran a quien no es administrador.
    rut = serializers.CharField(max_length=12, write_only=True)
    telefono = serializers.CharField(max_length=30, write_only=True)


class _DirectivaDesdeModelo:
    """La directiva está guardada en 9 columnas (presidente_nombre, presidente_rut, ...):
    aquí se arma el objeto {presidente: {...}, tesorero: {...}, secretario: {...}}."""

    def to_representation(self, org):
        return {cargo: self.fields[cargo].to_representation({
            'nombre': getattr(org, f'{cargo}_nombre'),
            'rut': getattr(org, f'{cargo}_rut'),
            'telefono': getattr(org, f'{cargo}_telefono'),
        }) for cargo, _ in OrganizacionComunitaria.CARGOS}


class DirectivaSerializer(_DirectivaDesdeModelo, serializers.Serializer):
    presidente = PersonaDirectivaSerializer()
    tesorero = PersonaDirectivaSerializer()
    secretario = PersonaDirectivaSerializer()


class DirectivaBasicaSerializer(_DirectivaDesdeModelo, serializers.Serializer):
    presidente = PersonaDirectivaBasicaSerializer()
    tesorero = PersonaDirectivaBasicaSerializer()
    secretario = PersonaDirectivaBasicaSerializer()


class OrganizacionSerializer(RecursoSerializer):
    """Vista completa (administrador): incluye RUT y teléfono de la directiva."""
    recurso = reglas.RECURSOS['organizaciones']

    id = serializers.IntegerField(read_only=True)
    codigo = serializers.CharField(required=False, max_length=20,
                                   help_text='Opcional al crear: si se omite se genera ORG-00N.')
    nombre = serializers.CharField(max_length=150)
    tipo = serializers.ChoiceField(choices=[t for t, _ in OrganizacionComunitaria.TIPOS])
    subcategoria = serializers.ChoiceField(choices=OrganizacionComunitaria.SUBCATEGORIAS, required=False,
                                           allow_blank=True, help_text='Obligatoria solo si el tipo es Funcional.')
    delegacionId = serializers.IntegerField(source='delegacion_id',
                                            help_text='Debe ser una de las delegaciones del usuario.')
    delegacionNombre = serializers.CharField(source='delegacion.nombre', read_only=True)
    sector = serializers.CharField(max_length=120)
    directiva = DirectivaSerializer(source='*', help_text='Presidente, tesorero y secretario (tres RUT distintos).')
    telefono = serializers.CharField(required=False, allow_blank=True, max_length=30,
                                     help_text='Teléfono de contacto de la organización (opcional).')
    verificacion = serializers.ChoiceField(choices=[v for v, _ in OrganizacionComunitaria.VERIFICACIONES],
                                           required=False)
    estado = EstadoField()


class OrganizacionBasicaSerializer(OrganizacionSerializer):
    """Vista básica: la directiva muestra solo los nombres (sin RUT ni teléfonos)."""
    directiva = DirectivaBasicaSerializer(source='*')


# ======================================================== PERSONA 1: transacción Atenciones
class AtencionSerializer(ReglasDeNegocioSerializer):
    """Vista completa (administrador): incluye RUT y teléfono del vecino."""
    id = serializers.IntegerField(read_only=True)
    codigo = serializers.CharField(read_only=True)
    solicitante = serializers.CharField(max_length=150, help_text='Nombre del vecino o institución.')
    rut = serializers.CharField(required=False, allow_blank=True, max_length=12,
                                help_text='RUT del vecino (opcional).')
    telefono = serializers.CharField(max_length=30, help_text='Teléfono del vecino (8 a 15 dígitos).')
    clasificacion = serializers.CharField(read_only=True,
                                          help_text='Atención ciudadana u Otra gestión (si el solicitante es el Delegado).')
    tipoId = serializers.IntegerField(source='tipo_id')
    tipoNombre = serializers.CharField(source='tipo.nombre', read_only=True)
    subId = serializers.IntegerField(source='subatencion_id', help_text='Sub atención del mismo tipo.')
    subNombre = serializers.CharField(source='subatencion.nombre', read_only=True)
    itemId = serializers.IntegerField(source='item_id', help_text='Ítem de la Matriz SGR al que suma.')
    itemNombre = serializers.CharField(source='item.nombre', read_only=True, default='')
    estado = serializers.ChoiceField(choices=[e for e, _ in Atencion.ESTADOS], required=False,
                                     help_text='Ejecutada (suma puntaje) o Preparación. Por defecto Ejecutada.')
    descripcion = serializers.CharField(min_length=10)
    delegacionId = serializers.IntegerField(source='delegacion_id')
    delegacionNombre = serializers.CharField(source='delegacion.nombre', read_only=True)
    responsableId = serializers.IntegerField(source='responsable_id')
    responsableNombre = serializers.SerializerMethodField()
    fecha = serializers.DateField(help_text='No futura y de una semana no cerrada (hasta el lunes siguiente).')
    beneficiario = serializers.ChoiceField(choices=[b for b, _ in Atencion.BENEFICIARIOS], required=False)
    organizacionId = serializers.IntegerField(source='organizacion_id', required=False, allow_null=True,
                                              help_text='Obligatoria si beneficiario = Organización.')
    organizacionNombre = serializers.CharField(source='organizacion.nombre', read_only=True, default='')
    fechaCompromiso = serializers.DateField(source='fecha_compromiso', required=False, allow_null=True,
                                            help_text='Plazo; por defecto fecha + 7 días.')
    solicitanteEsDelegado = serializers.BooleanField(write_only=True, required=False,
                                                     help_text='true si el solicitante es el propio Delegado.')
    etapa = serializers.CharField(read_only=True)
    ejecutadaEl = serializers.DateField(source='ejecutada_el', read_only=True)
    puntaje = serializers.IntegerField(read_only=True, help_text='1 si sumó a la matriz, 0 si no.')
    topeAlcanzado = serializers.BooleanField(source='tope_alcanzado', read_only=True,
                                             help_text='true si no sumó porque el ítem ya estaba en el 120%.')
    vencido = serializers.SerializerMethodField()
    alerta = serializers.SerializerMethodField(help_text='Solo en POST/PUT: aviso si el ítem alcanzó el tope.')

    def get_responsableNombre(self, a) -> str:
        return P.nombre_visible(a.responsable)

    def get_vencido(self, a) -> bool:
        return reglas.esta_vencida(a)

    def get_alerta(self, a) -> dict | None:
        return getattr(a, 'alerta', None)

    # ---- entrada
    def validar_negocio(self, datos):
        atencion = self.instance
        if atencion is not None:
            hoy = timezone.localdate()
            if hoy > reglas.limite_ingreso(atencion.fecha):
                raise reglas.ErrorApi('semana_cerrada', 'fecha', reglas.limite_ingreso(atencion.fecha).isoformat(),
                                      status=409)
        valores = reglas._validar_atencion(datos, self.usuario, excluir=atencion)
        if (atencion is not None and atencion.estado == Atencion.EJECUTADA
                and valores['estado'] == Atencion.PREPARACION):
            raise reglas.ErrorApi('ya_ejecutada', 'estado',
                                  'Una actividad ejecutada no puede volver a Preparación.', status=409)
        return valores

    def create(self, valores):
        atencion, alerta = reglas.crear_atencion(valores, self.usuario)
        atencion.alerta = alerta
        return atencion

    def update(self, instance, valores):
        with transaction.atomic():
            a = Atencion.objects.select_for_update().get(pk=instance.pk)
            if a.estado == Atencion.EJECUTADA:
                # Ya estaba ejecutada: conserva su fecha de ejecución (salvo que se ejecutó el mismo día
                # del registro, en cuyo caso sigue a la fecha corregida) y su etapa Realizado.
                if a.ejecutada_el is None or a.ejecutada_el == a.fecha or a.ejecutada_el < valores['fecha']:
                    valores['ejecutada_el'] = valores['fecha']
                else:
                    valores['ejecutada_el'] = a.ejecutada_el
            elif valores['estado'] == Atencion.PREPARACION:
                valores['etapa'] = a.etapa  # sigue en preparación: no pierde su avance en el tubo
            # Se recalcula el puntaje desde cero: primero se anula el propio, para que no se cuente
            # a sí misma al revisar el tope del 120%.
            a.puntaje, a.tope_alcanzado = 0, False
            a.save(update_fields=['puntaje', 'tope_alcanzado'])
            for campo, valor in valores.items():
                setattr(a, campo, valor)
            alerta = M.asignar_puntaje(a)
            a.save()
        a = Atencion.objects.select_related('tipo', 'subatencion', 'delegacion', 'responsable', 'item',
                                            'organizacion').get(pk=a.pk)
        a.alerta = alerta
        return a


class AtencionBasicaSerializer(AtencionSerializer):
    """Vista básica: el RUT y el teléfono del vecino se pueden enviar, pero no se muestran."""
    rut = serializers.CharField(required=False, allow_blank=True, max_length=12, write_only=True)
    telefono = serializers.CharField(max_length=30, write_only=True)


# ======================================================== PERSONA 2: transacción Reclamos
class ReclamoSerializer(ReglasDeNegocioSerializer):
    """Vista completa (administrador y Delegado): incluye quién reclamó y la referencia del respaldo."""
    id = serializers.IntegerField(read_only=True)
    delegacionId = serializers.IntegerField(source='delegacion_id', help_text='Delegación del Delegado.')
    funcionarioId = serializers.IntegerField(source='funcionario_id', help_text='Funcionario del equipo.')
    funcionario = serializers.SerializerMethodField()
    itemId = serializers.IntegerField(source='item_id', help_text='Ítem del que se descuentan los puntos.')
    item = serializers.CharField(source='item.nombre', read_only=True)
    fecha = serializers.DateField(help_text='No futura. Define el trimestre del descuento.')
    reclamante = serializers.CharField(max_length=150, help_text='Quién reclama.')
    motivo = serializers.CharField(min_length=10)
    respaldoTipo = serializers.ChoiceField(source='respaldo_tipo', choices=Felicitacion.RESPALDOS,
                                           help_text='Solo respaldos formales (nada de chats).')
    respaldoReferencia = serializers.CharField(source='respaldo_referencia', max_length=120,
                                               help_text='Folio, N° de oficio o asunto del correo.')
    puntos = serializers.IntegerField(min_value=1, max_value=Reclamo.MAX_DESCUENTO, required=False,
                                      help_text='Puntos que descuenta (1 a 5, por defecto 1).')
    registradoPor = serializers.SerializerMethodField()

    def get_funcionario(self, r) -> str:
        return P.nombre_visible(r.funcionario)

    def get_registradoPor(self, r) -> str:
        return P.nombre_visible(r.registrado_por) if r.registrado_por else ''

    def validar_negocio(self, datos):
        return reglas.validar_reclamo(datos, self.usuario)

    def create(self, valores):
        return Reclamo.objects.create(**valores, registrado_por=self.usuario)

    def update(self, instance, valores):
        for campo, valor in valores.items():
            setattr(instance, campo, valor)
        instance.save()
        return instance


class ReclamoBasicoSerializer(ReclamoSerializer):
    """Vista del funcionario (solo sus propios reclamos): sin el nombre del reclamante ni la
    referencia del respaldo. El funcionario no puede escribir reclamos, así que se quitan del todo."""

    def get_fields(self):
        campos = super().get_fields()
        campos.pop('reclamante')
        campos.pop('respaldoReferencia')
        return campos


# ======================================================== "¿quién soy?"
class DelegacionCortaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class YoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    usuario = serializers.CharField()
    nombre = serializers.CharField()
    rol = serializers.CharField(allow_null=True)
    perfil = serializers.ChoiceField(choices=[P.DASH_ADMINISTRADOR, P.DASH_SUPERVISOR, P.DASH_ADMINISTRATIVO],
                                     help_text='Tipo de panel del rol.')
    alcance = serializers.CharField()
    permisos = serializers.ListField(child=serializers.CharField())
    delegaciones = DelegacionCortaSerializer(many=True)
    esAdministrador = serializers.BooleanField(help_text='true: ve los datos sensibles (RUT, teléfonos).')
    esDelegado = serializers.BooleanField(help_text='true: puede registrar reclamos de su equipo.')

