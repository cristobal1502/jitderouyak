import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import CodigoRecuperacion


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BaseLogin(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_datos_iniciales', '--demo', verbosity=0)

    def setUp(self):
        cache.clear()

    def intentar(self, usuario, password):
        return self.client.post(reverse('login'), {'usuario': usuario, 'password': password})

    def error_de(self, resp):
        m = re.search(r'data-error="([^"]*)"', resp.content.decode())
        return m.group(1) if m else None


class Login(BaseLogin):
    def test_usuario_o_correo(self):
        r = self.intentar('juan.perez', 'Demo1234!')
        self.assertRedirects(r, reverse('dashboard'), fetch_redirect_response=False)
        self.client.logout()
        r = self.intentar('JUAN.PEREZ@municipalidad.cl', 'Demo1234!')
        self.assertRedirects(r, reverse('dashboard'), fetch_redirect_response=False)

    def test_credenciales_invalidas(self):
        for u, p in (('juan.perez', 'Mala1234!'), ('no.existe', 'Demo1234!')):
            r = self.intentar(u, p)
            self.assertEqual((r.status_code, self.error_de(r)), (200, 'credenciales_invalidas'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_usuario_inactivo(self):
        r = self.intentar('ana.nunez', 'Demo1234!')
        self.assertEqual(self.error_de(r), 'usuario_inactivo')
        self.assertNotIn('_auth_user_id', self.client.session)
        # con clave incorrecta no se revela que está inactivo
        self.assertEqual(self.error_de(self.intentar('ana.nunez', 'Otra1234!')), 'credenciales_invalidas')

    def test_bloqueo_por_intentos(self):
        for _ in range(4):
            self.assertEqual(self.error_de(self.intentar('juan.perez', 'Mala1234!')), 'credenciales_invalidas')
        self.assertEqual(self.error_de(self.intentar('juan.perez', 'Mala1234!')), 'bloqueado')
        # aunque ahora acierte, sigue bloqueado
        self.assertEqual(self.error_de(self.intentar('juan.perez', 'Demo1234!')), 'bloqueado')
        cache.clear()
        self.assertEqual(self.intentar('juan.perez', 'Demo1234!').status_code, 302)

    def test_next_seguro(self):
        r = self.client.post(reverse('login') + '?next=/dashboard/agenda/', {'usuario': 'juan.perez', 'password': 'Demo1234!'})
        self.assertEqual(r['Location'], '/dashboard/agenda/')
        self.client.logout()
        r = self.client.post(reverse('login') + '?next=https://malo.example/', {'usuario': 'juan.perez', 'password': 'Demo1234!'})
        self.assertEqual(r['Location'], reverse('dashboard'))

    def test_logout(self):
        self.intentar('juan.perez', 'Demo1234!')
        r = self.client.get(reverse('logout'))
        self.assertRedirects(r, reverse('login'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)

    def test_login_ya_autenticado_va_al_dashboard(self):
        self.intentar('juan.perez', 'Demo1234!')
        self.assertRedirects(self.client.get(reverse('login')), reverse('dashboard'), fetch_redirect_response=False)


class RecuperarPassword(BaseLogin):
    def solicitar(self, email='juan.perez@municipalidad.cl'):
        return self.client.post(reverse('forgot_password'), {'email': email})

    def codigo_enviado(self):
        return re.search(r'es: (\d{6})', mail.outbox[-1].body).group(1)

    def validar(self, codigo):
        r = self.client.post(reverse('validar_codigo'), {'codigo': codigo})
        return r, r.json()

    def test_correo_no_registrado_o_inactivo(self):
        for email in ('nadie@municipalidad.cl', 'ana.nunez@municipalidad.cl'):
            r = self.solicitar(email)
            self.assertEqual(self.error_de(r), 'correo_no_registrado')
        self.assertEqual(self.error_de(self.solicitar('malo')), 'email_invalido')
        self.assertEqual(len(mail.outbox), 0)

    def test_flujo_completo(self):
        r = self.solicitar()
        self.assertRedirects(r, reverse('validar_codigo'), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        pagina = self.client.get(reverse('validar_codigo')).content.decode()
        self.assertIn('ju••••••••@municipalidad.cl', pagina)
        self.assertIn('data-intentos="3"', pagina)

        r, cuerpo = self.validar(self.codigo_enviado())
        self.assertEqual((r.status_code, cuerpo['ok']), (200, True))
        self.assertEqual(cuerpo['siguiente'], reverse('nueva_password'))

        r = self.client.post(reverse('nueva_password'), {'password1': 'Nueva123!', 'password2': 'Nueva123!'})
        self.assertRedirects(r, reverse('login'), fetch_redirect_response=False)
        login = self.client.get(reverse('login')).content.decode()
        self.assertIn('data-aviso="password_actualizada"', login)
        self.assertTrue(self.client.login(username='juan.perez', password='Nueva123!'))

    def test_codigo_incorrecto_y_agotado(self):
        self.solicitar()
        real = self.codigo_enviado()
        malo = '000000' if real != '000000' else '111111'
        r, c = self.validar(malo)
        self.assertEqual((c['error'], c['restantes']), ('codigo_incorrecto', 2))
        r, c = self.validar(malo)
        self.assertEqual(c['restantes'], 1)
        r, c = self.validar(malo)
        self.assertEqual(c['error'], 'intentos_agotados')
        # ni siquiera el código correcto sirve tras agotar los intentos
        r, c = self.validar(real)
        self.assertEqual(c['error'], 'intentos_agotados')

    def test_formato_y_expiracion(self):
        self.solicitar()
        real = self.codigo_enviado()
        self.assertEqual(self.validar('12ab56')[1]['error'], 'codigo_formato')
        self.assertEqual(self.validar('123')[1]['error'], 'codigo_formato')
        CodigoRecuperacion.objects.update(expira=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.validar(real)[1]['error'], 'codigo_expirado')

    def test_reenvio_con_espera_e_invalida_el_anterior(self):
        self.solicitar()
        primero = self.codigo_enviado()
        r = self.client.post(reverse('reenviar_codigo'))
        self.assertEqual((r.status_code, r.json()['error']), (429, 'espera'))
        CodigoRecuperacion.objects.update(creado=timezone.now() - timedelta(seconds=31))
        r = self.client.post(reverse('reenviar_codigo'))
        self.assertEqual(r.json()['ok'], True)
        segundo = self.codigo_enviado()
        self.assertEqual(len(mail.outbox), 2)
        if primero != segundo:
            self.assertEqual(self.validar(primero)[1]['error'], 'codigo_incorrecto')
        self.assertTrue(self.validar(segundo)[1]['ok'])

    def test_no_se_puede_saltar_el_codigo(self):
        self.assertRedirects(self.client.get(reverse('nueva_password')), reverse('forgot_password'), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('validar_codigo')), reverse('forgot_password'), fetch_redirect_response=False)
        self.assertEqual(self.client.post(reverse('validar_codigo'), {'codigo': '123456'}).status_code, 403)
        self.solicitar()  # solicitó, pero no validó el código
        self.assertRedirects(self.client.get(reverse('nueva_password')), reverse('forgot_password'), fetch_redirect_response=False)

    def test_nueva_password_valida_reglas(self):
        self.solicitar()
        self.validar(self.codigo_enviado())
        for p1, p2 in (('corta1!', 'corta1!'), ('sinnumero!!', 'sinnumero!!'), ('Distinta123!', 'Otra123!!')):
            r = self.client.post(reverse('nueva_password'), {'password1': p1, 'password2': p2})
            self.assertEqual(r.status_code, 200)
            self.assertIn('server-errors', r.content.decode())
        self.assertTrue(User.objects.get(username='juan.perez').check_password('Demo1234!'))

    def test_codigo_se_guarda_hasheado(self):
        self.solicitar()
        c = CodigoRecuperacion.objects.get()
        self.assertNotIn(self.codigo_enviado(), c.codigo_hash)
