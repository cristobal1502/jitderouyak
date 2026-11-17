"""Metas trimestrales, directiva de las organizaciones, beneficiario de la atención y tubo de trabajo.

Conversión de los datos existentes:
  - La meta mensual pasa a ser trimestral (× 3).
  - El «representante» de cada organización pasa a ser su presidente(a) (sin RUT: hay que completarlo).
  - Las atenciones ejecutadas quedan en la etapa «Realizado» del tubo; las en preparación, en «Ingresado».
    Todas reciben como plazo la fecha de la actividad + 7 días.
"""
from datetime import timedelta

import django.db.models.deletion
from django.db import migrations, models


def convertir_datos(apps, schema_editor):
    ItemMeta = apps.get_model('dashboard', 'ItemMeta')
    for item in ItemMeta.objects.all():
        item.meta_trimestral = min(item.meta_trimestral * 3, 1500)
        item.save(update_fields=['meta_trimestral'])

    Organizacion = apps.get_model('dashboard', 'OrganizacionComunitaria')
    for org in Organizacion.objects.exclude(representante=''):
        org.presidente_nombre = org.representante
        org.save(update_fields=['presidente_nombre'])

    Atencion = apps.get_model('dashboard', 'Atencion')
    for a in Atencion.objects.all():
        a.etapa = 'Realizado' if a.estado == 'Ejecutada' else 'Ingresado'
        a.fecha_compromiso = a.fecha + timedelta(days=7)
        a.save(update_fields=['etapa', 'fecha_compromiso'])


def revertir_datos(apps, schema_editor):
    ItemMeta = apps.get_model('dashboard', 'ItemMeta')
    for item in ItemMeta.objects.all():
        item.meta_trimestral = max(1, round(item.meta_trimestral / 3))
        item.save(update_fields=['meta_trimestral'])
    Organizacion = apps.get_model('dashboard', 'OrganizacionComunitaria')
    for org in Organizacion.objects.exclude(presidente_nombre=''):
        org.representante = org.presidente_nombre
        org.save(update_fields=['representante'])


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0006_rut_del_vecino'),
    ]

    operations = [
        # Ítems: meta mensual → meta trimestral
        migrations.RenameField(model_name='itemmeta', old_name='meta_mensual', new_name='meta_trimestral'),
        migrations.AlterField(model_name='itemmeta', name='meta_trimestral',
                              field=models.PositiveSmallIntegerField(default=30)),

        # Organizaciones: directiva con RUT
        migrations.AddField(model_name='organizacioncomunitaria', name='presidente_nombre',
                            field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name='organizacioncomunitaria', name='presidente_rut',
                            field=models.CharField(blank=True, db_index=True, max_length=12)),
        migrations.AddField(model_name='organizacioncomunitaria', name='tesorero_nombre',
                            field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name='organizacioncomunitaria', name='tesorero_rut',
                            field=models.CharField(blank=True, db_index=True, max_length=12)),
        migrations.AddField(model_name='organizacioncomunitaria', name='secretario_nombre',
                            field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name='organizacioncomunitaria', name='secretario_rut',
                            field=models.CharField(blank=True, db_index=True, max_length=12)),

        # Atención: para quién es y su etapa en el tubo
        migrations.AddField(model_name='atencion', name='beneficiario',
                            field=models.CharField(choices=[('Persona natural', 'Persona natural'),
                                                            ('Organización', 'Organización')],
                                                   default='Persona natural', max_length=20)),
        migrations.AddField(model_name='atencion', name='organizacion',
                            field=models.ForeignKey(blank=True, null=True,
                                                    on_delete=django.db.models.deletion.PROTECT,
                                                    related_name='atenciones',
                                                    to='dashboard.organizacioncomunitaria')),
        migrations.AddField(model_name='atencion', name='etapa',
                            field=models.CharField(choices=[('Ingresado', 'Ingresado'), ('Pendiente', 'Pendiente'),
                                                            ('En proceso', 'En proceso'), ('Realizado', 'Realizado')],
                                                   default='Ingresado', max_length=20)),
        migrations.AddField(model_name='atencion', name='fecha_compromiso',
                            field=models.DateField(blank=True, null=True)),

        migrations.RunPython(convertir_datos, revertir_datos),

        migrations.RemoveField(model_name='organizacioncomunitaria', name='representante'),
    ]
