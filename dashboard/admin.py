from django.contrib import admin

from .models import Atencion, Delegacion, ItemMeta, Perfil, Rol, SubAtencion, TipoAtencion

admin.site.register([Delegacion, Rol, Perfil, ItemMeta, TipoAtencion, SubAtencion, Atencion])
