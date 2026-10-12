from django.conf import settings
from django.db import models


class Delegacion(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=120)
    direccion = models.CharField(max_length=200)
    comuna = models.CharField(max_length=80)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'delegación'
        verbose_name_plural = 'delegaciones'

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'


class Rol(models.Model):
    ALCANCES = [
        ('Propio', 'Propio'),
        ('Delegación', 'Delegación'),
        ('Todas las delegaciones', 'Todas las delegaciones'),
    ]
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.TextField()
    permisos = models.JSONField(default=list)  # lista de textos, ver permisos.PERMISOS
    alcance = models.CharField(max_length=30, choices=ALCANCES)

    class Meta:
        ordering = ['id']
        verbose_name_plural = 'roles'

    def __str__(self):
        return self.nombre


class Perfil(models.Model):
    """Datos del sistema para cada usuario de Django (rol, delegaciones, preferencias).
    Comparte la clave primaria con auth.User, así Perfil.pk == User.pk."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                primary_key=True, related_name='perfil')
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name='perfiles')
    delegaciones = models.ManyToManyField(Delegacion, related_name='perfiles', blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    pref_vencidos = models.BooleanField(default=True)
    pref_evidencias = models.BooleanField(default=True)
    pref_resumen = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'perfiles'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.rol})'


class ItemMeta(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField()
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'ítem / meta'
        verbose_name_plural = 'ítems y metas'

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'


class TipoAtencion(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField()
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'tipo de atención'
        verbose_name_plural = 'tipos de atención'

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'


class SubAtencion(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=120)
    tipo = models.ForeignKey(TipoAtencion, on_delete=models.PROTECT, related_name='subatenciones')
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'sub atención'
        verbose_name_plural = 'sub atenciones'

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'


class Atencion(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    solicitante = models.CharField(max_length=150)
    tipo = models.ForeignKey(TipoAtencion, on_delete=models.PROTECT, related_name='atenciones')
    subatencion = models.ForeignKey(SubAtencion, on_delete=models.PROTECT, related_name='atenciones')
    descripcion = models.TextField()
    delegacion = models.ForeignKey(Delegacion, on_delete=models.PROTECT, related_name='atenciones')
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name='atenciones_a_cargo')
    fecha = models.DateField()
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='atenciones_creadas')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']
        verbose_name = 'atención'
        verbose_name_plural = 'atenciones'

    def __str__(self):
        return f'{self.codigo} · {self.solicitante}'
