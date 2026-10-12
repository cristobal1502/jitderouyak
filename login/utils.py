"""Utilidades compartidas: reglas de contraseña y contraseñas temporales."""
import secrets
import string

ESPECIALES = "!@#$%^&*()_+-=[]{};':\"\\|,.<>/?"


def validar_password(password):
    """Devuelve el 'caso' que falla (el mismo nombre que usa el front en su switch)
    o None si la contraseña cumple: 8+ caracteres, 1 mayúscula, 1 número, 1 especial."""
    if len(password) < 8:
        return 'password_corto'
    if not any(c.isupper() for c in password):
        return 'password_sin_mayuscula'
    if not any(c.isdigit() for c in password):
        return 'password_sin_numero'
    if not any(c in ESPECIALES for c in password):
        return 'password_sin_especial'
    return None


def generar_password_temporal(largo=12):
    """Contraseña aleatoria que cumple las reglas anteriores."""
    especiales = '!@#$%&*?'
    obligatorios = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(especiales),
    ]
    todos = string.ascii_letters + string.digits + especiales
    resto = [secrets.choice(todos) for _ in range(largo - len(obligatorios))]
    caracteres = obligatorios + resto
    secrets.SystemRandom().shuffle(caracteres)
    return ''.join(caracteres)


def enviar_correo_seguro(asunto, mensaje, destinatario):
    """Envía un correo sin romper la petición si el servidor de correo falla.
    En desarrollo (EmailBackend de consola) el correo se imprime en la terminal."""
    import logging
    from django.core.mail import send_mail
    try:
        send_mail(asunto, mensaje, None, [destinatario], fail_silently=False)
        return True
    except Exception:  # noqa: BLE001 - no queremos tumbar la vista por un error de SMTP
        logging.getLogger(__name__).exception('No se pudo enviar el correo a %s', destinatario)
        return False
