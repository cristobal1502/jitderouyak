import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class CodigoRecuperacion(models.Model):
    """Código de 6 dígitos para recuperar contraseña.

    Se guarda hasheado (como una contraseña), con vigencia, intentos fallidos
    y un indicador de uso. Emitir un código nuevo invalida los anteriores.
    """
    VIGENCIA_SEGUNDOS = 5 * 60
    MAX_INTENTOS = 3
    COOLDOWN_SEGUNDOS = 30

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='codigos_recuperacion')
    codigo_hash = models.CharField(max_length=128)
    creado = models.DateTimeField(auto_now_add=True)
    expira = models.DateTimeField()
    intentos = models.PositiveSmallIntegerField(default=0)
    usado = models.BooleanField(default=False)

    class Meta:
        ordering = ['-creado']

    def __str__(self):
        return f'Código de {self.user} ({self.creado:%d/%m/%Y %H:%M})'

    @classmethod
    def emitir(cls, user):
        """Invalida los códigos anteriores y crea uno nuevo. Devuelve (objeto, código en claro)."""
        cls.objects.filter(user=user, usado=False).update(usado=True)
        codigo = f'{secrets.randbelow(10 ** 6):06d}'
        obj = cls.objects.create(
            user=user,
            codigo_hash=make_password(codigo),
            expira=timezone.now() + timedelta(seconds=cls.VIGENCIA_SEGUNDOS),
        )
        return obj, codigo

    @classmethod
    def vigente_de(cls, user):
        """Último código sin usar del usuario (puede estar expirado), o None."""
        return cls.objects.filter(user=user, usado=False).order_by('-creado').first()

    def coincide(self, codigo):
        return check_password(codigo, self.codigo_hash)

    @property
    def segundos_restantes(self):
        return max(0, int((self.expira - timezone.now()).total_seconds()))

    @property
    def intentos_restantes(self):
        return max(0, self.MAX_INTENTOS - self.intentos)

    @property
    def cooldown_restante(self):
        pasado = (timezone.now() - self.creado).total_seconds()
        return max(0, int(self.COOLDOWN_SEGUNDOS - pasado))
