"""Tests de la API REST /api/v1/ (JWT, permisos por rol, datos sensibles, CRUD y formato de error).

Ejecutar:  python manage.py test sgrApi     (con DB_ENGINE=sqlite en el .env)
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from dashboard.models import (
    Atencion, Delegacion, ItemMeta, OrganizacionComunitaria, Perfil, Reclamo, Rol, SubAtencion, TipoAtencion,
)

API = '/api/v1/'
CLAVE_DEMO = 'Demo1234!'


class BaseApi(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_datos_iniciales', '--demo', verbosity=0)

    def setUp(self):
        cache.clear()  # reinicia los contadores del throttling entre tests

    # ---- ayudas
    def token(self, usuario, password=CLAVE_DEMO):
        r = self.client.post(API + 'token/', {'username': usuario, 'password': password}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def entrar(self, usuario, password=CLAVE_DEMO):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token(usuario, password)['access'])

    def entrar_admin(self):
        self.entrar('admin', 'Admin123!')

    def salir(self):
        self.client.credentials()

    def assertError(self, r, status, caso, campo=None):
        """Comprueba el código HTTP y el formato uniforme {"error", "campo", "detalle"}."""
        self.assertEqual(r.status_code, status, r.content)
        cuerpo = r.json()
        self.assertEqual(set(cuerpo), {'error', 'campo', 'detalle'}, cuerpo)
        self.assertEqual(cuerpo['error'], caso, cuerpo)
        if campo is not None:
            self.assertEqual(cuerpo['campo'], campo, cuerpo)

    @staticmethod
    def usuario(nombre):
        return User.objects.get(username=nombre)

    @staticmethod
    def delegacion(codigo):
        return Delegacion.objects.get(codigo=codigo)


# ================================================================ autenticación JWT
class AutenticacionJWT(BaseApi):
    def test_configuracion_de_tokens(self):
        self.assertEqual(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'], timedelta(minutes=15))
        self.assertEqual(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'], timedelta(days=1))

    def test_sin_token_responde_401(self):
        for ruta in ('delegaciones/', 'tipos-atencion/', 'atenciones/', 'items/', 'organizaciones/',
                     'reclamos/', 'yo/'):
            self.assertError(self.client.get(API + ruta), 401, 'no_autenticado')

    def test_token_invalido_responde_401(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer esto-no-es-un-token')
        self.assertError(self.client.get(API + 'delegaciones/'), 401, 'token_invalido')

    def test_obtener_token_y_usarlo(self):
        tokens = self.token('juan.perez')
        self.assertEqual(set(tokens), {'access', 'refresh'})
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + tokens['access'])
        r = self.client.get(API + 'yo/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['usuario'], 'juan.perez')

    def test_credenciales_incorrectas(self):
        r = self.client.post(API + 'token/', {'username': 'juan.perez', 'password': 'mala'}, format='json')
        self.assertError(r, 401, 'credenciales_invalidas')
        r = self.client.post(API + 'token/', {'username': 'juan.perez'}, format='json')
        self.assertError(r, 400, 'datos_invalidos', 'password')

    def test_usuario_inactivo_no_obtiene_token(self):
        r = self.client.post(API + 'token/', {'username': 'ana.nunez', 'password': CLAVE_DEMO}, format='json')
        self.assertError(r, 401, 'credenciales_invalidas')

    def test_refresh_con_rotacion_y_lista_negra(self):
        refresh = self.token('juan.perez')['refresh']
        r = self.client.post(API + 'token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.json())
        self.assertNotEqual(r.json()['refresh'], refresh)  # rotación: llega un refresh nuevo
        # El refresh anterior quedó en lista negra.
        r = self.client.post(API + 'token/refresh/', {'refresh': refresh}, format='json')
        self.assertError(r, 401, 'token_invalido')

    def test_logout_invalida_el_refresh(self):
        refresh = self.token('juan.perez')['refresh']
        self.assertEqual(self.client.post(API + 'logout/', {'refresh': refresh}, format='json').status_code, 204)
        r = self.client.post(API + 'token/refresh/', {'refresh': refresh}, format='json')
        self.assertError(r, 401, 'token_invalido')

    def test_throttling_en_token(self):
        datos = {'username': 'juan.perez', 'password': 'mala'}
        for _ in range(10):
            self.client.post(API + 'token/', datos, format='json')
        self.assertError(self.client.post(API + 'token/', datos, format='json'), 429, 'demasiadas_solicitudes')

    def test_yo_indica_si_ve_como_administrador(self):
        self.entrar_admin()
        self.assertTrue(self.client.get(API + 'yo/').json()['esAdministrador'])
        self.entrar('maria.rojas')
        yo = self.client.get(API + 'yo/').json()
        self.assertEqual((yo['esAdministrador'], yo['esDelegado']), (False, True))
        self.assertEqual([d['nombre'] for d in yo['delegaciones']], ['Las Compañías'])


# ================================================================ formato y rutas
class FormatoDeRespuestas(BaseApi):
    def test_ruta_inexistente_responde_404_json(self):
        self.assertError(self.client.get(API + 'no-existe/'), 404, 'no_encontrado')
        self.entrar('juan.perez')
        self.assertError(self.client.post(API + 'otra/ruta/', {}, format='json'), 404, 'no_encontrado')

    def test_registro_inexistente_responde_404(self):
        self.entrar_admin()
        self.assertError(self.client.get(API + 'delegaciones/99999/'), 404, 'no_encontrado')
        self.assertError(self.client.put(API + 'items/99999/', {}, format='json'), 404, 'no_encontrado')
        self.entrar('maria.rojas')  # en reclamos el permiso (solo Delegado) se revisa antes que el registro
        self.assertError(self.client.delete(API + 'reclamos/99999/'), 404, 'no_encontrado')

    def test_patch_deshabilitado(self):
        self.entrar_admin()
        pk = self.delegacion('DEL-001').pk
        self.assertError(self.client.patch(API + f'delegaciones/{pk}/', {'nombre': 'X'}, format='json'),
                         405, 'metodo_no_permitido')

    def test_json_mal_formado(self):
        self.entrar_admin()
        r = self.client.post(API + 'delegaciones/', '{"nombre": ', content_type='application/json')
        self.assertError(r, 400, 'json_invalido')

    def test_lista_paginada(self):
        self.entrar('juan.perez')
        cuerpo = self.client.get(API + 'delegaciones/').json()
        self.assertEqual(set(cuerpo), {'count', 'next', 'previous', 'results'})
        self.assertEqual(cuerpo['count'], Delegacion.objects.count())

    def test_swagger_y_esquema_publicos(self):
        self.assertEqual(self.client.get(API + 'docs/').status_code, 200)
        r = self.client.get(API + 'schema/?format=json')
        self.assertEqual(r.status_code, 200)
        esquema = r.json()
        self.assertIn('/api/v1/atenciones/', esquema['paths'])
        self.assertIn('jwtAuth', esquema['components']['securitySchemes'])

    def test_la_api_web_con_sesion_sigue_funcionando(self):
        self.client.login(username='juan.perez', password=CLAVE_DEMO)
        self.assertEqual(self.client.get('/dashboard/api/delegaciones/').status_code, 200)
        # Y la sesión web no sirve para la API REST: exige JWT.
        self.assertError(self.client.get(API + 'delegaciones/'), 401, 'no_autenticado')


# ================================================================ Persona 1: mantenedores
class Delegaciones(BaseApi):
    def test_crud_completo_como_administrador(self):
        self.entrar_admin()
        r = self.client.post(API + 'delegaciones/', {'nombre': 'La Herradura', 'direccion': 'Costanera 100',
                                                    'comuna': 'Coquimbo'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        nueva = r.json()
        self.assertEqual((nueva['codigo'], nueva['estado']), ('DEL-005', 'Activo'))
        url = API + f'delegaciones/{nueva["id"]}/'
        self.assertEqual(self.client.get(url).json()['nombre'], 'La Herradura')
        r = self.client.put(url, {'codigo': 'DEL-005', 'nombre': 'La Herradura Alta', 'direccion': 'Costanera 200',
                                  'comuna': 'Coquimbo', 'estado': 'Inactivo'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['nombre'], r.json()['estado']), ('La Herradura Alta', 'Inactivo'))
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Delegacion.objects.filter(pk=nueva['id']).exists())

    def test_funcionario_lee_pero_no_escribe(self):
        self.entrar('juan.perez')
        self.assertEqual(self.client.get(API + 'delegaciones/').status_code, 200)
        r = self.client.post(API + 'delegaciones/', {'nombre': 'X', 'direccion': 'Y', 'comuna': 'Z'}, format='json')
        self.assertError(r, 403, 'prohibido')
        self.assertError(self.client.delete(API + f'delegaciones/{self.delegacion("DEL-004").pk}/'), 403, 'prohibido')

    def test_validacion_igual_que_la_web(self):
        self.entrar_admin()
        r = self.client.post(API + 'delegaciones/', {'nombre': '', 'direccion': 'Y', 'comuna': 'Z'}, format='json')
        self.assertError(r, 400, 'campo_vacio', 'nombre')

    def test_codigo_duplicado_es_409(self):
        self.entrar_admin()
        r = self.client.post(API + 'delegaciones/', {'codigo': 'DEL-001', 'nombre': 'X', 'direccion': 'Y',
                                                    'comuna': 'Z'}, format='json')
        self.assertError(r, 409, 'duplicado', 'codigo')

    def test_borrar_en_uso_es_409(self):
        self.entrar_admin()
        r = self.client.delete(API + f'delegaciones/{self.delegacion("DEL-001").pk}/')
        self.assertError(r, 409, 'en_uso')
        self.assertIn('usuario', r.json()['detalle'])


class TiposDeAtencion(BaseApi):
    def test_crud_completo_con_permiso_de_catalogos(self):
        self.entrar('laura.mena')  # Supervisor: tiene «Administrar catálogos»
        r = self.client.post(API + 'tipos-atencion/', {'nombre': 'Orientación legal',
                                                      'descripcion': 'Trámites y derechos.'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        url = API + f'tipos-atencion/{r.json()["id"]}/'
        self.assertEqual(r.json()['codigo'], 'TAT-005')
        r = self.client.put(url, {'codigo': 'TAT-005', 'nombre': 'Orientación jurídica',
                                  'descripcion': 'Trámites.', 'estado': 'Activo'}, format='json')
        self.assertEqual((r.status_code, r.json()['nombre']), (200, 'Orientación jurídica'))
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_funcionario_no_crea(self):
        self.entrar('juan.perez')
        r = self.client.post(API + 'tipos-atencion/', {'nombre': 'X', 'descripcion': 'Y'}, format='json')
        self.assertError(r, 403, 'prohibido')

    def test_borrar_en_uso_es_409(self):
        self.entrar_admin()
        r = self.client.delete(API + f'tipos-atencion/{TipoAtencion.objects.get(codigo="TAT-001").pk}/')
        self.assertError(r, 409, 'en_uso')

    def test_estado_invalido(self):
        self.entrar_admin()
        r = self.client.post(API + 'tipos-atencion/', {'nombre': 'X', 'descripcion': 'Y', 'estado': 'Quizás'},
                             format='json')
        self.assertError(r, 400, 'referencia_invalida', 'estado')


# ================================================================ Persona 2: mantenedores
class ItemsYMetas(BaseApi):
    def test_crud_completo(self):
        self.entrar_admin()
        r = self.client.post(API + 'items/', {'nombre': 'Visitas a dirigentes', 'descripcion': 'Reuniones.',
                                             'metaTrimestral': 25}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['metaTrimestral'], 25)
        url = API + f'items/{r.json()["id"]}/'
        r = self.client.put(url, {'codigo': r.json()['codigo'], 'nombre': 'Visitas a dirigentes',
                                  'descripcion': 'Reuniones.', 'metaTrimestral': 40, 'estado': 'Activo'}, format='json')
        self.assertEqual((r.status_code, r.json()['metaTrimestral']), (200, 40))
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_meta_fuera_de_rango(self):
        self.entrar_admin()
        r = self.client.post(API + 'items/', {'nombre': 'X', 'descripcion': 'Y', 'metaTrimestral': 0}, format='json')
        self.assertError(r, 400, 'numero_invalido', 'metaTrimestral')

    def test_borrar_en_uso_es_409(self):
        self.entrar_admin()
        item = ItemMeta.objects.filter(atenciones__isnull=False).first()
        self.assertError(self.client.delete(API + f'items/{item.pk}/'), 409, 'en_uso')

    def test_funcionario_no_edita(self):
        self.entrar('juan.perez')
        item = ItemMeta.objects.first()
        r = self.client.put(API + f'items/{item.pk}/', {'nombre': 'X'}, format='json')
        self.assertError(r, 403, 'prohibido')


DIRECTIVA = {'presidente': {'nombre': 'Ana Soto', 'rut': '10.234.567-3', 'telefono': '+56 9 1111 1111'},
             'tesorero': {'nombre': 'Luis Mena', 'rut': '11.345.678-7', 'telefono': '+56 9 2222 2222'},
             'secretario': {'nombre': 'Eva Díaz', 'rut': '12.456.789-0', 'telefono': '+56 9 3333 3333'}}


class Organizaciones(BaseApi):
    def organizacion(self, **cambios):
        d = {'nombre': 'Club Deportivo El Faro', 'tipo': OrganizacionComunitaria.FUNCIONAL,
             'subcategoria': 'Organización Deportiva', 'delegacionId': self.delegacion('DEL-001').pk,
             'sector': 'Coquimbo Centro', 'directiva': DIRECTIVA}
        d.update(cambios)
        return d

    def test_crud_completo(self):
        self.entrar_admin()
        r = self.client.post(API + 'organizaciones/', self.organizacion(), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        org = r.json()
        self.assertEqual(org['directiva']['presidente']['rut'], '10.234.567-3')
        url = API + f'organizaciones/{org["id"]}/'
        r = self.client.put(url, self.organizacion(codigo=org['codigo'], nombre='Club Deportivo Faro Norte'),
                            format='json')
        self.assertEqual((r.status_code, r.json()['nombre']), (200, 'Club Deportivo Faro Norte'))
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_funcionario_no_ve_rut_ni_telefono_de_la_directiva(self):
        org = OrganizacionComunitaria.objects.get(codigo='ORG-001')
        self.entrar('juan.perez')
        directiva = self.client.get(API + f'organizaciones/{org.pk}/').json()['directiva']
        self.assertEqual(directiva['presidente'], {'nombre': 'Rosa Álvarez'})
        self.entrar_admin()
        directiva = self.client.get(API + f'organizaciones/{org.pk}/').json()['directiva']
        self.assertEqual(directiva['presidente'],
                         {'nombre': 'Rosa Álvarez', 'rut': '10.234.567-3', 'telefono': '+56 9 6001 4001'})

    def test_rut_invalido_y_repetido(self):
        self.entrar_admin()
        mala = {**DIRECTIVA, 'presidente': {**DIRECTIVA['presidente'], 'rut': '10.234.567-0'}}
        r = self.client.post(API + 'organizaciones/', self.organizacion(directiva=mala), format='json')
        self.assertError(r, 400, 'rut_invalido', 'directiva.presidente.rut')
        repetida = {**DIRECTIVA, 'tesorero': {**DIRECTIVA['tesorero'], 'rut': '10.234.567-3'}}
        r = self.client.post(API + 'organizaciones/', self.organizacion(directiva=repetida), format='json')
        self.assertError(r, 400, 'rut_repetido', 'directiva.tesorero.rut')

    def test_permisos(self):
        self.entrar('juan.perez')  # sin «Gestionar organizaciones» ni catálogos
        self.assertError(self.client.post(API + 'organizaciones/', self.organizacion(), format='json'),
                         403, 'prohibido')
        self.entrar('laura.mena')  # Supervisor de DEL-001 y DEL-002: no puede crear en DEL-003
        r = self.client.post(API + 'organizaciones/',
                             self.organizacion(delegacionId=self.delegacion('DEL-003').pk), format='json')
        self.assertError(r, 403, 'prohibido', 'delegacionId')
        otra = OrganizacionComunitaria.objects.get(codigo='ORG-004')  # DEL-003
        self.assertError(self.client.delete(API + f'organizaciones/{otra.pk}/'), 403, 'prohibido')


# ================================================================ Persona 1: transacción Atenciones
class Atenciones(BaseApi):
    def atencion(self, usuario='juan.perez', delegacion='DEL-001', **cambios):
        tipo = TipoAtencion.objects.get(codigo='TAT-001')
        d = {'solicitante': 'Vecina del sector', 'rut': '10.234.567-3', 'telefono': '+56 9 1234 5678',
             'tipoId': tipo.pk, 'subId': SubAtencion.objects.get(codigo='SUB-001').pk,
             'itemId': ItemMeta.objects.get(codigo='ITM-001').pk, 'estado': Atencion.EJECUTADA,
             'descripcion': 'Orientación para postular a un subsidio.',
             'delegacionId': self.delegacion(delegacion).pk, 'responsableId': self.usuario(usuario).pk,
             'fecha': timezone.localdate().isoformat()}
        d.update(cambios)
        return d

    def crear(self, **cambios):
        r = self.client.post(API + 'atenciones/', self.atencion(**cambios), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_crud_completo(self):
        self.entrar('juan.perez')
        a = self.crear()
        self.assertEqual((a['puntaje'], a['etapa'], a['clasificacion']), (1, 'Realizado', 'Atención ciudadana'))
        self.assertTrue(a['codigo'].startswith('AT-'))
        url = API + f'atenciones/{a["id"]}/'
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.put(url, self.atencion(descripcion='Descripción corregida de la atención.'), format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['descripcion'], r.json()['codigo']), ('Descripción corregida de la atención.',
                                                                         a['codigo']))
        self.assertEqual(r.json()['puntaje'], 1)  # al editar no se cuenta a sí misma: sigue sumando
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Atencion.objects.filter(pk=a['id']).exists())

    def test_funcionario_no_ve_rut_ni_telefono_del_vecino(self):
        self.entrar('juan.perez')
        a = self.crear()
        self.assertNotIn('rut', a)
        self.assertNotIn('telefono', a)
        for fila in self.client.get(API + 'atenciones/').json()['results']:
            self.assertNotIn('telefono', fila)
        self.entrar_admin()
        completa = self.client.get(API + f'atenciones/{a["id"]}/').json()
        self.assertEqual((completa['rut'], completa['telefono']), ('10.234.567-3', '+56 9 1234 5678'))
        # El RUT y el teléfono sí se guardaron (write_only: se envían, no se leen).
        self.assertEqual(Atencion.objects.get(pk=a['id']).telefono, '+56 9 1234 5678')

    def test_alcance_propio_solo_ve_las_suyas(self):
        ajena = Atencion.objects.exclude(responsable__username='juan.perez').exclude(
            creado_por__username='juan.perez').first()
        self.entrar('juan.perez')
        self.assertError(self.client.get(API + f'atenciones/{ajena.pk}/'), 404, 'no_encontrado')
        self.entrar_admin()
        self.assertEqual(self.client.get(API + f'atenciones/{ajena.pk}/').status_code, 200)

    def test_sin_permiso_de_registrar(self):
        u = User.objects.create_user('consulta1', password='Clave1234!')
        Perfil.objects.create(user=u, rol=Rol.objects.get(nombre='Usuario de consulta'))
        self.entrar('consulta1', 'Clave1234!')
        self.assertError(self.client.post(API + 'atenciones/', self.atencion(), format='json'), 403, 'prohibido')

    def test_validaciones_de_negocio(self):
        self.entrar('juan.perez')
        r = self.client.post(API + 'atenciones/', self.atencion(telefono='123'), format='json')
        self.assertError(r, 400, 'telefono_invalido', 'telefono')
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertError(self.client.post(API + 'atenciones/', self.atencion(fecha=manana), format='json'),
                         400, 'fecha_futura', 'fecha')
        r = self.client.post(API + 'atenciones/', self.atencion(responsableId=self.usuario('carla.tapia').pk),
                             format='json')
        self.assertError(r, 400, 'responsable_invalido', 'responsableId')

    def test_limite_diario_excluye_la_propia_al_editar(self):
        self.entrar('juan.perez')
        creadas = [self.crear(estado=Atencion.PREPARACION) for _ in range(Atencion.MAX_POR_DIA)]
        self.assertError(self.client.post(API + 'atenciones/', self.atencion(), format='json'),
                         400, 'limite_diario', 'fecha')
        r = self.client.put(API + f'atenciones/{creadas[-1]["id"]}/',
                            self.atencion(estado=Atencion.PREPARACION, descripcion='Sigue en preparación, editada.'),
                            format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_editar_recalcula_puntaje(self):
        self.entrar('juan.perez')
        a = self.crear(estado=Atencion.PREPARACION)
        self.assertEqual(a['puntaje'], 0)
        r = self.client.put(API + f'atenciones/{a["id"]}/', self.atencion(), format='json')  # pasa a Ejecutada
        self.assertEqual((r.json()['estado'], r.json()['puntaje'], r.json()['etapa']), ('Ejecutada', 1, 'Realizado'))

    def test_ejecutada_no_vuelve_a_preparacion(self):
        self.entrar('juan.perez')
        a = self.crear()
        r = self.client.put(API + f'atenciones/{a["id"]}/', self.atencion(estado=Atencion.PREPARACION),
                            format='json')
        self.assertError(r, 409, 'ya_ejecutada', 'estado')

    def test_semana_cerrada_no_se_edita_ni_borra(self):
        vieja = Atencion.objects.filter(fecha__lt=timezone.localdate() - timedelta(days=14)).first()
        self.entrar_admin()
        url = API + f'atenciones/{vieja.pk}/'
        datos = self.atencion(usuario=vieja.responsable.username, delegacion=vieja.delegacion.codigo)
        self.assertError(self.client.put(url, datos, format='json'), 409, 'semana_cerrada', 'fecha')
        self.assertError(self.client.delete(url), 409, 'semana_cerrada', 'fecha')
        self.assertTrue(Atencion.objects.filter(pk=vieja.pk).exists())


# ================================================================ Persona 2: transacción Reclamos
class Reclamos(BaseApi):
    def reclamo(self, **cambios):
        d = {'delegacionId': self.delegacion('DEL-002').pk, 'funcionarioId': self.usuario('laura.mena').pk,
             'itemId': ItemMeta.objects.get(codigo='ITM-002').pk, 'fecha': (timezone.localdate()).isoformat(),
             'reclamante': 'Vecino del sector', 'motivo': 'No se presentó a la visita acordada.', 'puntos': 2,
             'respaldoTipo': 'Carta firmada', 'respaldoReferencia': 'Carta folio 2026-200'}
        d.update(cambios)
        return d

    def crear(self, **cambios):
        self.entrar('maria.rojas')  # Delegada de DEL-002
        r = self.client.post(API + 'reclamos/', self.reclamo(**cambios), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_crud_completo_como_delegado(self):
        rec = self.crear()
        self.assertEqual((rec['puntos'], rec['funcionario'], rec['registradoPor']), (2, 'Laura Mena', 'María Rojas'))
        url = API + f'reclamos/{rec["id"]}/'
        self.assertEqual(self.client.get(url).json()['reclamante'], 'Vecino del sector')
        r = self.client.put(url, self.reclamo(puntos=4), format='json')
        self.assertEqual((r.status_code, r.json()['puntos']), (200, 4))
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Reclamo.objects.filter(pk=rec['id']).exists())

    def test_solo_el_delegado_escribe(self):
        for usuario, clave in (('juan.perez', CLAVE_DEMO), ('laura.mena', CLAVE_DEMO), ('admin', 'Admin123!')):
            self.entrar(usuario, clave)
            self.assertError(self.client.post(API + 'reclamos/', self.reclamo(), format='json'), 403, 'prohibido')

    def test_delegado_de_otra_delegacion(self):
        self.entrar('maria.rojas')
        r = self.client.post(API + 'reclamos/', self.reclamo(delegacionId=self.delegacion('DEL-001').pk,
                                                            funcionarioId=self.usuario('juan.perez').pk),
                             format='json')
        self.assertError(r, 403, 'prohibido', 'delegacionId')

    def test_funcionario_ve_los_suyos_sin_datos_del_reclamante(self):
        rec = self.crear()
        self.entrar('laura.mena')
        lista = self.client.get(API + 'reclamos/').json()['results']
        self.assertEqual([x['id'] for x in lista], [rec['id']])
        self.assertNotIn('reclamante', lista[0])
        self.assertNotIn('respaldoReferencia', lista[0])
        self.assertEqual(lista[0]['motivo'], 'No se presentó a la visita acordada.')
        self.entrar('juan.perez')  # no tiene reclamos: no ve el de Laura
        self.assertEqual(self.client.get(API + 'reclamos/').json()['count'], 0)
        self.assertError(self.client.get(API + f'reclamos/{rec["id"]}/'), 404, 'no_encontrado')

    def test_administrador_ve_todo(self):
        rec = self.crear()
        self.entrar_admin()
        r = self.client.get(API + f'reclamos/{rec["id"]}/').json()
        self.assertEqual((r['reclamante'], r['respaldoReferencia']), ('Vecino del sector', 'Carta folio 2026-200'))

    def test_validaciones_de_negocio(self):
        self.entrar('maria.rojas')
        r = self.client.post(API + 'reclamos/', self.reclamo(respaldoReferencia='captura de WhatsApp'),
                             format='json')
        self.assertError(r, 400, 'respaldo_informal', 'respaldoReferencia')
        self.assertError(self.client.post(API + 'reclamos/', self.reclamo(puntos=9), format='json'),
                         400, 'numero_invalido', 'puntos')
        r = self.client.post(API + 'reclamos/', self.reclamo(funcionarioId=self.usuario('juan.perez').pk),
                             format='json')
        self.assertError(r, 400, 'referencia_invalida', 'funcionarioId')  # Juan no es del equipo de DEL-002

