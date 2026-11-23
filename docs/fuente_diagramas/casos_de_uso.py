"""Genera el Diagrama de Casos de Uso (SGR) como SVG por página y un HTML para imprimir a PDF."""
import html, math, sys

FONT = "Arial, Helvetica, sans-serif"

def ancho_texto(t, size=13, bold=True):
    return len(t) * size * (0.58 if bold else 0.52)

class Diagrama:
    def __init__(self, titulo, sistema, w, h, caja=(270, 70, 1040, None)):
        self.titulo, self.sistema, self.w, self.h = titulo, sistema, w, h
        x0, y0, x1, y1 = caja
        self.caja = (x0, y0, x1, y1 if y1 else h - 30)
        self.actores, self.cus, self.rel, self.out = {}, {}, [], []

    def actor(self, k, nombre, x, y):
        self.actores[k] = (nombre, x, y)

    def cu(self, k, nombre, x, y, w=None):
        lineas = nombre.split('\n')
        ancho = w or max(170, max(ancho_texto(l) for l in lineas) + 54)
        alto = 50 if len(lineas) == 1 else 66
        self.cus[k] = (lineas, x, y, ancho / 2, alto / 2)

    def asocia(self, a, c): self.rel.append(('asoc', a, c, None))
    def incluye(self, base, incl, off=(0, 0)): self.rel.append(('include', base, incl, off))
    def extiende(self, ext, base, off=(0, 0)): self.rel.append(('extend', ext, base, off))
    def generaliza(self, hijo, padre, dy=0): self.rel.append(('gen', hijo, padre, (0, dy)))

    # ---- geometría
    def borde_cu(self, k, hacia):
        _, cx, cy, a, b = self.cus[k]
        dx, dy = hacia[0] - cx, hacia[1] - cy
        if dx == dy == 0: return cx, cy
        t = 1 / math.sqrt((dx / a) ** 2 + (dy / b) ** 2)
        return cx + dx * t, cy + dy * t

    def punto_actor(self, k, hacia):
        _, x, y = self.actores[k]
        lado = 1 if hacia[0] > x else -1
        return x + 20 * lado, y - 22

    def centro(self, k):
        if k in self.cus: return self.cus[k][1], self.cus[k][2]
        _, x, y = self.actores[k]; return x, y - 22

    def extremo(self, k, hacia):
        return self.borde_cu(k, hacia) if k in self.cus else self.punto_actor(k, hacia)

    # ---- dibujo
    def flecha_abierta(self, p, q):
        ang = math.atan2(q[1] - p[1], q[0] - p[0]); L = 13; s = 0.42
        a1 = (q[0] - L * math.cos(ang - s), q[1] - L * math.sin(ang - s))
        a2 = (q[0] - L * math.cos(ang + s), q[1] - L * math.sin(ang + s))
        return f'<polyline points="{a1[0]:.1f},{a1[1]:.1f} {q[0]:.1f},{q[1]:.1f} {a2[0]:.1f},{a2[1]:.1f}" fill="none" stroke="#111" stroke-width="1.6"/>'

    def triangulo(self, p, q):
        ang = math.atan2(q[1] - p[1], q[0] - p[0]); L = 18; s = 0.5
        a1 = (q[0] - L * math.cos(ang - s), q[1] - L * math.sin(ang - s))
        a2 = (q[0] - L * math.cos(ang + s), q[1] - L * math.sin(ang + s))
        return f'<polygon points="{a1[0]:.1f},{a1[1]:.1f} {q[0]:.1f},{q[1]:.1f} {a2[0]:.1f},{a2[1]:.1f}" fill="#fff" stroke="#111" stroke-width="1.6"/>'

    def svg(self):
        o = []
        W, H = self.w, self.h
        o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">')
        o.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" fill="#fff" stroke="#111"/>')
        # marco del diagrama (pestaña uc)
        t = f'uc {self.titulo}'
        tw = ancho_texto(t, 13, False) + 26
        o.append(f'<path d="M0.5 0.5 H{tw} V20 L{tw-12} 32 H0.5" fill="#fff" stroke="#111"/>')
        o.append(f'<text x="8" y="21" font-size="13"><tspan font-weight="bold">uc</tspan> {html.escape(self.titulo)}</text>')
        x0, y0, x1, y1 = self.caja
        o.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="#fff" stroke="#111" stroke-width="1.8"/>')
        o.append(f'<text x="{(x0+x1)/2}" y="{y0+22}" text-anchor="middle" font-size="13.5" font-weight="bold">{html.escape(self.sistema)}</text>')
        # relaciones (debajo de las figuras)
        for tipo, a, b, off in self.rel:
            ca, cb = self.centro(a), self.centro(b)
            p, q = self.extremo(a, cb), self.extremo(b, ca)
            if tipo == 'gen' and off:
                q = (q[0] + 6, q[1] + off[1])
            if tipo == 'asoc':
                o.append(f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" stroke="#111" stroke-width="1.6"/>')
            elif tipo == 'gen':
                o.append(f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" stroke="#111" stroke-width="1.6"/>')
                o.append(self.triangulo(p, q))
            else:
                o.append(f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" stroke="#111" stroke-width="1.6" stroke-dasharray="7 5"/>')
                o.append(self.flecha_abierta(p, q))
                mx, my = (p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1]
                etiqueta = '«include»' if tipo == 'include' else '«extend»'
                o.append(f'<text x="{mx:.1f}" y="{my-7:.1f}" text-anchor="middle" font-size="12.5" paint-order="stroke" stroke="#fff" stroke-width="4">{etiqueta}</text>')
        # casos de uso
        for k, (lineas, x, y, a, b) in self.cus.items():
            o.append(f'<ellipse cx="{x}" cy="{y}" rx="{a:.1f}" ry="{b:.1f}" fill="#fff" stroke="#111" stroke-width="1.8"/>')
            y_ini = y - (len(lineas) - 1) * 8 + 5
            for i, l in enumerate(lineas):
                o.append(f'<text x="{x}" y="{y_ini + i*16:.1f}" text-anchor="middle" font-size="13" font-weight="bold">{html.escape(l)}</text>')
        # actores
        for k, (nombre, x, y) in self.actores.items():
            o.append(f'<g stroke="#111" stroke-width="1.8" fill="none"><circle cx="{x}" cy="{y-50}" r="9" fill="#fff"/>'
                     f'<line x1="{x}" y1="{y-41}" x2="{x}" y2="{y-12}"/><line x1="{x-17}" y1="{y-32}" x2="{x+17}" y2="{y-32}"/>'
                     f'<line x1="{x}" y1="{y-12}" x2="{x-15}" y2="{y+8}"/><line x1="{x}" y1="{y-12}" x2="{x+15}" y2="{y+8}"/></g>')
            for i, l in enumerate(nombre.split('\n')):
                o.append(f'<text x="{x}" y="{y+26+i*16}" text-anchor="middle" font-size="13" font-weight="bold">{html.escape(l)}</text>')
        o.append('</svg>')
        return '\n'.join(o)

SIS = 'SGR - Sistema de Gestión de Resultados'
paginas = []

# ---------------------------------------------------------------- 0. Actores
d = Diagrama('0. Actores', '', 1100, 760, caja=(0, 0, 0, 0))
d.caja = None
d.actor('UA', 'Usuario autenticado', 240, 420)
for i, (k, n) in enumerate([('AD', 'Administrador'), ('CO', 'Coordinador del\nsistema'), ('DE', 'Delegado /\nJefatura'),
                            ('FU', 'Funcionario'), ('VE', 'Verificador'), ('UC', 'Usuario de consulta')]):
    d.actor(k, n, 880, 120 + i * 108)
    d.generaliza(k, 'UA', -52 + i * 12)
paginas.append(d)

# ---------------------------------------------------------------- 1. General (épicas)
d = Diagrama('1. General (épicas)', SIS, 1240, 940, caja=(250, 60, 990, 910))
d.actor('UA', 'Usuario\nautenticado', 120, 160)
d.actor('AD', 'Administrador', 120, 360)
d.actor('CO', 'Coordinador del\nsistema', 120, 640)
d.actor('DE', 'Delegado /\nJefatura', 1120, 420)
d.actor('FU', 'Funcionario', 1120, 800)
d.actor('VE', 'Verificador', 1120, 610)
d.actor('UCo', 'Usuario de\nconsulta', 1120, 210)
cx = 620
d.cu('E1', 'E1. Gestionar acceso y cuenta', cx, 130, 330)
d.cu('E2', 'E2. Administrar el sistema', cx, 225, 330)
d.cu('E5', 'E3. Gestionar organizaciones\ncomunitarias', cx, 325, 330)
d.cu('E8', 'E4. Consultar y reportar\ninformación', cx, 430, 330)
d.cu('E6', 'E5. Supervisar desempeño\ndel equipo (Matriz SGR)', cx, 540, 330)
d.cu('E7', 'E6. Verificar registros', cx, 640, 330)
d.cu('E4', 'E7. Gestionar el tubo de\ncompromisos', cx, 740, 330)
d.cu('E3', 'E8. Gestionar actividades\nterritoriales', cx, 845, 330)
for a, e in [('UA', 'E1'), ('UA', 'E5'), ('AD', 'E2'), ('AD', 'E5'), ('CO', 'E8'), ('CO', 'E6'), ('CO', 'E7'),
             ('DE', 'E5'), ('DE', 'E8'), ('DE', 'E6'), ('DE', 'E4'), ('UCo', 'E8'), ('VE', 'E7'),
             ('FU', 'E4'), ('FU', 'E3')]:
    d.asocia(a, e)
paginas.append(d)

# ---------------------------------------------------------------- E1
d = Diagrama('2. Detalle E1 - Gestionar acceso y cuenta', 'E1. Gestionar acceso y cuenta', 1200, 560, caja=(260, 50, 1150, 530))
d.actor('UA', 'Usuario\nautenticado', 120, 300)
d.cu('ini', 'Iniciar sesión', 520, 130)
d.cu('cer', 'Cerrar sesión', 520, 225)
d.cu('cam', 'Cambiar contraseña', 520, 320)
d.cu('per', 'Actualizar datos de perfil', 520, 410)
d.cu('pre', 'Configurar preferencias\nde notificación', 520, 485)
d.cu('val', 'Validar credenciales', 930, 225)
d.cu('rec', 'Recuperar contraseña\npor código de correo', 930, 115)
d.cu('blo', 'Bloquear cuenta por\nintentos fallidos', 930, 330)
for c in ('ini', 'cer', 'cam', 'per', 'pre'): d.asocia('UA', c)
d.incluye('ini', 'val'); d.incluye('cam', 'val', (0, 18))
d.extiende('rec', 'ini'); d.extiende('blo', 'val', (40, 10))
paginas.append(d)

# ---------------------------------------------------------------- E2
d = Diagrama('3. Detalle E2 - Administrar el sistema', 'E2. Administrar el sistema', 1200, 640, caja=(260, 50, 1150, 610))
d.actor('AD', 'Administrador', 120, 340)
filas = [('usu', 'Gestionar usuarios'), ('rol', 'Gestionar roles y permisos'), ('del', 'Gestionar delegaciones'),
         ('cat', 'Gestionar catálogos\nde atención'), ('ite', 'Gestionar ítems y\nmetas trimestrales'),
         ('his', 'Consultar historial\nde cambios')]
for i, (k, n) in enumerate(filas):
    d.cu(k, n, 500, 115 + i * 92)
    d.asocia('AD', k)
d.cu('reg', 'Registrar cambio\nen el historial', 930, 310)
d.cu('res', 'Restablecer contraseña\nde un usuario', 930, 110)
for k in ('usu', 'rol', 'del', 'cat', 'ite'): d.incluye(k, 'reg')
d.extiende('res', 'usu')
paginas.append(d)

# ---------------------------------------------------------------- E3 Organizaciones
d = Diagrama('4. Detalle E3 - Gestionar organizaciones comunitarias', 'E3. Gestionar organizaciones comunitarias', 1240, 620, caja=(260, 50, 1180, 590))
d.actor('UA', 'Usuario\nautenticado', 120, 170)
d.actor('AD', 'Administrador', 120, 380)
d.actor('DE', 'Delegado /\nJefatura', 120, 540)
d.cu('con', 'Consultar organizaciones', 520, 130)
d.cu('reg', 'Registrar organización', 520, 250)
d.cu('act', 'Actualizar organización\ny su directiva', 520, 370)
d.cu('ver', 'Marcar organización como\nverificada', 520, 490)
d.cu('dir', 'Validar directiva\n(nombre, RUT y teléfono)', 950, 310)
d.cu('sub', 'Asignar subfamilia\nfuncional', 950, 160)
d.asocia('UA', 'con')
for a in ('AD', 'DE'):
    for c in ('reg', 'act', 'ver'): d.asocia(a, c)
d.incluye('reg', 'dir'); d.incluye('act', 'dir', (0, 20))
d.extiende('sub', 'reg')
paginas.append(d)

# ---------------------------------------------------------------- E4 Consultar y reportar
d = Diagrama('5. Detalle E4 - Consultar y reportar información', 'E4. Consultar y reportar información', 1240, 520, caja=(260, 50, 1180, 490))
d.actor('UCo', 'Usuario de\nconsulta', 120, 150)
d.actor('CO', 'Coordinador del\nsistema', 120, 300)
d.actor('DE', 'Delegado /\nJefatura', 120, 440)
d.cu('bus', 'Realizar búsqueda avanzada', 540, 140)
d.cu('inf', 'Generar informe de gestión', 540, 400)
d.cu('exp', 'Exportar resultados\n(Excel o PDF)', 560, 270)
d.cu('fil', 'Filtrar información\n(delegación, período, ítem…)', 965, 270)
for a in ('UCo', 'CO', 'DE'):
    d.asocia(a, 'bus'); d.asocia(a, 'inf')
d.incluye('bus', 'fil', (10, 0)); d.incluye('inf', 'fil', (10, 30))
d.extiende('exp', 'bus', (34, 6)); d.extiende('exp', 'inf', (34, 14))
paginas.append(d)

# ---------------------------------------------------------------- E5 Matriz SGR
d = Diagrama('6. Detalle E5 - Supervisar desempeño del equipo (Matriz SGR)', 'E5. Supervisar desempeño del equipo (Matriz SGR)', 1240, 700, caja=(260, 50, 1180, 670))
d.actor('DE', 'Delegado /\nJefatura', 120, 360)
d.actor('CO', 'Coordinador del\nsistema', 120, 140)
d.cu('com', 'Comparar desempeño\nde delegaciones', 520, 120)
d.cu('mat', 'Consultar matriz del\nequipo por trimestre', 520, 235)
d.cu('aus', 'Registrar ausencia\n(vacaciones, licencias)', 520, 360)
d.cu('fel', 'Registrar felicitación', 520, 475)
d.cu('rcl', 'Registrar reclamo', 520, 590)
d.cu('cum', 'Calcular cumplimiento\ntrimestral', 960, 175)
d.cu('rez', 'Identificar funcionarios\nrezagados', 960, 330)
d.cu('res', 'Validar respaldo formal', 960, 530)
d.asocia('CO', 'com'); d.asocia('CO', 'mat')
for c in ('mat', 'aus', 'fel', 'rcl'): d.asocia('DE', c)
d.incluye('com', 'cum'); d.incluye('mat', 'cum', (0, 22))
d.extiende('rez', 'mat', (0, 20))
d.incluye('fel', 'res'); d.incluye('rcl', 'res', (0, 22))
paginas.append(d)

# ---------------------------------------------------------------- E6 Verificar
d = Diagrama('7. Detalle E6 - Verificar registros', 'E6. Verificar registros', 1200, 520, caja=(260, 50, 1150, 490))
d.actor('VE', 'Verificador', 120, 200)
d.actor('CO', 'Coordinador del\nsistema', 120, 430)
d.cu('val', 'Validar registro', 520, 130)
d.cu('rec', 'Rechazar registro', 520, 270)
d.cu('obs', 'Responder observaciones\nde registros', 520, 420)
d.cu('evi', 'Revisar evidencia\ny respaldos', 930, 200)
d.cu('cor', 'Solicitar corrección', 930, 380)
d.asocia('VE', 'val'); d.asocia('VE', 'rec'); d.asocia('CO', 'obs')
d.incluye('val', 'evi'); d.incluye('rec', 'evi', (0, 22))
d.extiende('cor', 'rec')
paginas.append(d)

# ---------------------------------------------------------------- E7 Tubo
d = Diagrama('8. Detalle E7 - Gestionar el tubo de compromisos', 'E7. Gestionar el tubo de compromisos', 1240, 620, caja=(260, 50, 1180, 590))
d.actor('FU', 'Funcionario', 120, 200)
d.actor('DE', 'Delegado /\nJefatura', 120, 470)
d.cu('con', 'Consultar el tubo\n(lista o tablero)', 520, 125)
d.cu('ven', 'Revisar compromisos\nvencidos', 520, 240)
d.cu('mov', 'Mover compromiso\nde etapa', 520, 380)
d.cu('rea', 'Reasignar compromiso', 520, 510)
d.cu('fil', 'Filtrar compromisos\n(delegación, responsable, etapa)', 960, 180)
d.cu('rlz', 'Marcar compromiso\ncomo realizado', 960, 380)
for c in ('con', 'mov'): d.asocia('FU', c)
for c in ('con', 'mov', 'ven', 'rea'): d.asocia('DE', c)
d.incluye('con', 'fil'); d.incluye('ven', 'fil', (0, 28))
d.extiende('rlz', 'mov')
paginas.append(d)

# ---------------------------------------------------------------- E8 Actividades
d = Diagrama('9. Detalle E8 - Gestionar actividades territoriales', 'E8. Gestionar actividades territoriales', 1240, 640, caja=(260, 50, 1180, 610))
d.actor('FU', 'Funcionario', 120, 330)
d.cu('reg', 'Registrar atención\no actividad', 480, 150)
d.cu('evi', 'Adjuntar evidencia', 480, 290)
d.cu('eje', 'Marcar actividad\ncomo ejecutada', 480, 430)
d.cu('ava', 'Consultar mi avance', 480, 545)
d.cu('reglas', 'Validar reglas de ingreso\n(plazo semanal, máx. 7 diarias)', 790, 290)
d.cu('pun', 'Calcular puntaje\n(tope 120%)', 1065, 290, 190)
d.cu('org', 'Asociar a organización\npor RUT del dirigente', 820, 130)
d.cu('otra', 'Clasificar como\notra gestión', 1080, 190, 170)
for c in ('reg', 'eje', 'evi', 'ava'): d.asocia('FU', c)
d.incluye('reg', 'reglas', (-30, 6)); d.incluye('eje', 'reglas', (-30, 24))
d.incluye('reg', 'pun', (40, -6)); d.incluye('eje', 'pun', (40, 26))
d.extiende('org', 'reg', (0, 2)); d.extiende('otra', 'reg', (120, 30))
paginas.append(d)

# ---------------------------------------------------------------- salida
def svg_actores(d):
    s = d.svg()
    # la página de actores no lleva caja de sistema
    return s.replace('<rect x="0" y="0" width="0" height="0" fill="#fff" stroke="#111" stroke-width="1.8"/>', '').replace(
        '<text x="0.0" y="22" text-anchor="middle" font-size="13.5" font-weight="bold"></text>', '')

partes = []
for i, d in enumerate(paginas):
    if d.caja is None:
        d.caja = (0, 0, 0, 0)
        s = svg_actores(d)
    else:
        s = d.svg()
    partes.append(f'<section class="pag">{s}</section>')
html_doc = '''<!doctype html><html><head><meta charset="utf-8"><title>Diagrama de casos de uso - SGR</title>
<style>@page{size:1240px 940px; margin:0} body{margin:0} .pag{width:1240px; height:940px; display:flex; align-items:center; justify-content:center;
 page-break-after:always; break-after:page; overflow:hidden}
.pag:last-child{page-break-after:auto}</style></head><body>''' + '\n'.join(partes) + '</body></html>'
open(sys.argv[1], 'w').write(html_doc)
for i, d in enumerate(paginas):
    open(f'{sys.argv[2]}/pag{i}.svg', 'w').write(partes[i].split('>', 1)[1].rsplit('</section>', 1)[0])
print(len(paginas), 'páginas')
