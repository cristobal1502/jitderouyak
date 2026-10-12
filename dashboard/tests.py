"""Pruebas de la API y de los permisos. Ejecutar con:  python manage.py test dashboard login"""
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Atencion, Delegacion, Rol, SubAtencion, TipoAtencion


# Hasher rápido solo para las pruebas (PBKDF2 hace que cada login tarde ~0,1 s)
HASHER_RAPIDO = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])


@HASHER_RAPIDO
class BaseApi(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_datos_iniciales', '--demo', verbosity=0)

    def entrar(self, usuario, password='Demo1234!'):
        self.client.logout()
        assert self.client.login(username=usuario, password=password)

    def entrar_admin(self):
        self.entrar('admin', 'Admin123!')

    def api(self, metodo, ruta, datos=None):
        url = reverse('api_raiz') + ruta
        kwargs = {'content_type': 'application/json'}
        if datos is not None:
            kwargs['data'] = json.dumps(datos)
        return getattr(self.client, metodo)(url, **kwargs)

    def json(self, resp):
        return json.loads(resp.content)


class AutenticacionYPermisos(BaseApi):
    def test_api_exige_sesion(self):
        r = self.api('get', 'delegaciones/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.json(r)['error'], 'no_autenticado')

    def test_paginas_exigen_login(self):
        for nombre in ('dashboard', 'agenda', 'ingreso_atencion', 'configuraciones'):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertIn(reverse('login'), r['Location'])

    def test_funcionario_no_administra(self):
        self.entrar('juan.perez')
        self.assertEqual(self.client.get(reverse('administracion', args=['usuarios'])).status_code, 403)
        self.assertEqual(self.client.get(reverse('administracion', args=['delegaciones'])).status_code, 403)
        self.assertEqual(self.api('get', 'usuarios/').status_code, 403)
        self.assertEqual(self.api('get', 'roles/').status_code, 403)
        self.assertEqual(self.api('post', 'delegaciones/', {'nombre': 'X'}).status_code, 403)
        # pero puede leer catálogos
        self.assertEqual(self.api('get', 'delegaciones/').status_code, 200)

    def test_menu_segun_rol(self):
        self.entrar('juan.perez')
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertNotIn('nav-tag', html)
        self.assertIn('Juan Pérez', html)
        self.entrar_admin()
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('nav-tag', html)

    def test_entidad_inexistente(self):
        self.entrar_admin()
        self.assertEqual(self.api('get', 'inventada/').status_code, 404)
        self.assertEqual(self.client.get(reverse('administracion', args=['inventada'])).status_code, 404)


class Catalogos(BaseApi):
    def setUp(self):
        self.entrar_admin()

    def test_crear_delegacion_con_codigo_automatico(self):
        r = self.api('post', 'delegaciones/', {
            'nombre': 'Nueva', 'direccion': 'Calle 1', 'comuna': 'Coquimbo', 'estado': 'Activo'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.json(r)['codigo'], 'DEL-005')

    def test_campos_requeridos_y_duplicados(self):
        r = self.api('post', 'delegaciones/', {'nombre': '', 'direccion': 'x', 'comuna': 'y'})
        self.assertEqual((r.status_code, self.json(r)['error'], self.json(r)['campo']), (400, 'campo_vacio', 'nombre'))
        r = self.api('post', 'delegaciones/', {'codigo': 'del-001', 'nombre': 'a', 'direccion': 'b', 'comuna': 'c'})
        self.assertEqual((self.json(r)['error'], self.json(r)['campo']), ('duplicado', 'codigo'))

    def test_editar_y_estado(self):
        d = Delegacion.objects.get(codigo='DEL-002')
        r = self.api('put', f'delegaciones/{d.pk}/', {
            'codigo': 'DEL-002', 'nombre': 'Compañías Norte', 'direccion': d.direccion,
            'comuna': d.comuna, 'estado': 'Inactivo'})
        self.assertEqual(r.status_code, 200)
        d.refresh_from_db()
        self.assertEqual((d.nombre, d.activo), ('Compañías Norte', False))

    def test_estado_invalido(self):
        r = self.api('post', 'items/', {'nombre': 'x', 'descripcion': 'y', 'estado': 'Quizás'})
        self.assertEqual(self.json(r)['error'], 'referencia_invalida')

    def test_no_elimina_registros_en_uso(self):
        d = Delegacion.objects.get(codigo='DEL-001')  # tiene usuarios y atenciones
        r = self.api('delete', f'delegaciones/{d.pk}/')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.json(r)['error'], 'en_uso')
        t = TipoAtencion.objects.get(codigo='TAT-001')  # tiene sub atenciones
        self.assertEqual(self.json(self.api('delete', f'tipos-atencion/{t.pk}/'))['error'], 'en_uso')

    def test_elimina_registro_libre(self):
        d = Delegacion.objects.create(codigo='DEL-900', nombre='Temporal', direccion='x', comuna='y')
        self.assertEqual(self.api('delete', f'delegaciones/{d.pk}/').status_code, 200)
        self.assertFalse(Delegacion.objects.filter(pk=d.pk).exists())

    def test_sub_atencion_valida_tipo(self):
        r = self.api('post', 'sub-atenciones/', {'nombre': 'x', 'tipoId': 9999})
        self.assertEqual(self.json(r)['error'], 'referencia_invalida')
        t = TipoAtencion.objects.get(codigo='TAT-004')
        r = self.api('post', 'sub-atenciones/', {'nombre': 'Nueva sub', 'tipoId': t.pk})
        self.assertEqual((r.status_code, self.json(r)['codigo']), (201, 'SUB-008'))

    def test_json_invalido(self):
        r = self.client.post(reverse('api_raiz') + 'items/', data='no es json', content_type='application/json')
        self.assertEqual(self.json(r)['error'], 'json_invalido')


class Roles(BaseApi):
    def setUp(self):
        self.entrar_admin()

    def test_crud_rol(self):
        datos = {'nombre': 'Auditor', 'descripcion': 'Solo lectura', 'permisos': ['Ver panel'], 'alcance': 'Propio'}
        r = self.api('post', 'roles/', datos)
        self.assertEqual(r.status_code, 201)
        pk = self.json(r)['id']
        self.assertEqual(self.json(self.api('post', 'roles/', datos))['error'], 'duplicado')
        datos['permisos'] = ['Ver panel', 'Exportar informes']
        self.assertEqual(self.api('put', f'roles/{pk}/', datos).status_code, 200)
        self.assertEqual(Rol.objects.get(pk=pk).permisos, ['Ver panel', 'Exportar informes'])
        self.assertEqual(self.api('delete', f'roles/{pk}/').status_code, 200)

    def test_validaciones(self):
        base = {'nombre': 'X', 'descripcion': 'Y', 'permisos': ['Ver panel'], 'alcance': 'Propio'}
        for cambio, esperado in (({'permisos': []}, 'sin_seleccion'),
                                 ({'permisos': ['Hackear']}, 'referencia_invalida'),
                                 ({'alcance': ''}, 'campo_vacio'),
                                 ({'alcance': 'Planeta'}, 'referencia_invalida'),
                                 ({'descripcion': ' '}, 'campo_vacio')):
            r = self.api('post', 'roles/', {**base, **cambio})
            self.assertEqual(self.json(r)['error'], esperado, cambio)

    def test_rol_en_uso_no_se_elimina(self):
        rol = Rol.objects.get(nombre='Funcionario')
        r = self.api('delete', f'roles/{rol.pk}/')
        self.assertEqual((r.status_code, self.json(r)['error']), (409, 'en_uso'))

    def test_admin_no_puede_quitarse_gestionar_usuarios(self):
        rol = Rol.objects.get(nombre='Administrador')
        r = self.api('put', f'roles/{rol.pk}/', {
            'nombre': rol.nombre, 'descripcion': rol.descripcion, 'permisos': ['Ver panel'], 'alcance': rol.alcance})
        self.assertEqual(self.json(r)['error'], 'auto_rol')


class Usuarios(BaseApi):
    def setUp(self):
        self.entrar_admin()
        self.rol = Rol.objects.get(nombre='Funcionario')
        self.d1 = Delegacion.objects.get(codigo='DEL-001')

    def nuevo(self, **cambios):
        datos = {'nombre': 'Rosa Díaz', 'correo': 'rosa.diaz@municipalidad.cl', 'rolId': self.rol.pk,
                 'delegaciones': [self.d1.pk], 'estado': 'Activo'}
        datos.update(cambios)
        return self.api('post', 'usuarios/', datos)

    def test_crear_usuario_y_primer_ingreso(self):
        from django.core import mail
        r = self.nuevo()
        self.assertEqual(r.status_code, 201)
        cuerpo = self.json(r)
        self.assertEqual(cuerpo['usuario'], 'rosa.diaz')
        self.assertTrue(User.objects.get(username='rosa.diaz').perfil.delegaciones.filter(pk=self.d1.pk).exists())
        self.assertTrue(any('rosa.diaz@municipalidad.cl' in m.to for m in mail.outbox))
        self.client.logout()
        self.assertTrue(self.client.login(username='rosa.diaz', password=cuerpo['passwordTemporal']))

    def test_username_unico(self):
        self.nuevo()
        r = self.nuevo(correo='rosa.diaz@otro.cl')
        self.assertEqual(self.json(r)['usuario'], 'rosa.diaz2')

    def test_validaciones(self):
        self.assertEqual(self.json(self.nuevo(correo='sin-arroba'))['error'], 'correo_invalido')
        self.assertEqual(self.json(self.nuevo(correo='JUAN.PEREZ@municipalidad.cl'))['error'], 'duplicado')
        self.assertEqual(self.json(self.nuevo(delegaciones=[]))['error'], 'sin_seleccion')
        self.assertEqual(self.json(self.nuevo(delegaciones=[999]))['error'], 'referencia_invalida')
        self.assertEqual(self.json(self.nuevo(rolId=999))['error'], 'referencia_invalida')
        self.assertEqual(self.json(self.nuevo(nombre=''))['error'], 'campo_vacio')

    def test_editar_y_desactivar(self):
        pk = self.json(self.nuevo())['id']
        r = self.api('put', f'usuarios/{pk}/', {
            'nombre': 'Rosa D.', 'correo': 'rosa.diaz@municipalidad.cl', 'rolId': self.rol.pk,
            'delegaciones': [self.d1.pk], 'estado': 'Inactivo'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.get(pk=pk).is_active)

    def test_autoproteccion(self):
        yo = User.objects.get(username='admin')
        base = {'nombre': 'Admin', 'correo': yo.email, 'rolId': yo.perfil.rol_id,
                'delegaciones': [self.d1.pk], 'estado': 'Activo'}
        self.assertEqual(self.json(self.api('put', f'usuarios/{yo.pk}/', {**base, 'estado': 'Inactivo'}))['error'], 'auto_desactivar')
        self.assertEqual(self.json(self.api('put', f'usuarios/{yo.pk}/', {**base, 'rolId': self.rol.pk}))['error'], 'auto_rol')
        self.assertEqual(self.json(self.api('delete', f'usuarios/{yo.pk}/'))['error'], 'auto_eliminar')
        self.assertEqual(self.json(self.api('post', f'usuarios/{yo.pk}/reiniciar-password/', {}))['error'], 'auto_reiniciar')

    def test_eliminar(self):
        pk = self.json(self.nuevo())['id']
        self.assertEqual(self.api('delete', f'usuarios/{pk}/').status_code, 200)
        self.assertFalse(User.objects.filter(pk=pk).exists())
        juan = User.objects.get(username='juan.perez')  # tiene atenciones a cargo
        r = self.api('delete', f'usuarios/{juan.pk}/')
        self.assertEqual((r.status_code, self.json(r)['error']), (409, 'en_uso'))

    def test_reiniciar_password(self):
        juan = User.objects.get(username='juan.perez')
        r = self.api('post', f'usuarios/{juan.pk}/reiniciar-password/', {})
        self.assertEqual(r.status_code, 200)
        self.client.logout()
        self.assertFalse(self.client.login(username='juan.perez', password='Demo1234!'))
        self.assertTrue(self.client.login(username='juan.perez', password=self.json(r)['passwordTemporal']))

    def test_listado_incluye_estado_y_delegaciones(self):
        lista = self.json(self.api('get', 'usuarios/'))
        ana = next(u for u in lista if u['usuario'] == 'ana.nunez')
        self.assertEqual(ana['estado'], 'Inactivo')
        carla = next(u for u in lista if u['usuario'] == 'carla.tapia')
        self.assertEqual(len(carla['delegaciones']), 2)


class Atenciones(BaseApi):
    def datos(self, **cambios):
        tipo = TipoAtencion.objects.get(codigo='TAT-001')
        d = {'solicitante': 'Pedro Pablo', 'tipoId': tipo.pk,
             'subId': SubAtencion.objects.get(codigo='SUB-001').pk,
             'descripcion': 'Descripción suficientemente larga',
             'delegacionId': Delegacion.objects.get(codigo='DEL-001').pk,
             'responsableId': User.objects.get(username='juan.perez').pk,
             'fecha': timezone.localdate().isoformat()}
        d.update(cambios)
        return d

    def test_registro_propio_genera_codigo(self):
        self.entrar('juan.perez')
        r = self.api('post', 'atenciones/', self.datos())
        self.assertEqual((r.status_code, self.json(r)['codigo']), (201, 'AT-003'))
        self.assertEqual(Atencion.objects.get(codigo='AT-003').creado_por.username, 'juan.perez')

    def test_validaciones_en_orden(self):
        self.entrar('juan.perez')
        casos = [
            ({'solicitante': ' '}, 'campo_vacio'),
            ({'subId': SubAtencion.objects.get(codigo='SUB-003').pk}, 'sub_no_corresponde'),
            ({'subId': SubAtencion.objects.get(codigo='SUB-006').pk}, 'referencia_invalida'),
            ({'descripcion': 'corta'}, 'descripcion_corta'),
            ({'fecha': (timezone.localdate() + timedelta(days=1)).isoformat()}, 'fecha_futura'),
            ({'fecha': 'ayer'}, 'fecha_invalida'),
            ({'fecha': ''}, 'campo_vacio'),
            ({'delegacionId': Delegacion.objects.get(codigo='DEL-004').pk}, 'referencia_invalida'),
        ]
        for cambio, esperado in casos:
            r = self.api('post', 'atenciones/', self.datos(**cambio))
            self.assertEqual(self.json(r)['error'], esperado, cambio)

    def test_alcance_propio(self):
        self.entrar('juan.perez')
        # otra delegación a la que no pertenece
        r = self.api('post', 'atenciones/', self.datos(delegacionId=Delegacion.objects.get(codigo='DEL-002').pk))
        self.assertEqual(r.status_code, 403)
        # responsable distinto de sí mismo
        r = self.api('post', 'atenciones/', self.datos(responsableId=User.objects.get(username='carla.tapia').pk))
        self.assertEqual(self.json(r)['error'], 'responsable_invalido')

    def test_responsable_debe_pertenecer_a_la_delegacion_e_estar_activo(self):
        self.entrar_admin()
        d2 = Delegacion.objects.get(codigo='DEL-002').pk
        r = self.api('post', 'atenciones/', self.datos(delegacionId=d2))  # juan no está en DEL-002
        self.assertEqual(self.json(r)['error'], 'responsable_invalido')
        ana = User.objects.get(username='ana.nunez')  # inactiva
        r = self.api('post', 'atenciones/', self.datos(responsableId=ana.pk))
        self.assertEqual(self.json(r)['error'], 'responsable_invalido')
        carla = User.objects.get(username='carla.tapia')
        self.assertEqual(self.api('post', 'atenciones/', self.datos(responsableId=carla.pk)).status_code, 201)

    def test_visibilidad_por_alcance(self):
        self.entrar('juan.perez')  # Propio: solo AT-002 (a su cargo)
        self.assertEqual([a['codigo'] for a in self.json(self.api('get', 'atenciones/'))], ['AT-002'])
        self.entrar('maria.rojas')  # Delegación DEL-002: ninguna
        self.assertEqual(self.json(self.api('get', 'atenciones/')), [])
        self.entrar('carla.tapia')  # Propio: AT-001
        self.assertEqual([a['codigo'] for a in self.json(self.api('get', 'atenciones/'))], ['AT-001'])
        self.entrar_admin()
        self.assertEqual(len(self.json(self.api('get', 'atenciones/'))), 2)

    def test_opciones_segun_alcance(self):
        self.entrar('juan.perez')
        op = self.json(self.api('get', 'opciones-atencion/'))
        self.assertEqual([d['nombre'] for d in op['delegaciones']], ['Coquimbo Centro'])
        self.assertEqual([r['nombre'] for r in op['responsables']], ['Juan Pérez'])
        self.assertNotIn('Ficha FIBE ', [s['nombre'] for s in op['subatenciones']])
        self.assertNotIn('Entrega de materiales', [s['nombre'] for s in op['subatenciones']])  # inactiva
        self.entrar_admin()
        op = self.json(self.api('get', 'opciones-atencion/'))
        self.assertEqual(len(op['delegaciones']), 3)  # DEL-004 está inactiva
        self.assertNotIn('Ana Núñez', [r['nombre'] for r in op['responsables']])

    def test_sin_permiso_para_registrar(self):
        from .models import Perfil
        u = User.objects.create_user('veri', 'veri@x.cl', 'Veri1234!', first_name='Veri')
        p = Perfil.objects.create(user=u, rol=Rol.objects.get(nombre='Verificador'))  # sin "Registrar actividades"
        p.delegaciones.set(Delegacion.objects.filter(codigo='DEL-001'))
        self.entrar('veri', 'Veri1234!')
        r = self.api('post', 'atenciones/', self.datos(responsableId=u.pk))
        self.assertEqual(r.status_code, 403)


class PerfilPropio(BaseApi):
    def setUp(self):
        self.entrar('juan.perez')

    def test_leer_y_actualizar(self):
        self.assertEqual(self.json(self.api('get', 'yo/'))['cargo'], 'Funcionario')
        r = self.api('put', 'yo/', {'nombre': 'Juan P. Soto', 'correo': 'juan@nuevo.cl', 'telefono': '+56 9 1234 5678'})
        self.assertEqual(r.status_code, 200)
        u = User.objects.get(username='juan.perez')
        self.assertEqual((u.first_name, u.email, u.perfil.telefono), ('Juan P. Soto', 'juan@nuevo.cl', '+56 9 1234 5678'))

    def test_validaciones(self):
        self.assertEqual(self.json(self.api('put', 'yo/', {'correo': 'x'}))['error'], 'correo_invalido')
        self.assertEqual(self.json(self.api('put', 'yo/', {'correo': 'ana.nunez@municipalidad.cl'}))['error'], 'duplicado')
        self.assertEqual(self.json(self.api('put', 'yo/', {'nombre': ' '}))['error'], 'campo_vacio')
        self.assertEqual(self.json(self.api('put', 'yo/', {'telefono': 'abc'}))['error'], 'telefono_invalido')

    def test_preferencias(self):
        self.api('put', 'yo/', {'prefVencidos': False, 'prefResumen': True})
        p = User.objects.get(username='juan.perez').perfil
        self.assertEqual((p.pref_vencidos, p.pref_resumen), (False, True))
        self.assertEqual(self.json(self.api('put', 'yo/', {'prefResumen': 'si'}))['error'], 'referencia_invalida')

    def test_cambiar_password(self):
        for datos, esperado in (({'actual': '', 'nueva': 'Nueva123!'}, 'actual_vacia'),
                                ({'actual': 'Mala1234!', 'nueva': 'Nueva123!'}, 'actual_incorrecta'),
                                ({'actual': 'Demo1234!', 'nueva': 'corta1!'}, 'password_corto'),
                                ({'actual': 'Demo1234!', 'nueva': 'sinnumero!!'}, 'password_sin_mayuscula'),
                                ({'actual': 'Demo1234!', 'nueva': 'Sinnumero!!'}, 'password_sin_numero'),
                                ({'actual': 'Demo1234!', 'nueva': 'Sinespecial1'}, 'password_sin_especial'),
                                ({'actual': 'Demo1234!', 'nueva': 'Demo1234!'}, 'igual_a_actual')):
            self.assertEqual(self.json(self.api('post', 'yo/password/', datos))['error'], esperado, datos)
        r = self.api('post', 'yo/password/', {'actual': 'Demo1234!', 'nueva': 'Nueva123!'})
        self.assertEqual(r.status_code, 200)
        # sigue con la sesión abierta y la nueva contraseña funciona
        self.assertEqual(self.api('get', 'yo/').status_code, 200)
        self.client.logout()
        self.assertTrue(self.client.login(username='juan.perez', password='Nueva123!'))

    def test_pagina_configuraciones_trae_datos_del_usuario(self):
        html = self.client.get(reverse('configuraciones')).content.decode()
        self.assertIn('value="juan.perez@municipalidad.cl"', html)
        self.assertIn('value="Funcionario"', html)
