import re
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import CodigoRecuperacion
from .utils import enviar_correo_seguro, validar_password

CORREO_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
MAX_FALLOS_LOGIN = 5
BLOQUEO_SEGUNDOS = 15 * 60
VALIDEZ_CODIGO_OK = timedelta(minutes=10)  # tiempo para crear la contraseña tras validar el código


# --------------------------------------------------------------------- login
def _clave_fallos(usuario):
    return 'sgr_login_fallos:' + usuario.lower()


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    contexto = {'aviso': request.session.pop('aviso_login', ''), 'error': '', 'usuario': ''}

    if request.method == 'POST':
        usuario = request.POST.get('usuario', '').strip()
        password = request.POST.get('password', '')
        contexto['usuario'] = usuario
        clave = _clave_fallos(usuario)

        if cache.get(clave, 0) >= MAX_FALLOS_LOGIN:
            contexto['error'] = 'bloqueado'
        else:
            # El usuario puede escribir su nombre de usuario o su correo.
            candidato = (User.objects.filter(username__iexact=usuario).first()
                         or User.objects.filter(email__iexact=usuario).first())
            if candidato is not None and not candidato.is_active and candidato.check_password(password):
                contexto['error'] = 'usuario_inactivo'
            else:
                user = authenticate(request, username=candidato.username, password=password) if candidato else None
                if user is None:
                    fallos = cache.get(clave, 0) + 1
                    cache.set(clave, fallos, BLOQUEO_SEGUNDOS)
                    contexto['error'] = 'bloqueado' if fallos >= MAX_FALLOS_LOGIN else 'credenciales_invalidas'
                else:
                    cache.delete(clave)
                    login(request, user)
                    if not request.POST.get('recordar'):
                        request.session.set_expiry(0)  # la sesión termina al cerrar el navegador
                    destino = request.POST.get('next') or request.GET.get('next') or ''
                    if destino and url_has_allowed_host_and_scheme(destino, {request.get_host()}):
                        return redirect(destino)
                    return redirect('dashboard')

    contexto['next'] = request.POST.get('next') or request.GET.get('next') or ''
    return render(request, 'login/login.html', contexto)


def logout_view(request):
    logout(request)
    return redirect('login')


# ------------------------------------------------------ recuperar contraseña
def _enmascarar(correo):
    usuario, _, dominio = correo.partition('@')
    return usuario[:2] + '•' * max(len(usuario) - 2, 2) + '@' + dominio


def _enviar_codigo(user):
    """Emite un código nuevo y lo envía por correo."""
    _, codigo = CodigoRecuperacion.emitir(user)
    minutos = CodigoRecuperacion.VIGENCIA_SEGUNDOS // 60
    enviar_correo_seguro(
        'Código para recuperar tu contraseña — SGR Municipal',
        f'Hola,\n\nTu código de verificación es: {codigo}\n\n'
        f'Vence en {minutos} minutos. Si no lo solicitaste, ignora este mensaje.',
        user.email)


def forgot_password_view(request):
    """Paso 1: el usuario ingresa su correo y se le envía un código."""
    contexto = {'error': '', 'email': ''}
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        contexto['email'] = email
        if not CORREO_RE.match(email):
            contexto['error'] = 'email_invalido'
        else:
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user is None:
                contexto['error'] = 'correo_no_registrado'
            else:
                vigente = CodigoRecuperacion.vigente_de(user)
                # Si pide otro código antes del cooldown, se reutiliza el último (anti-spam).
                if vigente is None or vigente.cooldown_restante == 0:
                    _enviar_codigo(user)
                request.session['reset_user_id'] = user.pk
                request.session.pop('reset_ok_user', None)
                return redirect('validar_codigo')
    return render(request, 'login/forgot_password.html', contexto)


def _usuario_en_recuperacion(request):
    uid = request.session.get('reset_user_id')
    return User.objects.filter(pk=uid, is_active=True).first() if uid else None


def validar_codigo_view(request):
    """Paso 2: pantalla para ingresar el código. La validación la hace el servidor
    (vigencia, intentos fallidos y reenvío) y el front le consulta por fetch (POST)."""
    user = _usuario_en_recuperacion(request)

    if request.method == 'POST':
        if user is None:
            return JsonResponse({'error': 'sesion_invalida', 'redirect': reverse('forgot_password')}, status=403)
        codigo = request.POST.get('codigo', '').strip()
        if not re.fullmatch(r'\d{6}', codigo):
            return JsonResponse({'error': 'codigo_formato'}, status=400)

        vigente = CodigoRecuperacion.vigente_de(user)
        if vigente is None or vigente.segundos_restantes == 0:
            return JsonResponse({'error': 'codigo_expirado'}, status=400)
        if vigente.intentos >= CodigoRecuperacion.MAX_INTENTOS:
            return JsonResponse({'error': 'intentos_agotados'}, status=400)

        if not vigente.coincide(codigo):
            vigente.intentos += 1
            vigente.save(update_fields=['intentos'])
            if vigente.intentos_restantes == 0:
                return JsonResponse({'error': 'intentos_agotados'}, status=400)
            return JsonResponse({'error': 'codigo_incorrecto', 'restantes': vigente.intentos_restantes}, status=400)

        vigente.usado = True
        vigente.save(update_fields=['usado'])
        request.session['reset_ok_user'] = user.pk
        request.session['reset_ok_ts'] = timezone.now().timestamp()
        return JsonResponse({'ok': True, 'siguiente': reverse('nueva_password')})

    if user is None:
        return redirect('forgot_password')
    vigente = CodigoRecuperacion.vigente_de(user)
    return render(request, 'login/validar_codigo.html', {
        'correo_enmascarado': _enmascarar(user.email),
        'vigencia': vigente.segundos_restantes if vigente else 0,
        'intentos': vigente.intentos_restantes if vigente else 0,
        'cooldown': vigente.cooldown_restante if vigente else 0,
        'max_intentos': CodigoRecuperacion.MAX_INTENTOS,
    })


@require_POST
def reenviar_codigo_view(request):
    user = _usuario_en_recuperacion(request)
    if user is None:
        return JsonResponse({'error': 'sesion_invalida', 'redirect': reverse('forgot_password')}, status=403)
    vigente = CodigoRecuperacion.vigente_de(user)
    if vigente is not None and vigente.cooldown_restante > 0:
        return JsonResponse({'error': 'espera', 'segundos': vigente.cooldown_restante}, status=429)
    _enviar_codigo(user)
    return JsonResponse({
        'ok': True,
        'vigencia': CodigoRecuperacion.VIGENCIA_SEGUNDOS,
        'intentos': CodigoRecuperacion.MAX_INTENTOS,
        'cooldown': CodigoRecuperacion.COOLDOWN_SEGUNDOS,
    })


def nueva_password_view(request):
    """Paso 3: crear la nueva contraseña (solo si el código fue validado) y volver al login."""
    uid = request.session.get('reset_ok_user')
    ts = request.session.get('reset_ok_ts')
    vigente = bool(uid and ts and timezone.now().timestamp() - ts <= VALIDEZ_CODIGO_OK.total_seconds())
    user = User.objects.filter(pk=uid, is_active=True).first() if vigente else None
    if user is None:
        return redirect('forgot_password')

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        caso = validar_password(password1)
        if caso:
            messages.error(request, {
                'password_corto': 'La contraseña debe tener al menos 8 caracteres.',
                'password_sin_mayuscula': 'La contraseña debe incluir al menos una mayúscula.',
                'password_sin_numero': 'La contraseña debe incluir al menos un número.',
                'password_sin_especial': 'La contraseña debe incluir al menos un carácter especial.',
            }[caso])
        elif password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
        else:
            user.set_password(password1)
            user.save()
            for clave in ('reset_user_id', 'reset_ok_user', 'reset_ok_ts'):
                request.session.pop(clave, None)
            request.session['aviso_login'] = 'password_actualizada'
            return redirect('login')

    return render(request, 'login/reset_password.html', {'valid_link': True})
