from django.contrib import admin

from .models import CodigoRecuperacion


@admin.register(CodigoRecuperacion)
class CodigoRecuperacionAdmin(admin.ModelAdmin):
    list_display = ('user', 'creado', 'expira', 'intentos', 'usado')
    readonly_fields = ('codigo_hash',)
