"""Cálculo de la Matriz SGR: puntaje, metas ajustadas por ausencias y tope de 120%.

Reglas:
  - Cada actividad EJECUTADA suma 1 punto a su ítem. Las de PREPARACIÓN no suman.
  - Solo suman las atenciones ciudadanas con nombre y teléfono del vecino y con ítem.
  - Meta del funcionario en un ítem = meta mensual del ítem × días hábiles disponibles / días hábiles
    del mes (las ausencias que ingresa el Delegado rebajan los días disponibles).
  - Cuando un ítem llega al 120% de su meta, deja de sumar: la actividad se guarda con 0 puntos
    y se avisa al usuario para que se enfoque en los ítems más bajos.
"""
import calendar
import math
from datetime import date, timedelta

from django.db.models import Sum

from .models import Atencion, Ausencia, ItemMeta

TOPE = 1.2             # 120% de cumplimiento
VERDE, AMARILLO = 1.0, 0.7  # semáforo: ≥100% verde, ≥70% amarillo, bajo eso rojo


def rango_mes(anio, mes):
    return date(anio, mes, 1), date(anio, mes, calendar.monthrange(anio, mes)[1])


def dias_habiles(desde, hasta):
    """Días de lunes a viernes entre dos fechas (ambas incluidas)."""
    if hasta < desde:
        return 0
    total = 0
    dia = desde
    while dia <= hasta:
        if dia.weekday() < 5:
            total += 1
        dia += timedelta(days=1)
    return total


def dias_ausente(user, desde, hasta, ausencias=None):
    """Días hábiles del rango en que el funcionario estuvo ausente (sin contar dos veces los traslapes)."""
    if ausencias is None:
        ausencias = Ausencia.objects.filter(funcionario=user, desde__lte=hasta, hasta__gte=desde)
    dias = set()
    for a in ausencias:
        dia = max(a.desde, desde)
        while dia <= min(a.hasta, hasta):
            if dia.weekday() < 5:
                dias.add(dia)
            dia += timedelta(days=1)
    return len(dias)


def factor_disponibilidad(user, anio, mes, ausencias=None):
    """Fracción del mes que el funcionario estuvo disponible (1 = todo el mes)."""
    desde, hasta = rango_mes(anio, mes)
    habiles = dias_habiles(desde, hasta)
    if not habiles:
        return 1.0
    return max(0, habiles - dias_ausente(user, desde, hasta, ausencias)) / habiles


def meta_ajustada(item, factor):
    return round(item.meta_mensual * factor, 1)


def tope_puntos(meta):
    """Máximo de puntos que puede sumar un ítem (120% de la meta)."""
    return math.floor(meta * TOPE + 1e-9)


def puntos(user, item, anio, mes):
    desde, hasta = rango_mes(anio, mes)
    return (Atencion.objects.filter(responsable=user, item=item, ejecutada_el__range=(desde, hasta))
            .aggregate(t=Sum('puntaje'))['t'] or 0)


def cumplimiento(pts, meta):
    if meta <= 0:
        return 1.0 if pts == 0 else TOPE
    return pts / meta


def semaforo(valor):
    if valor >= VERDE:
        return 'verde'
    if valor >= AMARILLO:
        return 'amarillo'
    return 'rojo'


def suma_puntaje(atencion):
    """True si la actividad cumple las condiciones para sumar (sin mirar el tope)."""
    return (atencion.estado == Atencion.EJECUTADA and atencion.clasificacion == Atencion.CIUDADANA
            and bool(atencion.telefono) and atencion.item_id is not None
            and atencion.ejecutada_el is not None)


def asignar_puntaje(atencion):
    """Calcula puntaje y tope_alcanzado de una atención antes de guardarla.
    Devuelve una alerta (dict) si el ítem ya estaba en el 120%, o None."""
    atencion.puntaje = 0
    atencion.tope_alcanzado = False
    if not suma_puntaje(atencion):
        return None
    dia = atencion.ejecutada_el
    meta = meta_ajustada(atencion.item, factor_disponibilidad(atencion.responsable, dia.year, dia.month))
    actuales = puntos(atencion.responsable, atencion.item, dia.year, dia.month)
    if actuales >= tope_puntos(meta):
        atencion.tope_alcanzado = True
        return {
            'item': atencion.item.nombre,
            'cumplimiento': round(cumplimiento(actuales, meta) * 100),
            'sugeridos': items_mas_bajos(atencion.responsable, dia.year, dia.month, excluir=atencion.item_id),
        }
    atencion.puntaje = 1
    return None


def resumen_funcionario(user, anio, mes, items=None, ausencias=None):
    """Puntos, meta y cumplimiento de cada ítem activo para un funcionario en un mes."""
    items = items if items is not None else list(ItemMeta.objects.filter(activo=True))
    factor = factor_disponibilidad(user, anio, mes, ausencias)
    desde, hasta = rango_mes(anio, mes)
    por_item = dict(Atencion.objects.filter(responsable=user, ejecutada_el__range=(desde, hasta))
                    .order_by().values('item').annotate(t=Sum('puntaje')).values_list('item', 't'))
    filas = []
    for item in items:
        meta = meta_ajustada(item, factor)
        pts = por_item.get(item.pk) or 0
        valor = cumplimiento(pts, meta)
        filas.append({'itemId': item.pk, 'item': item.nombre, 'puntos': pts, 'meta': meta,
                      'cumplimiento': round(valor * 100), 'semaforo': semaforo(valor),
                      'enTope': pts >= tope_puntos(meta)})
    return factor, filas


def items_mas_bajos(user, anio, mes, excluir=None, cuantos=3):
    _, filas = resumen_funcionario(user, anio, mes)
    filas = [f for f in filas if f['itemId'] != excluir and not f['enTope']]
    filas.sort(key=lambda f: (f['cumplimiento'], f['item']))
    return [{'item': f['item'], 'cumplimiento': f['cumplimiento']} for f in filas[:cuantos]]
