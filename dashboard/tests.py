"""Pruebas de la API y de los permisos. Ejecutar con:  python manage.py test dashboard login"""
import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from unittest import mock

from .api import limite_ingreso, primera_fecha_abierta
from . import matriz as M
from .models import (
    Atencion, Ausencia, Delegacion, Felicitacion, ItemMeta, OrganizacionComunitaria, Rol, SubAtencion, TipoAtencion,
)


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
        d = {'solicitante': 'Pedro Pablo', 'telefono': '+56 9 1234 5678', 'tipoId': tipo.pk,
             'itemId': ItemMeta.objects.get(codigo='ITM-001').pk,
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


# ------------------------------------------------------------ casos sociales
from .models import CasoSocial, GestionSocial  # noqa: E402


class CasosSociales(BaseApi):
    def nuevo(self, **extra):
        d = {'nombre': 'Rosa Pizarro Vega', 'rut': '11.111.111-1', 'telefono': '+56 9 5555 1111',
             'sector': 'Peñuelas', 'delegacionId': Delegacion.objects.get(codigo='DEL-001').pk,
             'tipoId': TipoAtencion.objects.get(codigo='TAT-001').pk,
             'detalle': 'Primera entrevista con la persona.', 'fecha': '2026-09-01'}
        d.update(extra)
        return d

    def test_crear_caso_es_atomico_con_gestion_1(self):
        self.entrar('juan.perez')
        r = self.api('post', 'casos/', self.nuevo())
        self.assertEqual(r.status_code, 201, r.content)
        c = CasoSocial.objects.get(rut='11.111.111-1')
        self.assertEqual(c.gestiones.count(), 1)
        self.assertEqual(c.gestiones.first().numero, 1)

    def test_si_falla_la_gestion_no_queda_el_caso(self):
        self.entrar('juan.perez')
        antes = CasoSocial.objects.count()
        r = self.api('post', 'casos/', self.nuevo(detalle='corto'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(CasoSocial.objects.count(), antes)

    def test_rut_invalido_y_duplicado(self):
        self.entrar('juan.perez')
        r = self.api('post', 'casos/', self.nuevo(rut='12.345.678-9'))
        self.assertEqual(self.json(r)['error'], 'rut_invalido')
        r = self.api('post', 'casos/', self.nuevo(rut='12.345.678-5'))  # ya existe CS-001
        self.assertEqual(self.json(r)['error'], 'duplicado')

    def test_maximo_tres_gestiones_y_fecha_no_anterior(self):
        self.entrar('carla.tapia')
        caso = CasoSocial.objects.get(codigo='CS-001')
        g = {'tipoId': TipoAtencion.objects.get(codigo='TAT-004').pk,
             'detalle': 'Derivación a la red comunal.', 'fecha': '2026-08-01'}
        r = self.api('post', f'casos/{caso.pk}/gestiones/', g)
        self.assertEqual(self.json(r)['error'], 'fecha_anterior')
        g['fecha'] = '2026-09-01'
        self.assertEqual(self.api('post', f'casos/{caso.pk}/gestiones/', g).status_code, 201)
        r = self.api('post', f'casos/{caso.pk}/gestiones/', g)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.json(r)['error'], 'gestiones_completas')
        self.assertEqual(caso.gestiones.count(), 3)

    def test_alcance_y_permisos(self):
        self.entrar('juan.perez')  # Propio
        codigos = [c['codigo'] for c in self.json(self.api('get', 'casos/'))]
        self.assertEqual(codigos, ['CS-002'])
        caso_ajeno = CasoSocial.objects.get(codigo='CS-001')
        self.assertEqual(self.api('post', f'casos/{caso_ajeno.pk}/gestiones/', {}).status_code, 404)
        self.entrar_admin()
        self.assertEqual(len(self.json(self.api('get', 'casos/'))), 2)
        # Verificador activo sin permiso de registrar
        u = User.objects.get(username='ana.nunez'); u.is_active = True; u.save()
        self.entrar('ana.nunez')
        self.assertEqual(self.api('post', 'casos/', self.nuevo()).status_code, 403)


# ------------------------------------------------------------ dashboards
class DashboardsPorPerfil(BaseApi):
    def html(self, usuario, password='Demo1234!'):
        self.entrar(usuario, password)
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_administrador(self):
        h = self.html('admin', 'Admin123!')
        self.assertIn('Dashboard Administrador', h)
        self.assertIn('bloqueMantenedores', h)
        self.assertIn('bloqueRoles', h)
        self.assertIn('Usuarios activos', h)

    def test_supervisor(self):
        h = self.html('laura.mena')
        self.assertIn('Dashboard Supervisor', h)
        self.assertIn('bloqueMantenedores', h)
        self.assertIn('bloqueEquipo', h)
        self.assertNotIn('bloqueRoles', h)
        self.assertNotIn('/administracion/usuarios', h)  # sin Gestionar usuarios

    def test_administrativo(self):
        h = self.html('diego.vera')
        self.assertIn('Mi panel', h)
        self.assertNotIn('bloqueMantenedores', h)
        self.assertIn('bloqueRestriccion', h)
        self.assertNotIn('nav-tag', h)
        self.assertEqual(self.client.get(reverse('administracion', args=['usuarios'])).status_code, 403)

    def test_datos_reales_segun_alcance(self):
        # Funcionario (Propio) ve solo sus atenciones; administrador ve todas
        self.assertIn('AT-002', self.html('juan.perez'))
        self.assertNotIn('AT-001', self.html('juan.perez'))
        h = self.html('admin', 'Admin123!')
        self.assertIn('AT-001', h); self.assertIn('AT-002', h)


class BusquedaAvanzada(BaseApi):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        juan = User.objects.get(username='juan.perez')
        maria = User.objects.get(username='maria.rojas')
        tipo2 = TipoAtencion.objects.get(codigo='TAT-002')
        tipo3 = TipoAtencion.objects.get(codigo='TAT-003')
        d1 = Delegacion.objects.get(codigo='DEL-001')
        d2 = Delegacion.objects.get(codigo='DEL-002')
        for i in range(12):  # 12 atenciones extra de juan en DEL-001 para probar la paginación
            Atencion.objects.create(
                codigo=f'AT-{100 + i}', solicitante=f'Vecino {i}', tipo=tipo2,
                subatencion=SubAtencion.objects.get(codigo='SUB-004'),
                descripcion=f'Mediación por ruidos molestos número {i}', delegacion=d1,
                responsable=juan, fecha=date(2026, 7, 1 + i))
        Atencion.objects.create(
            codigo='AT-200', solicitante='Junta de vecinos', tipo=tipo3,
            subatencion=SubAtencion.objects.get(codigo='SUB-005'),
            descripcion='Entrega de subsidio de luminaria', delegacion=d2, responsable=maria,
            fecha=date(2026, 9, 15))

    def buscar(self, **params):
        from urllib.parse import urlencode
        return self.api('get', 'busqueda/?' + urlencode(params))

    def codigos(self, resp):
        return [a['codigo'] for a in self.json(resp)['resultados']]

    def test_exige_sesion(self):
        self.assertEqual(self.buscar().status_code, 401)
        self.assertEqual(self.client.get(reverse('busqueda')).status_code, 302)

    def test_paginacion_y_orden(self):
        self.entrar_admin()
        r = self.json(self.buscar())
        self.assertEqual((r['total'], r['paginas'], r['pagina'], len(r['resultados'])), (15, 2, 1, 10))
        self.assertEqual(r['resultados'][0]['codigo'], 'AT-002')  # la más reciente primero (08/10)
        r2 = self.json(self.buscar(pagina=2))
        self.assertEqual(len(r2['resultados']), 5)
        self.assertEqual(self.json(self.buscar(pagina=99))['pagina'], 2)  # se ajusta a la última

    def test_filtros(self):
        self.entrar_admin()
        juan = User.objects.get(username='juan.perez')
        d2 = Delegacion.objects.get(codigo='DEL-002')
        self.assertEqual(self.json(self.buscar(funcionario=juan.pk))['total'], 13)
        self.assertEqual(self.codigos(self.buscar(delegacion=d2.pk)), ['AT-200'])
        self.assertEqual(self.json(self.buscar(desde='2026-07-01', hasta='2026-07-05'))['total'], 5)
        tipo3 = TipoAtencion.objects.get(codigo='TAT-003')
        self.assertEqual(self.codigos(self.buscar(tipo=tipo3.pk)), ['AT-200'])
        sub = SubAtencion.objects.get(codigo='SUB-003')
        self.assertEqual(self.codigos(self.buscar(sub=sub.pk)), ['AT-002'])
        # palabras clave: todas deben aparecer (en descripción, solicitante, código, tipo o sub)
        self.assertEqual(self.codigos(self.buscar(q='subsidio luminaria')), ['AT-200'])
        self.assertEqual(self.codigos(self.buscar(q='junta')), ['AT-200'])
        self.assertEqual(self.codigos(self.buscar(q='at-001')), ['AT-001'])
        self.assertEqual(self.json(self.buscar(q='ruidos', delegacion=d2.pk))['total'], 0)

    def test_validaciones(self):
        self.entrar_admin()
        casos = [
            ({'desde': 'ayer'}, 'fecha_invalida'),
            ({'desde': '2026-09-01', 'hasta': '2026-08-01'}, 'rango_invalido'),
            ({'tipo': 'x'}, 'referencia_invalida'),
            ({'tipo': 99999}, 'referencia_invalida'),
            ({'tipo': TipoAtencion.objects.get(codigo='TAT-001').pk,
              'sub': SubAtencion.objects.get(codigo='SUB-005').pk}, 'sub_no_corresponde'),
            ({'q': 'x' * 101}, 'texto_largo'),
        ]
        for params, esperado in casos:
            r = self.buscar(**params)
            self.assertEqual((r.status_code, self.json(r)['error']), (400, esperado), params)

    def test_alcance_del_rol(self):
        self.entrar('juan.perez')  # Propio: solo lo suyo, aunque busque todo
        r = self.json(self.buscar())
        self.assertEqual(r['total'], 13)
        self.assertNotIn('AT-200', [a['codigo'] for a in r['resultados']])
        # no puede filtrar por una delegación ajena
        d2 = Delegacion.objects.get(codigo='DEL-002')
        self.assertEqual(self.buscar(delegacion=d2.pk).status_code, 403)
        # filtrar por otro funcionario no revela nada
        maria = User.objects.get(username='maria.rojas')
        self.assertEqual(self.json(self.buscar(funcionario=maria.pk))['total'], 0)
        self.entrar('maria.rojas')  # Delegación DEL-002
        self.assertEqual(self.codigos(self.buscar()), ['AT-200'])

    def test_opciones_segun_alcance(self):
        self.entrar('juan.perez')
        op = self.json(self.api('get', 'busqueda/opciones/'))
        self.assertEqual([d['nombre'] for d in op['delegaciones']], ['Coquimbo Centro'])
        self.assertEqual([f['nombre'] for f in op['funcionarios']], ['Juan Pérez'])
        self.assertFalse(op['puedeExportar'])
        self.assertIn(2026, op['anios'])
        # incluye catálogos inactivos para poder buscar el historial
        self.assertIn('Entrega de materiales', [s['nombre'] for s in op['subatenciones']])
        self.entrar_admin()
        op = self.json(self.api('get', 'busqueda/opciones/'))
        self.assertEqual(len(op['delegaciones']), 4)
        self.assertEqual(sorted(f['nombre'] for f in op['funcionarios']),
                         ['Carla Tapia', 'Juan Pérez', 'María Rojas'])
        self.assertTrue(op['puedeExportar'])

    def test_exportar_excel(self):
        from io import BytesIO
        from openpyxl import load_workbook
        self.entrar('juan.perez')  # sin "Exportar informes"
        self.assertEqual(self.api('get', 'busqueda/exportar/').status_code, 403)
        self.entrar('maria.rojas')
        r = self.api('get', 'busqueda/exportar/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('.xlsx', r['Content-Disposition'])
        ws = load_workbook(BytesIO(r.content)).active
        filas = list(ws.iter_rows(values_only=True))
        self.assertEqual(filas[0][0], 'Código')
        self.assertEqual([f[0] for f in filas[1:]], ['AT-200'])  # solo lo de su alcance
        self.entrar_admin()
        from urllib.parse import urlencode
        r = self.api('get', 'busqueda/exportar/?' + urlencode({'q': 'ruidos'}))
        self.assertEqual(load_workbook(BytesIO(r.content)).active.max_row, 13)  # encabezado + 12

    def test_version_imprimible(self):
        self.entrar('juan.perez')
        self.assertEqual(self.client.get(reverse('busqueda_imprimir')).status_code, 403)
        self.entrar('maria.rojas')
        html = self.client.get(reverse('busqueda_imprimir')).content.decode()
        self.assertIn('AT-200', html)
        self.assertNotIn('AT-101', html)
        d1 = Delegacion.objects.get(codigo='DEL-001')
        self.assertEqual(self.client.get(reverse('busqueda_imprimir') + f'?delegacion={d1.pk}').status_code, 403)



class ReglasMatrizSGR(BaseApi):
    """Candados del ingreso de actividades (Matriz SGR)."""
    datos = Atenciones.datos

    def test_nombre_y_telefono_obligatorios(self):
        self.entrar('juan.perez')
        for cambio, esperado in [({'solicitante': ''}, ('campo_vacio', 'solicitante')),
                                 ({'telefono': ''}, ('campo_vacio', 'telefono')),
                                 ({'telefono': '   '}, ('campo_vacio', 'telefono')),
                                 ({'telefono': '1234'}, ('telefono_invalido', 'telefono')),
                                 ({'telefono': 'llamar luego'}, ('telefono_invalido', 'telefono'))]:
            r = self.json(self.api('post', 'atenciones/', self.datos(**cambio)))
            self.assertEqual((r['error'], r['campo']), esperado, cambio)
        r = self.api('post', 'atenciones/', self.datos(telefono='(51) 222-3344'))
        self.assertEqual((r.status_code, self.json(r)['telefono']), (201, '(51) 222-3344'))

    def test_delegado_como_solicitante_es_otra_gestion(self):
        self.entrar('juan.perez')
        r = self.json(self.api('post', 'atenciones/', self.datos()))
        self.assertEqual(r['clasificacion'], 'Atención ciudadana')
        # marcado a mano en el formulario
        r = self.json(self.api('post', 'atenciones/', self.datos(solicitanteEsDelegado=True)))
        self.assertEqual(r['clasificacion'], 'Otra gestión')
        # detectado por nombre: Laura Mena es Supervisor (no Delegado) → sigue siendo ciudadana
        r = self.json(self.api('post', 'atenciones/', self.datos(solicitante='Laura Mena')))
        self.assertEqual(r['clasificacion'], 'Atención ciudadana')
        # María Rojas es Delegado / Jefatura de DEL-002: si es la solicitante, se detecta sola
        self.entrar_admin()
        d2 = Delegacion.objects.get(codigo='DEL-002').pk
        maria = User.objects.get(username='maria.rojas').pk
        r = self.json(self.api('post', 'atenciones/', self.datos(
            solicitante='  maria ROJAS ', delegacionId=d2, responsableId=maria)))
        self.assertEqual(r['clasificacion'], 'Otra gestión')

    def test_maximo_siete_por_dia(self):
        self.entrar('juan.perez')
        for _ in range(Atencion.MAX_POR_DIA):
            self.assertEqual(self.api('post', 'atenciones/', self.datos()).status_code, 201)
        r = self.api('post', 'atenciones/', self.datos())
        self.assertEqual((r.status_code, self.json(r)['error']), (400, 'limite_diario'))
        # otro día sí se puede
        ayer = timezone.localdate() - timedelta(days=1)
        if ayer >= primera_fecha_abierta():
            self.assertEqual(self.api('post', 'atenciones/', self.datos(fecha=ayer.isoformat())).status_code, 201)
        # y otro funcionario el mismo día también
        self.entrar_admin()
        carla = User.objects.get(username='carla.tapia').pk
        self.assertEqual(self.api('post', 'atenciones/', self.datos(responsableId=carla)).status_code, 201)

    def test_limite_de_ingreso_es_el_lunes_siguiente(self):
        self.assertEqual(limite_ingreso(date(2026, 11, 9)), date(2026, 11, 16))   # lunes → lunes siguiente
        self.assertEqual(limite_ingreso(date(2026, 11, 13)), date(2026, 11, 16))  # viernes → lunes
        self.assertEqual(primera_fecha_abierta(date(2026, 11, 16)), date(2026, 11, 9))   # lunes: aún la anterior
        self.assertEqual(primera_fecha_abierta(date(2026, 11, 17)), date(2026, 11, 16))  # martes: solo esta semana

    def test_cierre_semanal(self):
        self.entrar('juan.perez')
        viernes = date(2026, 11, 13)
        with mock.patch('dashboard.api.timezone.localdate', return_value=date(2026, 11, 16)):  # lunes
            r = self.api('post', 'atenciones/', self.datos(fecha=viernes.isoformat()))
            self.assertEqual(r.status_code, 201)
        with mock.patch('dashboard.api.timezone.localdate', return_value=date(2026, 11, 17)):  # martes
            r = self.api('post', 'atenciones/', self.datos(fecha=viernes.isoformat()))
            self.assertEqual((r.status_code, self.json(r)['error'], self.json(r)['detalle']),
                             (400, 'semana_cerrada', '2026-11-16'))
            r = self.api('post', 'atenciones/', self.datos(fecha='2026-11-16'))  # lunes de la semana actual
            self.assertEqual(r.status_code, 201)
            op = self.json(self.api('get', 'opciones-atencion/'))
            self.assertEqual((op['fechaMinima'], op['maxPorDia']), ('2026-11-16', 7))

    def test_busqueda_por_clasificacion(self):
        self.entrar('juan.perez')
        self.api('post', 'atenciones/', self.datos(solicitanteEsDelegado=True))
        r = self.json(self.api('get', 'busqueda/?clasificacion=Otra+gesti%C3%B3n'))
        self.assertEqual(r['total'], 1)
        self.assertEqual(self.api('get', 'busqueda/?clasificacion=x').status_code, 400)


class Organizaciones(BaseApi):
    def datos(self, **cambios):
        d = {'nombre': 'Club Deportivo Nuevo', 'tipo': OrganizacionComunitaria.FUNCIONAL,
             'subcategoria': 'Organización Deportiva', 'delegacionId': Delegacion.objects.get(codigo='DEL-001').pk,
             'sector': 'Centro', 'representante': '', 'telefono': '', 'verificacion': 'Pendiente de revisión',
             'estado': 'Activo'}
        d.update(cambios)
        return d

    def test_todos_consultan_solo_catalogos_editan(self):
        self.entrar('juan.perez')
        self.assertEqual(self.client.get(reverse('organizaciones')).status_code, 200)
        self.assertIn('data-solo-lectura="1"', self.client.get(reverse('organizaciones')).content.decode())
        self.assertEqual(len(self.json(self.api('get', 'organizaciones/'))), 6)
        self.assertEqual(self.api('post', 'organizaciones/', self.datos()).status_code, 403)
        self.entrar_admin()
        self.assertIn('data-solo-lectura="0"', self.client.get(reverse('organizaciones')).content.decode())
        r = self.api('post', 'organizaciones/', self.datos())
        self.assertEqual((r.status_code, self.json(r)['codigo']), (201, 'ORG-007'))

    def test_subfamilia(self):
        self.entrar_admin()
        r = self.json(self.api('post', 'organizaciones/', self.datos(subcategoria='')))
        self.assertEqual((r['error'], r['campo']), ('campo_vacio', 'subcategoria'))
        r = self.json(self.api('post', 'organizaciones/', self.datos(subcategoria='Otra cosa')))
        self.assertEqual(r['error'], 'referencia_invalida')
        # las juntas de vecinos (territoriales) no llevan subfamilia
        r = self.json(self.api('post', 'organizaciones/', self.datos(tipo=OrganizacionComunitaria.TERRITORIAL)))
        self.assertEqual(r['subcategoria'], '')
        self.assertEqual(r['verificacion'], 'Pendiente de revisión')

    def test_verificar(self):
        self.entrar_admin()
        org = OrganizacionComunitaria.objects.get(codigo='ORG-002')
        datos = self.json(self.api('get', 'organizaciones/'))[1]
        datos['verificacion'] = 'Verificado'
        self.assertEqual(self.api('put', f'organizaciones/{org.pk}/', datos).status_code, 200)
        org.refresh_from_db()
        self.assertEqual(org.verificacion, 'Verificado')

    def test_supervisor_solo_en_sus_delegaciones(self):
        self.entrar('laura.mena')  # Supervisor de DEL-001 y DEL-002
        d3 = Delegacion.objects.get(codigo='DEL-003').pk
        self.assertEqual(self.api('post', 'organizaciones/', self.datos(delegacionId=d3)).status_code, 403)
        self.assertEqual(self.api('post', 'organizaciones/', self.datos()).status_code, 201)
        org = OrganizacionComunitaria.objects.get(codigo='ORG-004')  # DEL-003
        self.assertEqual(self.api('delete', f'organizaciones/{org.pk}/').status_code, 403)

    def test_delegacion_con_organizaciones_no_se_elimina(self):
        self.entrar_admin()
        OrganizacionComunitaria.objects.create(
            codigo='ORG-900', nombre='X', tipo=OrganizacionComunitaria.TERRITORIAL, sector='x',
            delegacion=Delegacion.objects.create(codigo='DEL-900', nombre='T', direccion='x', comuna='y'))
        d = Delegacion.objects.get(codigo='DEL-900')
        r = self.api('delete', f'delegaciones/{d.pk}/')
        self.assertEqual((r.status_code, self.json(r)['error']), (409, 'en_uso'))



class PuntajeMatriz(BaseApi):
    datos = Atenciones.datos

    def crear(self, **cambios):
        r = self.api('post', 'atenciones/', self.datos(**cambios))
        self.assertEqual(r.status_code, 201, r.content)
        return self.json(r)

    def test_item_obligatorio(self):
        self.entrar('juan.perez')
        r = self.json(self.api('post', 'atenciones/', self.datos(itemId='')))
        self.assertEqual((r['error'], r['campo']), ('campo_vacio', 'itemId'))
        inactivo = ItemMeta.objects.get(codigo='ITM-004').pk
        self.assertEqual(self.json(self.api('post', 'atenciones/', self.datos(itemId=inactivo)))['error'],
                         'referencia_invalida')

    def test_ejecutada_suma_preparacion_no(self):
        self.entrar('juan.perez')
        a = self.crear()
        self.assertEqual((a['estado'], a['puntaje'], a['alerta']), ('Ejecutada', 1, None))
        p = self.crear(estado='Preparación')
        self.assertEqual((p['puntaje'], p['ejecutadaEl']), (0, None))
        # al marcarla como ejecutada empieza a sumar
        r = self.api('post', f"atenciones/{p['id']}/ejecutar/", {})
        self.assertEqual((r.status_code, self.json(r)['puntaje'], self.json(r)['estado']), (200, 1, 'Ejecutada'))
        self.assertEqual(self.api('post', f"atenciones/{p['id']}/ejecutar/", {}).status_code, 409)

    def test_ejecucion_no_anterior_al_registro(self):
        self.entrar('juan.perez')
        p = self.crear(estado='Preparación')
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
        r = self.json(self.api('post', f"atenciones/{p['id']}/ejecutar/", {'fecha': ayer}))
        self.assertEqual(r['error'], 'ejecucion_anterior')

    def test_otra_gestion_no_suma(self):
        self.entrar('juan.perez')
        self.assertEqual(self.crear(solicitanteEsDelegado=True)['puntaje'], 0)

    def test_ejecutar_solo_lo_visible(self):
        self.entrar('carla.tapia')
        p = self.crear(responsableId=User.objects.get(username='carla.tapia').pk, estado='Preparación')
        self.entrar('juan.perez')
        self.assertEqual(self.api('post', f"atenciones/{p['id']}/ejecutar/", {}).status_code, 404)

    def test_tope_120_y_alerta(self):
        item = ItemMeta.objects.get(codigo='ITM-001')
        item.meta_mensual = 2  # tope = 2,4 → 2 puntos
        item.save()
        hoy = timezone.localdate()
        Ausencia.objects.filter(funcionario__username='juan.perez').delete()
        self.entrar('juan.perez')
        # puntos de AT-002 pueden existir en otro ítem; los de ITM-001 de este mes parten en 0
        base = M.puntos(User.objects.get(username='juan.perez'), item, hoy.year, hoy.month)
        for _ in range(max(0, 2 - base)):
            self.assertEqual(self.crear()['puntaje'], 1)
        r = self.crear()
        self.assertEqual((r['puntaje'], r['topeAlcanzado']), (0, True))
        self.assertEqual(r['alerta']['item'], 'Atención social')
        self.assertGreaterEqual(r['alerta']['cumplimiento'], 100)
        self.assertIn('Operativos en terreno', [x['item'] for x in r['alerta']['sugeridos']])
        # otro ítem sigue sumando
        otro = ItemMeta.objects.get(codigo='ITM-002').pk
        self.assertEqual(self.crear(itemId=otro)['puntaje'], 1)

    def test_meta_se_ajusta_por_ausencias(self):
        juan = User.objects.get(username='juan.perez')
        # octubre 2026: 22 días hábiles; la demo trae vacaciones del 19 al 23 (5 días hábiles)
        self.assertEqual(M.dias_habiles(date(2026, 10, 1), date(2026, 10, 31)), 22)
        self.assertAlmostEqual(M.factor_disponibilidad(juan, 2026, 10), 17 / 22)
        _, filas = M.resumen_funcionario(juan, 2026, 10)
        operativos = next(f for f in filas if f['item'] == 'Operativos en terreno')
        self.assertEqual((operativos['puntos'], operativos['meta']), (1, round(10 * 17 / 22, 1)))
        # una ausencia traslapada no descuenta dos veces
        Ausencia.objects.create(funcionario=juan, tipo='Licencia médica', desde=date(2026, 10, 22),
                                hasta=date(2026, 10, 27))
        self.assertEqual(M.dias_ausente(juan, date(2026, 10, 1), date(2026, 10, 31)), 7)

    def test_meta_mensual_en_items(self):
        self.entrar_admin()
        item = ItemMeta.objects.get(codigo='ITM-001')
        base = {'codigo': item.codigo, 'nombre': item.nombre, 'descripcion': item.descripcion, 'estado': 'Activo'}
        for meta, esperado in [('', 'campo_vacio'), ('cero', 'numero_invalido'), (0, 'numero_invalido')]:
            r = self.json(self.api('put', f'items/{item.pk}/', {**base, 'metaMensual': meta}))
            self.assertEqual(r['error'], esperado, meta)
        r = self.api('put', f'items/{item.pk}/', {**base, 'metaMensual': 15})
        self.assertEqual((r.status_code, self.json(r)['metaMensual']), (200, 15))
        # los tipos de atención no tienen meta
        self.assertNotIn('metaMensual', self.json(self.api('get', 'tipos-atencion/'))[0])


class VistaEquipo(BaseApi):
    def test_matriz_del_equipo(self):
        self.entrar_admin()
        d1 = Delegacion.objects.get(codigo='DEL-001').pk
        r = self.json(self.api('get', f'matriz/?delegacion={d1}&mes=2026-10'))
        nombres = [m['nombre'] for m in r['equipo']]
        self.assertIn('Juan Pérez', nombres)
        self.assertNotIn('Ana Núñez', nombres)  # inactiva
        self.assertNotIn('Pedro Soto', nombres)  # Administrador del sistema, no equipo territorial
        juan = next(m for m in r['equipo'] if m['nombre'] == 'Juan Pérez')
        self.assertEqual((juan['puntos'], juan['diasAusente'], juan['disponibilidad']), (1, 5, 77))
        self.assertEqual(r['grupo']['puntos'], 2)  # AT-001 (Carla) + AT-002 (Juan)
        self.assertEqual(sum(r['grupo']['conteo'].values()), len(r['equipo']))
        self.assertFalse(r['puedeGestionar'])  # el Administrador no es Delegado
        self.assertEqual(len(r['ausencias']), 1)
        self.entrar('maria.rojas')
        r = self.json(self.api('get', 'matriz/?mes=2026-10'))
        self.assertTrue(r['puedeGestionar'])
        self.assertEqual(len(r['felicitaciones']), 1)

    def test_alcance_y_validaciones(self):
        self.entrar('juan.perez')
        r = self.json(self.api('get', 'matriz/'))
        self.assertEqual(r['delegacion']['nombre'], 'Coquimbo Centro')
        self.assertFalse(r['puedeGestionar'])
        d2 = Delegacion.objects.get(codigo='DEL-002').pk
        self.assertEqual(self.api('get', f'matriz/?delegacion={d2}').status_code, 403)
        self.assertEqual(self.json(self.api('get', 'matriz/?mes=2026-13'))['error'], 'fecha_invalida')


class AusenciasYFelicitaciones(BaseApi):
    def ausencia(self, **cambios):
        d = {'delegacionId': Delegacion.objects.get(codigo='DEL-002').pk,
             'funcionarioId': User.objects.get(username='laura.mena').pk,
             'tipo': 'Licencia médica', 'desde': '2026-11-02', 'hasta': '2026-11-04'}
        d.update(cambios)
        return d

    def felicitacion(self, **cambios):
        d = {'delegacionId': Delegacion.objects.get(codigo='DEL-002').pk,
             'funcionarioId': User.objects.get(username='laura.mena').pk,
             'fecha': timezone.localdate().isoformat(), 'emisor': 'Vecina del sector',
             'motivo': 'Excelente atención en terreno', 'respaldoTipo': 'Correo electrónico formal',
             'respaldoReferencia': 'Correo del 10/11 a delegacion@muni.cl'}
        d.update(cambios)
        return d

    def test_solo_el_delegado(self):
        self.entrar('juan.perez')  # Funcionario
        r = self.api('post', 'ausencias/', self.ausencia(delegacionId=Delegacion.objects.get(codigo='DEL-001').pk,
                                                         funcionarioId=User.objects.get(username='juan.perez').pk))
        self.assertEqual((r.status_code, self.json(r)['error']), (403, 'solo_delegado'))
        self.entrar('laura.mena')  # Supervisor: tampoco
        self.assertEqual(self.json(self.api('post', 'felicitaciones/', self.felicitacion()))['error'], 'solo_delegado')
        self.entrar('maria.rojas')  # Delegado / Jefatura de DEL-002
        self.assertEqual(self.api('post', 'ausencias/', self.ausencia()).status_code, 201)
        self.assertEqual(self.api('post', 'felicitaciones/', self.felicitacion()).status_code, 201)
        # no puede gestionar otra delegación
        r = self.api('post', 'ausencias/', self.ausencia(delegacionId=Delegacion.objects.get(codigo='DEL-001').pk))
        self.assertEqual(r.status_code, 403)

    def test_ausencia_validaciones(self):
        self.entrar('maria.rojas')
        self.assertEqual(self.json(self.api('post', 'ausencias/', self.ausencia(hasta='2026-11-01')))['error'],
                         'rango_invalido')
        self.assertEqual(self.json(self.api('post', 'ausencias/', self.ausencia(tipo='Paseo')))['error'],
                         'referencia_invalida')
        juan = User.objects.get(username='juan.perez').pk  # no es del equipo de DEL-002
        self.assertEqual(self.json(self.api('post', 'ausencias/', self.ausencia(funcionarioId=juan)))['error'],
                         'referencia_invalida')
        self.assertEqual(self.api('post', 'ausencias/', self.ausencia()).status_code, 201)
        r = self.json(self.api('post', 'ausencias/', self.ausencia(desde='2026-11-04', hasta='2026-11-06')))
        self.assertEqual(r['error'], 'ausencia_traslapada')
        a = Ausencia.objects.get(funcionario__username='laura.mena')
        self.assertEqual(self.api('delete', f'ausencias/{a.pk}/').status_code, 200)

    def test_felicitacion_exige_respaldo_formal(self):
        self.entrar('maria.rojas')
        for cambio, esperado in [({'respaldoTipo': 'WhatsApp'}, 'respaldo_informal'),
                                 ({'respaldoReferencia': 'mensaje por whatsapp del vecino'}, 'respaldo_informal'),
                                 ({'respaldoReferencia': ''}, 'campo_vacio'),
                                 ({'respaldoTipo': ''}, 'campo_vacio'),
                                 ({'motivo': ''}, 'campo_vacio'),
                                 ({'fecha': (timezone.localdate() + timedelta(days=1)).isoformat()}, 'fecha_futura')]:
            r = self.json(self.api('post', 'felicitaciones/', self.felicitacion(**cambio)))
            self.assertEqual(r['error'], esperado, cambio)
        self.assertEqual(Felicitacion.objects.filter(funcionario__username='laura.mena').count(), 1)  # solo la demo


class RolesDeCargo(BaseApi):
    """Los 7 perfiles de cargo de la delegación como roles del sistema."""

    def usuario(self, username, rol, delegacion='DEL-001'):
        from .models import Perfil
        u = User.objects.create_user(username, f'{username}@muni.cl', 'Clave1234!', first_name=username.title())
        p = Perfil.objects.create(user=u, rol=Rol.objects.get(nombre=rol))
        p.delegaciones.set(Delegacion.objects.filter(codigo=delegacion))
        return u

    def test_existen_los_siete_cargos(self):
        from .cargos import ROLES_CARGO
        from .permisos import PERMISOS
        self.assertEqual(len(ROLES_CARGO), 7)
        for nombre, _, permisos, alcance in ROLES_CARGO:
            rol = Rol.objects.get(nombre=nombre)
            self.assertTrue(rol.descripcion)
            self.assertEqual((rol.permisos, rol.alcance), (permisos, alcance))
            self.assertTrue(set(permisos) <= set(PERMISOS), nombre)
            self.assertIn('Registrar actividades', permisos)  # todos son parte del equipo de la matriz

    def test_delegado_gestiona_su_equipo(self):
        d = self.usuario('delegada', 'Delegado')
        self.entrar('delegada', 'Clave1234!')
        r = self.json(self.api('get', 'matriz/'))
        self.assertTrue(r['puedeGestionar'])
        self.assertIn('Delegada', [m['nombre'] for m in r['equipo']])
        juan = User.objects.get(username='juan.perez').pk
        r = self.api('post', 'ausencias/', {'delegacionId': Delegacion.objects.get(codigo='DEL-001').pk,
                                            'funcionarioId': juan, 'tipo': 'Vacaciones',
                                            'desde': '2026-12-01', 'hasta': '2026-12-05'})
        self.assertEqual(r.status_code, 201)
        # puede editar organizaciones, pero no los demás catálogos
        self.assertIn('data-solo-lectura="0"', self.client.get(reverse('organizaciones')).content.decode())
        self.assertEqual(self.api('post', 'delegaciones/', {'nombre': 'X', 'direccion': 'x', 'comuna': 'y'}).status_code, 403)
        self.assertIsNotNone(d)

    def test_encargado_de_organizaciones(self):
        self.usuario('orgs', 'Organizaciones Comunitarias')
        self.entrar('orgs', 'Clave1234!')
        datos = {'nombre': 'Club de Adulto Mayor Nuevo', 'tipo': OrganizacionComunitaria.FUNCIONAL,
                 'subcategoria': 'Club de Adulto Mayor', 'delegacionId': Delegacion.objects.get(codigo='DEL-001').pk,
                 'sector': 'Centro', 'verificacion': 'Verificado', 'estado': 'Activo'}
        self.assertEqual(self.api('post', 'organizaciones/', datos).status_code, 201)
        otra = {**datos, 'delegacionId': Delegacion.objects.get(codigo='DEL-002').pk}
        self.assertEqual(self.api('post', 'organizaciones/', otra).status_code, 403)
        self.assertEqual(self.client.get(reverse('administracion', args=['items'])).status_code, 403)
        # no puede registrar ausencias ni felicitaciones (no es Delegado)
        self.assertFalse(self.json(self.api('get', 'matriz/'))['puedeGestionar'])

    def test_alcance_propio_del_gestor_social(self):
        self.usuario('gestor', 'Gestor Social (Trabajador Social)')
        self.entrar('gestor', 'Clave1234!')
        op = self.json(self.api('get', 'opciones-atencion/'))
        self.assertEqual([r['nombre'] for r in op['responsables']], ['Gestor'])

    def test_apoyo_administrativo_registra_para_el_equipo(self):
        self.usuario('apoyo', 'Apoyo Administrativo')
        self.entrar('apoyo', 'Clave1234!')
        op = self.json(self.api('get', 'opciones-atencion/'))
        self.assertIn('Juan Pérez', [r['nombre'] for r in op['responsables']])

    def test_nuevo_permiso_en_roles(self):
        self.entrar_admin()
        r = self.api('post', 'roles/', {'nombre': 'Encargado JJVV', 'descripcion': 'x',
                                        'permisos': ['Ver panel', 'Gestionar organizaciones'], 'alcance': 'Delegación'})
        self.assertEqual(r.status_code, 201)
