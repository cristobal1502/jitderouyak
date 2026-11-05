"""Carga los datos base del sistema.

    python manage.py cargar_datos_iniciales          # roles, catálogos y un administrador
    python manage.py cargar_datos_iniciales --demo   # además usuarios y atenciones de ejemplo

Es idempotente: se puede ejecutar varias veces sin duplicar registros.
"""
from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from dashboard.models import (
    Atencion, CasoSocial, Delegacion, GestionSocial, ItemMeta, Perfil, Rol, SubAtencion, TipoAtencion,
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
    ('Administrativo', 'Registra atenciones y casos propios. Sin acceso a administración.',
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

# (código, nombre, RUT, teléfono, sector, delegación, creado por, [(tipo, detalle, fecha, atendido por)])
CASOS_DEMO = [
    ('CS-001', 'María Morales Carrasco', '12.345.678-5', '+56 9 8765 4321', 'Tierras Blancas', 'DEL-003', 'carla.tapia', [
        ('TAT-001', 'Entrevista en delegación y diagnóstico socioeconómico preliminar.', date(2026, 8, 2), 'carla.tapia'),
        ('TAT-002', 'Visita en domicilio para verificar condiciones de techumbre tras precipitaciones.', date(2026, 8, 20), 'carla.tapia'),
    ]),
    ('CS-002', 'Carlos Araya Godoy', '9.876.543-3', '+56 9 1122 3344', 'Coquimbo Oriente', 'DEL-001', 'juan.perez', [
        ('TAT-001', 'Entrevista inicial y levantamiento de antecedentes.', date(2026, 7, 28), 'juan.perez'),
        ('TAT-004', 'Derivación a red de apoyo comunal para seguimiento.', date(2026, 8, 15), 'juan.perez'),
    ]),
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
        for nombre, desc, permisos, alcance in ROLES:
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
                ('AT-001', 'María Morales Carrasco', 'TAT-001', 'SUB-001', 'Entrevista en delegación y ficha FIBE.',
                 'DEL-003', carla, date(2026, 10, 5)),
                ('AT-002', 'Carlos Araya Godoy', 'TAT-002', 'SUB-003', 'Verificación de techumbre tras lluvias.',
                 'DEL-001', juan, date(2026, 10, 8)),
            ]
            for codigo, sol, tipo, sub, desc, deleg, resp, fecha in demo:
                Atencion.objects.get_or_create(codigo=codigo, defaults={
                    'solicitante': sol, 'tipo': tipos[tipo], 'subatencion': subs[sub], 'descripcion': desc,
                    'delegacion': dels[deleg], 'responsable': resp, 'fecha': fecha, 'creado_por': admin_user})
            for codigo, nombre, rut, tel, sector, deleg, creador, gestiones in CASOS_DEMO:
                caso, nuevo = CasoSocial.objects.get_or_create(codigo=codigo, defaults={
                    'nombre': nombre, 'rut': rut, 'telefono': tel, 'sector': sector,
                    'delegacion': dels[deleg], 'creado_por': User.objects.get(username=creador)})
                if nuevo:
                    for numero, (tipo, detalle, fecha, atiende) in enumerate(gestiones, start=1):
                        GestionSocial.objects.create(caso=caso, numero=numero, tipo=tipos[tipo], detalle=detalle,
                                                     fecha=fecha, atendido_por=User.objects.get(username=atiende))
            self.stdout.write(self.style.SUCCESS('Datos de ejemplo cargados (contraseña de los usuarios demo: Demo1234!).'))

        self.stdout.write(self.style.SUCCESS('Listo: roles, catálogos y administrador.'))
