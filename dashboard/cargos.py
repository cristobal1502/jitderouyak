"""Los 7 perfiles de cargo de una delegación, como roles del sistema.

(nombre, descripción de funciones, permisos, alcance). Los permisos deben existir en
permisos.PERMISOS. La migración 0005 los crea en bases existentes; cargar_datos_iniciales
también los usa en instalaciones nuevas.
"""
ROLES_CARGO = [
    ('Delegado',
     'Representante directo del alcalde en el territorio. Visita a los vecinos, detecta problemas '
     'locales (seguridad, limpieza, áreas verdes), coordina mesas de trabajo y dirige al equipo de la '
     'delegación. Registra ausencias y felicitaciones de su equipo.',
     ['Ver panel', 'Registrar actividades', 'Validar evidencias', 'Gestionar agenda',
      'Gestionar organizaciones', 'Exportar informes'], 'Delegación'),
    ('Gestor Social (Trabajador Social)',
     'Atiende casos sociales de personas vulnerables, hace visitas a domicilio, deriva a ayudas '
     'municipales y organiza programas comunitarios.',
     ['Ver panel', 'Registrar actividades'], 'Propio'),
    ('Apoyo Administrativo',
     'Atiende al público en oficina, lleva la agenda del delegado, registra las atenciones en la '
     'planilla SGR, maneja el transporte, el inventario y los trámites internos.',
     ['Ver panel', 'Registrar actividades', 'Gestionar agenda'], 'Delegación'),
    ('Organizaciones Comunitarias',
     'Ayuda a crear, legalizar y capacitar a Juntas de Vecinos y agrupaciones funcionales, mantiene '
     'actualizado su registro y convoca a actividades municipales.',
     ['Ver panel', 'Registrar actividades', 'Gestionar organizaciones'], 'Delegación'),
    ('Gestor de Compras y Proyectos',
     'Tramita las compras de materiales y la contratación de servicios que necesita la delegación, '
     'revisando presupuestos y plazos.',
     ['Ver panel', 'Registrar actividades'], 'Propio'),
    ('Gestión y Planificación',
     'Revisa que las metas diarias se cumplan, analiza los puntajes de la matriz SGR para detectar '
     'fallas o mejoras, prepara informes y coordina las reuniones semanales.',
     ['Ver panel', 'Registrar actividades', 'Gestionar agenda', 'Exportar informes'], 'Delegación'),
    ('Coordinador de Servicios Comunitarios',
     'Organiza operativos de limpieza, desmalezado, reciclaje y recuperación de espacios públicos; '
     'además supervisa a las cuadrillas de emergencia y empleabilidad.',
     ['Ver panel', 'Registrar actividades', 'Gestionar agenda'], 'Delegación'),
]
