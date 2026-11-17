"""Carga los datos base del sistema.

    python manage.py cargar_datos_iniciales          # roles, catálogos y un administrador
    python manage.py cargar_datos_iniciales --demo   # además usuarios y atenciones de ejemplo

Es idempotente: se puede ejecutar varias veces sin duplicar registros.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from dashboard.cargos import ROLES_CARGO
from dashboard.models import (
    Atencion, Ausencia, Delegacion, Felicitacion, ItemMeta,
    OrganizacionComunitaria, Perfil, Rol, SubAtencion, TipoAtencion,
)

ROLES = [
    ('Administrador', 'Configura el sistema, usuarios y catálogos.',
     ['Ver panel', 'Registrar actividades', 'Validar evidencias', 'Gestionar agenda',
      'Gestionar usuarios', 'Administrar catálogos', 'Exportar informes'], 'Todas las delegaciones'),
    ('Coordinador del sistema', 'Supervisa metas, ponderaciones y reportes.',
     ['Ver panel', 'Gestionar agenda', 'Exportar informes'], 'Todas las delegaciones'),
    ('Delegado / Jefatura', 'Monitorea y asigna compromisos de su delegación.',
     ['Ver panel', 'Registrar actividades', 'Gestionar agenda', 'Exportar informes'], 'Delegación'),
    ('Verificador', 'Aprueba o rechaza evidencias.',
     ['Ver panel', 'Validar evidencias'], 'Delegación'),
    ('Funcionario', 'Registra actividades y atenciones propias.',
     ['Ver panel', 'Registrar actividades'], 'Propio'),
    ('Usuario de consulta', 'Consulta y exporta información.',
     ['Ver panel', 'Exportar informes'], 'Todas las delegaciones'),
    # Los tres perfiles base de la evaluación (cada uno con su propio dashboard):
    # Administrador (arriba) = acceso total · Supervisor = permisos intermedios · Administrativo = permisos mínimos
    ('Supervisor', 'Supervisa la operación de sus delegaciones: valida evidencias, gestiona agenda y catálogos.',
     ['Ver panel', 'Registrar actividades', 'Validar evidencias', 'Gestionar agenda',
      'Administrar catálogos', 'Exportar informes'], 'Delegación'),
    ('Administrativo', 'Registra sus propias atenciones. Sin acceso a administración.',
     ['Ver panel', 'Registrar actividades'], 'Propio'),
]

DELEGACIONES = [
    ('DEL-001', 'Coquimbo Centro', 'Av. Varela 1500', 'Coquimbo', True),
    ('DEL-002', 'Las Compañías', 'Av. Estadio 3200', 'La Serena', True),
    ('DEL-003', 'Tierras Blancas', 'Ruta D-43 Km 2', 'Coquimbo', True),
    ('DEL-004', 'Guayacán', 'Calle Costanera 450', 'Coquimbo', False),
]

ITEMS = [
    ('ITM-001', 'Atención social', 'Atenciones sociales a personas usuarias.', True),
    ('ITM-002', 'Operativos en terreno', 'Operativos de limpieza, despeje y mejoras en terreno.', True),
    ('ITM-003', 'Mediación vecinal', 'Mediación comunitaria entre vecinos.', True),
    ('ITM-004', 'Inspección', 'Inspecciones de infraestructura y señalética.', False),
]

TIPOS = [
    ('TAT-001', 'Atención inicial', 'Primer contacto y levantamiento de antecedentes.'),
    ('TAT-002', 'Visita a terreno', 'Gestión realizada en el domicilio o sector.'),
    ('TAT-003', 'Entrega de beneficio', 'Entrega de subsidios o materiales municipales.'),
    ('TAT-004', 'Derivación', 'Derivación a otras redes de apoyo.'),
]

SUBS = [
    ('SUB-001', 'Ficha FIBE', 'TAT-001', True),
    ('SUB-002', 'Diagnóstico socioeconómico', 'TAT-001', True),
    ('SUB-003', 'Verificación habitacional', 'TAT-002', True),
    ('SUB-004', 'Mediación en terreno', 'TAT-002', True),
    ('SUB-005', 'Subsidio municipal', 'TAT-003', True),
    ('SUB-006', 'Entrega de materiales', 'TAT-003', False),
    ('SUB-007', 'Derivación a red comunal', 'TAT-004', True),
]

# (usuario, nombre, correo, rol, delegaciones, activo)
USUARIOS_DEMO = [
    ('juan.perez', 'Juan Pérez', 'juan.perez@municipalidad.cl', 'Funcionario', ['DEL-001'], True),
    ('carla.tapia', 'Carla Tapia', 'carla.tapia@municipalidad.cl', 'Funcionario', ['DEL-001', 'DEL-003'], True),
    ('maria.rojas', 'María Rojas', 'maria.rojas@municipalidad.cl', 'Delegado / Jefatura', ['DEL-002'], True),
    ('pedro.soto', 'Pedro Soto', 'pedro.soto@municipalidad.cl', 'Administrador', ['DEL-001', 'DEL-002', 'DEL-003'], True),
    ('ana.nunez', 'Ana Núñez', 'ana.nunez@municipalidad.cl', 'Verificador', ['DEL-001'], False),
    ('laura.mena', 'Laura Mena', 'laura.mena@municipalidad.cl', 'Supervisor', ['DEL-001', 'DEL-002'], True),
    ('diego.vera', 'Diego Vera', 'diego.vera@municipalidad.cl', 'Administrativo', ['DEL-001'], True),
]

# (código, nombre, tipo, subfamilia, delegación, sector, teléfono, verificación,
#  directiva: ((presidente, RUT), (tesorero, RUT), (secretario, RUT)))
_T, _F = OrganizacionComunitaria.TERRITORIAL, OrganizacionComunitaria.FUNCIONAL
_SUB = OrganizacionComunitaria.SUBCATEGORIAS
ORGANIZACIONES_DEMO = [
    ('ORG-001', 'Junta de Vecinos Villa El Faro', _T, '', 'DEL-001', 'Coquimbo Centro', '+56 9 5555 1111', OrganizacionComunitaria.VERIFICADO,
     (('Rosa Álvarez', '10.234.567-3'), ('Pedro Contreras', '11.345.678-7'), ('Lucía Rivas', '12.456.789-0'))),
    ('ORG-002', 'Junta de Vecinos Las Compañías Norte', _T, '', 'DEL-002', 'Las Compañías', '', OrganizacionComunitaria.PENDIENTE,
     (('Hernán Gómez', '13.567.890-2'), ('Marta Salinas', '14.678.901-3'), ('Jorge Pizarro', '15.789.012-3'))),
    ('ORG-003', 'Club de Adulto Mayor Renacer', _F, _SUB[0], 'DEL-001', 'Coquimbo Oriente', '+56 9 5555 2222', OrganizacionComunitaria.PENDIENTE,
     (('Rosa Álvarez', '10.234.567-3'), ('Elena Vega', '17.901.234-0'), ('Raúl Torres', '18.012.345-8'))),
    ('ORG-004', 'Club Deportivo Tierras Blancas', _F, _SUB[1], 'DEL-003', 'Tierras Blancas', '+56 9 5555 3333', OrganizacionComunitaria.VERIFICADO,
     (('Pablo Rivera', '19.123.456-1'), ('Andrea Campos', '8.234.567-1'), ('Felipe Rojas', '9.345.678-5'))),
    ('ORG-005', 'Centro de Madres Esperanza', _F, _SUB[2], 'DEL-002', 'Las Compañías', '', OrganizacionComunitaria.PENDIENTE,
     (('Gloria Pizarro', '7.456.789-4'), ('Teresa Muñoz', '6.567.890-K'), ('Carmen Díaz', '5.678.901-4'))),
    ('ORG-006', 'Comité de Seguridad Pasaje Los Aromos', _F, _SUB[3], 'DEL-003', 'Tierras Blancas', '', OrganizacionComunitaria.PENDIENTE,
     (('Sergio Olivares', '21.789.012-8'), ('Daniela Fuentes', '22.890.123-7'), ('Tomás Araya', '23.901.234-5'))),
]


class Command(BaseCommand):
    help = 'Carga roles, catálogos y un usuario administrador (y datos de ejemplo con --demo).'

    def add_arguments(self, parser):
        parser.add_argument('--demo', action='store_true', help='Agrega usuarios y atenciones de ejemplo.')
        parser.add_argument('--admin-password', default='Admin123!',
                            help='Contraseña del administrador inicial (por defecto Admin123!).')
        parser.add_argument('--reset-admin', action='store_true',
                            help='Si el usuario "admin" ya existe, le restablece la contraseña, lo activa y le da el rol Administrador.')

    @transaction.atomic
    def handle(self, *args, **opts):
        roles = {}
        for nombre, desc, permisos, alcance in ROLES + ROLES_CARGO:
            roles[nombre], _ = Rol.objects.get_or_create(
                nombre=nombre, defaults={'descripcion': desc, 'permisos': permisos, 'alcance': alcance})

        dels = {}
        for codigo, nombre, direccion, comuna, activo in DELEGACIONES:
            dels[codigo], _ = Delegacion.objects.get_or_create(
                codigo=codigo, defaults={'nombre': nombre, 'direccion': direccion,
                                         'comuna': comuna, 'activo': activo})
        for codigo, nombre, desc, activo in ITEMS:
            ItemMeta.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre, 'descripcion': desc, 'activo': activo})

        tipos = {}
        for codigo, nombre, desc in TIPOS:
            tipos[codigo], _ = TipoAtencion.objects.get_or_create(
                codigo=codigo, defaults={'nombre': nombre, 'descripcion': desc})
        subs = {}
        for codigo, nombre, tipo, activo in SUBS:
            subs[codigo], _ = SubAtencion.objects.get_or_create(
                codigo=codigo, defaults={'nombre': nombre, 'tipo': tipos[tipo], 'activo': activo})

        # Administrador inicial
        admin_user, creado = User.objects.get_or_create(
            username='admin',
            defaults={'email': 'admin@municipalidad.cl', 'first_name': 'Administrador SGR', 'is_staff': True})
        if creado or opts['reset_admin']:
            admin_user.set_password(opts['admin_password'])
            admin_user.is_active = True
            if not admin_user.email:
                admin_user.email = 'admin@municipalidad.cl'
            admin_user.save()
        perfil, _ = Perfil.objects.get_or_create(user=admin_user, defaults={'rol': roles['Administrador']})
        if opts['reset_admin']:
            perfil.rol = roles['Administrador']
            perfil.save()
        perfil.delegaciones.set(Delegacion.objects.all())
        if creado or opts['reset_admin']:
            self.stdout.write(self.style.SUCCESS(
                f"Administrador listo → usuario: admin  contraseña: {opts['admin_password']}"))
        else:
            self.stdout.write(self.style.WARNING(
                'El usuario "admin" ya existía: no se cambió su contraseña. '
                'Usa --reset-admin para restablecerla a Admin123!.'))

        if opts['demo']:
            for username, nombre, correo, rol, deleg, activo in USUARIOS_DEMO:
                user, nuevo = User.objects.get_or_create(
                    username=username, defaults={'email': correo, 'first_name': nombre, 'is_active': activo})
                if nuevo:
                    user.set_password('Demo1234!')
                    user.save()
                p, _ = Perfil.objects.get_or_create(user=user, defaults={'rol': roles[rol]})
                p.delegaciones.set([dels[c] for c in deleg])

            juan = User.objects.get(username='juan.perez')
            carla = User.objects.get(username='carla.tapia')
            demo = [
                ('AT-001', 'María Morales Carrasco', '+56 9 8765 4321', 'ITM-001', 'TAT-001', 'SUB-001', 'Entrevista en delegación y ficha FIBE.',
                 'DEL-003', carla, date(2026, 10, 5)),
                ('AT-002', 'Carlos Araya Godoy', '+56 9 1122 3344', 'ITM-002', 'TAT-002', 'SUB-003', 'Verificación de techumbre tras lluvias.',
                 'DEL-001', juan, date(2026, 10, 8)),
            ]
            for codigo, sol, tel, item, tipo, sub, desc, deleg, resp, fecha in demo:
                Atencion.objects.get_or_create(codigo=codigo, defaults={
                    'item': ItemMeta.objects.get(codigo=item), 'estado': Atencion.EJECUTADA,
                    'ejecutada_el': fecha, 'puntaje': 1, 'etapa': Atencion.REALIZADO,
                    'fecha_compromiso': fecha + timedelta(days=Atencion.PLAZO_DIAS),
                    'solicitante': sol, 'telefono': tel, 'tipo': tipos[tipo], 'subatencion': subs[sub], 'descripcion': desc,
                    'delegacion': dels[deleg], 'responsable': resp, 'fecha': fecha, 'creado_por': admin_user})
            for codigo, nombre, tipo, sub, deleg, sector, tel, verif, directiva in ORGANIZACIONES_DEMO:
                (pn, pr), (tn, tr), (sn, sr) = directiva
                OrganizacionComunitaria.objects.get_or_create(codigo=codigo, defaults={
                    'nombre': nombre, 'tipo': tipo, 'subcategoria': sub, 'delegacion': dels[deleg],
                    'sector': sector, 'telefono': tel, 'verificacion': verif,
                    'presidente_nombre': pn, 'presidente_rut': pr, 'tesorero_nombre': tn, 'tesorero_rut': tr,
                    'secretario_nombre': sn, 'secretario_rut': sr})
            maria = User.objects.get(username='maria.rojas')
            Ausencia.objects.get_or_create(
                funcionario=juan, desde=date(2026, 10, 19), defaults={
                    'tipo': 'Vacaciones', 'hasta': date(2026, 10, 23), 'registrada_por': admin_user})
            Felicitacion.objects.get_or_create(
                funcionario=User.objects.get(username='laura.mena'), fecha=date(2026, 10, 12), defaults={
                    'delegacion': dels['DEL-002'], 'emisor': 'Junta de Vecinos Las Compañías Norte',
                    'motivo': 'Gestión rápida del operativo de limpieza en la plaza del sector.',
                    'respaldo_tipo': 'Carta firmada', 'respaldo_referencia': 'Carta folio 2026-118',
                    'registrada_por': maria})
            self.stdout.write(self.style.SUCCESS('Datos de ejemplo cargados (contraseña de los usuarios demo: Demo1234!).'))

        self.stdout.write(self.style.SUCCESS('Listo: roles, catálogos y administrador.'))
