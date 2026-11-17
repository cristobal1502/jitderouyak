"""Cálculo de la Matriz SGR: puntaje por TRIMESTRE, metas ajustadas por ausencias,
traspaso del sobrante al trimestre siguiente y tope de 120%.

Reglas:
  - Cada actividad EJECUTADA suma 1 punto a su ítem. Las de PREPARACIÓN no suman.
  - Solo suman las atenciones ciudadanas con nombre y teléfono del vecino y con ítem.
  - Los períodos son trimestres: Q1 ene-mar, Q2 abr-jun, Q3 jul-sep, Q4 oct-dic.
  - Meta del funcionario en un ítem = meta trimestral del ítem × días hábiles disponibles / días
    hábiles del trimestre (las ausencias que ingresa el Delegado rebajan los días disponibles).
  - Sobrante: lo que un funcionario logró por sobre el 100% de la meta de un ítem al cerrar el
    trimestre pasa al trimestre siguiente, en ese mismo ítem. Como nada supera el 120%, el
    sobrante es como máximo un 20% de la meta.
  - Cuando un ítem llega al 120% de su meta (contando el sobrante recibido), deja de sumar: la
    actividad se guarda con 0 puntos y se avisa al usuario para que se enfoque en los ítems más bajos.
"""
import calendar
import math
from datetime import date, timedelta

from django.db.models import Sum

from .models import Atencion, Ausencia, ItemMeta

TOPE = 1.2                  # 120% de cumplimiento
VERDE, AMARILLO = 1.0, 0.7  # semáforo: ≥100% verde, ≥70% amarillo, bajo eso rojo
TRIMESTRES_ARRASTRE = 8     # cuántos trimestres hacia atrás se revisan para calcular el sobrante


# ------------------------------------------------------------------ trimestres
def trimestre_de(dia):
    return dia.year, (dia.month - 1) // 3 + 1


def rango_trimestre(anio, q):
    mes_fin = q * 3
    return date(anio, mes_fin - 2, 1), date(anio, mes_fin, calendar.monthrange(anio, mes_fin)[1])


def trimestre_anterior(anio, q):
    return (anio, q - 1) if q > 1 else (anio - 1, 4)


def nombre_trimestre(anio, q):
    return f'Q{q} {anio}'


# ------------------------------------------------------------------ días y metas
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


def factor_disponibilidad(user, anio, q, ausencias=None):
    """Fracción del trimestre que el funcionario estuvo disponible (1 = todo el trimestre)."""
    desde, hasta = rango_trimestre(anio, q)
    habiles = dias_habiles(desde, hasta)
    if not habiles:
        return 1.0
    return max(0, habiles - dias_ausente(user, desde, hasta, ausencias)) / habiles


def meta_ajustada(item, factor):
    return round(item.meta_trimestral * factor, 1)


def tope_puntos(meta):
    """Máximo de puntos que puede llegar a tener un ítem (120% de la meta)."""
    return math.floor(meta * TOPE + 1e-9)


def puntos(user, item, anio, q):
    """Puntos ganados en el trimestre (sin contar el sobrante recibido)."""
    desde, hasta = rango_trimestre(anio, q)
    return (Atencion.objects.filter(responsable=user, item=item, ejecutada_el__range=(desde, hasta))
            .aggregate(t=Sum('puntaje'))['t'] or 0)


def arrastre(user, item, anio, q):
    """Sobrante que llega al trimestre (anio, q) desde el trimestre anterior, en ese ítem.
    Se calcula en cadena: lo recibido en un trimestre también cuenta para su propio sobrante."""
    cadena = []
    a, t = anio, q
    for _ in range(TRIMESTRES_ARRASTRE):
        a, t = trimestre_anterior(a, t)
        cadena.append((a, t))
    cadena.reverse()  # del más antiguo al más reciente
    desde = rango_trimestre(*cadena[0])[0]
    hasta = rango_trimestre(*cadena[-1])[1]
    # Dos consultas en total: los puntos del período y las ausencias del período.
    por_trimestre = {}
    for dia, pts in Atencion.objects.filter(responsable=user, item=item, puntaje__gt=0,
                                            ejecutada_el__range=(desde, hasta)).values_list('ejecutada_el', 'puntaje'):
        clave = trimestre_de(dia)
        por_trimestre[clave] = por_trimestre.get(clave, 0) + pts
    if not por_trimestre:
        return 0.0
    ausencias = list(Ausencia.objects.filter(funcionario=user, desde__lte=hasta, hasta__gte=desde))
    sobrante = 0.0
    for a, t in cadena:
        pts = por_trimestre.get((a, t), 0)
        if not pts and not sobrante:
            continue
        meta = meta_ajustada(item, factor_disponibilidad(user, a, t, ausencias))
        sobrante = max(0.0, pts + sobrante - meta)
    return round(sobrante, 1)


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


# ------------------------------------------------------------------ puntaje de una actividad
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
    anio, q = trimestre_de(atencion.ejecutada_el)
    meta = meta_ajustada(atencion.item, factor_disponibilidad(atencion.responsable, anio, q))
    actuales = puntos(atencion.responsable, atencion.item, anio, q) + arrastre(atencion.responsable, atencion.item, anio, q)
    if actuales >= tope_puntos(meta):
        atencion.tope_alcanzado = True
        return {
            'item': atencion.item.nombre,
            'cumplimiento': round(cumplimiento(actuales, meta) * 100),
            'trimestre': nombre_trimestre(anio, q),
            'sugeridos': items_mas_bajos(atencion.responsable, anio, q, excluir=atencion.item_id),
        }
    atencion.puntaje = 1
    return None


# ------------------------------------------------------------------ resúmenes
def resumen_funcionario(user, anio, q, items=None, ausencias=None):
    """Puntos, sobrante recibido, meta y cumplimiento de cada ítem activo en un trimestre."""
    items = items if items is not None else list(ItemMeta.objects.filter(activo=True))
    factor = factor_disponibilidad(user, anio, q, ausencias)
    desde, hasta = rango_trimestre(anio, q)
    por_item = dict(Atencion.objects.filter(responsable=user, ejecutada_el__range=(desde, hasta))
                    .order_by().values('item').annotate(t=Sum('puntaje')).values_list('item', 't'))
    filas = []
    for item in items:
        meta = meta_ajustada(item, factor)
        pts = por_item.get(item.pk) or 0
        extra = arrastre(user, item, anio, q)
        total = pts + extra
        valor = cumplimiento(total, meta)
        filas.append({'itemId': item.pk, 'item': item.nombre, 'puntos': pts, 'arrastre': extra,
                      'total': round(total, 1), 'meta': meta,
                      'sobrante': round(max(0.0, total - meta), 1),
                      'cumplimiento': round(valor * 100), 'semaforo': semaforo(valor),
                      'enTope': total >= tope_puntos(meta)})
    return factor, filas


def items_mas_bajos(user, anio, q, excluir=None, cuantos=3):
    _, filas = resumen_funcionario(user, anio, q)
    filas = [f for f in filas if f['itemId'] != excluir and not f['enTope']]
    filas.sort(key=lambda f: (f['cumplimiento'], f['item']))
    return [{'item': f['item'], 'cumplimiento': f['cumplimiento']} for f in filas[:cuantos]]
