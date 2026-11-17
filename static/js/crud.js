/* ============================================================
   crud.js — motor genérico para los 6 mantenedores de Administración.
   La entidad se toma de <body data-entidad="...">. Cada entidad se
   describe en ENTIDADES (campos y columnas). Los datos viven en la
   base de datos: se leen y escriben con la API (api.js).
   ============================================================ */

// Debe coincidir con dashboard/permisos.py (PERMISOS).
const OPC_PERMISOS = [
  'Ver panel', 'Registrar actividades', 'Validar evidencias', 'Gestionar agenda',
  'Gestionar usuarios', 'Administrar catálogos', 'Gestionar organizaciones', 'Exportar informes'
];
const OPC_ALCANCE = ['Propio', 'Delegación', 'Todas las delegaciones'];
// Deben coincidir con OrganizacionComunitaria (dashboard/models.py).
const ORG_TERRITORIAL = 'Territorial (Junta de Vecinos)';
const ORG_FUNCIONAL = 'Funcional';
const OPC_SUBCATEGORIAS = [
  'Club de Adulto Mayor',
  'Organización Deportiva',
  'Centro de Madres, Cultural o Agrupación Juvenil',
  'Comité de Vecinos, Allegados o Seguridad'
];
const OPC_VERIFICACION = ['Pendiente de revisión', 'Verificado'];
const CARGOS_DIRECTIVA = [['presidente', 'Presidente(a)'], ['tesorero', 'Tesorero(a)'], ['secretario', 'Secretario(a)']];

// 'api' es el nombre de la entidad en la API; 'refApi' apunta a la entidad referenciada.
const ENTIDADES = {
  'delegaciones': {
    titulo: 'Delegaciones',
    subtitulo: 'Código, nombre, dirección, comuna y estado',
    api: 'delegaciones', nuevoLabel: 'Nueva delegación', singular: 'delegación',
    campos: [
      { key: 'codigo', label: 'Código', tipo: 'texto', auto: true },
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'direccion', label: 'Dirección', tipo: 'texto', requerido: true },
      { key: 'comuna', label: 'Comuna', tipo: 'texto', requerido: true },
      { key: 'estado', label: 'Estado', tipo: 'estado' }
    ],
    columnas: ['codigo', 'nombre', 'direccion', 'comuna', 'estado']
  },

  'roles': {
    titulo: 'Roles',
    subtitulo: 'Nombre, descripción, permisos y alcance autorizado',
    api: 'roles', nuevoLabel: 'Nuevo rol', singular: 'rol',
    campos: [
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'descripcion', label: 'Descripción', tipo: 'textarea', requerido: true },
      { key: 'permisos', label: 'Permisos', tipo: 'multiopcion', opciones: OPC_PERMISOS, requerido: true },
      { key: 'alcance', label: 'Alcance autorizado', tipo: 'opcion', opciones: OPC_ALCANCE, requerido: true }
    ],
    columnas: ['nombre', 'descripcion', 'permisos', 'alcance']
  },

  'usuarios': {
    titulo: 'Usuarios',
    subtitulo: 'Nombre, correo, rol, delegaciones autorizadas y estado',
    api: 'usuarios', nuevoLabel: 'Nuevo usuario', singular: 'usuario',
    campos: [
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'correo', label: 'Correo', tipo: 'correo', requerido: true },
      { key: 'rolId', label: 'Rol', tipo: 'ref', refApi: 'roles', requerido: true },
      { key: 'delegaciones', label: 'Delegaciones autorizadas', tipo: 'multiref', refApi: 'delegaciones', requerido: true },
      { key: 'estado', label: 'Estado', tipo: 'estado' }
    ],
    columnas: ['nombre', 'correo', 'rolId', 'delegaciones', 'estado'],
    accionesExtra: [{ accion: 'reiniciar', label: 'Clave', ayuda: 'Restablecer contraseña' }]
  },

  'items': {
    titulo: 'Ítems y metas',
    subtitulo: 'Ítems de la matriz SGR y su meta trimestral por funcionario (1 punto por actividad ejecutada)',
    api: 'items', nuevoLabel: 'Nuevo ítem', singular: 'ítem',
    campos: [
      { key: 'codigo', label: 'Código', tipo: 'texto', auto: true },
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'descripcion', label: 'Descripción', tipo: 'textarea', requerido: true },
      { key: 'metaTrimestral', label: 'Meta trimestral (puntos por funcionario)', tipo: 'numero', min: 1, max: 1500, requerido: true },
      { key: 'estado', label: 'Estado', tipo: 'estado' }
    ],
    columnas: ['codigo', 'nombre', 'descripcion', 'metaTrimestral', 'estado']
  },

  'tipos-atencion': {
    titulo: 'Tipos de atención',
    subtitulo: 'Código, nombre, descripción y estado',
    api: 'tipos-atencion', nuevoLabel: 'Nuevo tipo de atención', singular: 'tipo de atención',
    campos: [
      { key: 'codigo', label: 'Código', tipo: 'texto', auto: true },
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'descripcion', label: 'Descripción', tipo: 'textarea', requerido: true },
      { key: 'estado', label: 'Estado', tipo: 'estado' }
    ],
    columnas: ['codigo', 'nombre', 'descripcion', 'estado']
  },

  'sub-atenciones': {
    titulo: 'Sub atenciones',
    subtitulo: 'Código, nombre, tipo de atención asociado y estado',
    api: 'sub-atenciones', nuevoLabel: 'Nueva sub atención', singular: 'sub atención',
    campos: [
      { key: 'codigo', label: 'Código', tipo: 'texto', auto: true },
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'tipoId', label: 'Tipo de atención', tipo: 'ref', refApi: 'tipos-atencion', requerido: true },
      { key: 'estado', label: 'Estado', tipo: 'estado' }
    ],
    columnas: ['codigo', 'nombre', 'tipoId', 'estado']
  },

  'organizaciones': {
    titulo: 'Registro de organizaciones',
    subtitulo: 'Juntas de vecinos y organizaciones funcionales, con su estado de verificación',
    api: 'organizaciones', nuevoLabel: 'Nueva organización', singular: 'organización',
    campos: [
      { key: 'codigo', label: 'Código', tipo: 'texto', auto: true },
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'tipo', label: 'Tipo de organización', tipo: 'opcion', opciones: [ORG_TERRITORIAL, ORG_FUNCIONAL], requerido: true },
      { key: 'subcategoria', label: 'Subfamilia (funcionales)', tipo: 'opcion', opciones: OPC_SUBCATEGORIAS,
        activoSi: { key: 'tipo', valor: ORG_FUNCIONAL } },
      { key: 'delegacionId', label: 'Delegación', tipo: 'ref', refApi: 'delegaciones', requerido: true },
      { key: 'sector', label: 'Sector', tipo: 'texto', requerido: true },
      { key: 'telefono', label: 'Teléfono de contacto', tipo: 'texto', validar: 'telefono' },
      { key: 'verificacion', label: 'Verificación', tipo: 'verificacion', opciones: OPC_VERIFICACION },
      { key: 'estado', label: 'Estado', tipo: 'estado' },
      { key: 'directiva', label: 'Directiva', tipo: 'directiva', requerido: true }
    ],
    columnas: ['codigo', 'nombre', 'tipo', 'subcategoria', 'delegacionId', 'directiva', 'verificacion', 'estado'],
    columnasModal: 3,  // formulario en tres columnas para que quepa sin barra de desplazamiento
    porDelegacion: true,  // respeta la delegación elegida en la barra superior
    // Filtro rápido junto al buscador: [etiqueta, función que decide si la fila se muestra]
    filtros: [
      ['Todas las organizaciones', () => true],
      ['Juntas de vecinos', (f) => f.tipo === ORG_TERRITORIAL],
      ['Funcionales (todas)', (f) => f.tipo === ORG_FUNCIONAL],
      ...OPC_SUBCATEGORIAS.map((sc) => [`· ${sc}`, (f) => f.subcategoria === sc]),
      ['Pendientes de revisión', (f) => f.verificacion !== 'Verificado'],
      ['Verificadas', (f) => f.verificacion === 'Verificado']
    ]
  }
};

/* ---------- Estado de la página ---------- */
const CFG = ENTIDADES[document.body.dataset.entidad];
const SOLO_LECTURA = document.body.dataset.soloLectura === '1';
const filtroExtra = document.getElementById('filtroExtra');
const esc = SGR.esc;
const BTN = 'var(--red-primary)';
const correoRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

let filas = [];                 // registros de la entidad actual
const referencias = {};         // listas de las entidades referenciadas, por nombre de API
let editandoId = null;
let guardando = false;

const crudTitulo = document.getElementById('crudTitulo');
const crudSubtitulo = document.getElementById('crudSubtitulo');
const nuevoBtn = document.getElementById('nuevoBtn');
const nuevoLabel = document.getElementById('nuevoLabel');
const buscarInput = document.getElementById('buscarInput');
const tablaHead = document.getElementById('tablaHead');
const tablaBody = document.getElementById('tablaBody');
const emptyState = document.getElementById('emptyState');
const contador = document.getElementById('contador');

const modalOverlay = document.getElementById('modalOverlay');
const modalTitle = document.getElementById('modalTitle');
const closeModalBtn = document.getElementById('closeModalBtn');
const cancelModalBtn = document.getElementById('cancelModalBtn');
const saveBtn = document.getElementById('saveBtn');
const crudForm = document.getElementById('crudForm');

const campoDe = (key) => CFG.campos.find((c) => c.key === key);

/* ---------- Alertas (un case por situación) ---------- */
function mostrarAlerta(caso, ctx = {}){
  const etiqueta = ctx.campo ? ctx.campo.label : '';
  switch(caso){
    case 'campo_vacio':
      return Swal.fire({ icon: 'error', title: 'Campo requerido',
        text: `Completa el campo «${etiqueta}».`, confirmButtonColor: BTN });

    case 'sin_seleccion':
      return Swal.fire({ icon: 'error', title: 'Falta una selección',
        text: `Selecciona al menos una opción en «${etiqueta}».`, confirmButtonColor: BTN });

    case 'rut_repetido':
      return Swal.fire({ icon: 'error', title: 'RUT repetido en la directiva',
        text: 'Presidente, tesorero y secretario deben ser personas distintas: sus RUT no se pueden repetir.', confirmButtonColor: BTN });

    case 'rut_invalido':
      return Swal.fire({ icon: 'error', title: 'RUT inválido',
        text: `El RUT de «${etiqueta}» no es válido: revisa los números y el dígito verificador.`, confirmButtonColor: BTN });

    case 'nombre_invalido':
      return Swal.fire({ icon: 'error', title: 'Nombre inválido',
        text: `Escribe un nombre en «${etiqueta}», no solo números o símbolos.`, confirmButtonColor: BTN });

    case 'numero_invalido':
      return Swal.fire({ icon: 'error', title: 'Número inválido',
        text: `«${etiqueta}» debe ser un número entero entre ${ctx.campo.min ?? 1} y ${ctx.campo.max ?? 500}.`, confirmButtonColor: BTN });

    case 'telefono_invalido':
      return Swal.fire({ icon: 'error', title: 'Teléfono inválido',
        text: 'Usa solo números, espacios y los signos + ( ) -.', confirmButtonColor: BTN });

    case 'correo_invalido':
      return Swal.fire({ icon: 'error', title: 'Correo inválido',
        text: 'Ingresa un correo electrónico con formato válido.', confirmButtonColor: BTN });

    case 'duplicado':
      return Swal.fire({ icon: 'error', title: 'Registro duplicado',
        text: `Ya existe un registro con ese valor en «${etiqueta}».`, confirmButtonColor: BTN });

    case 'texto_largo':
      return Swal.fire({ icon: 'error', title: 'Texto demasiado largo',
        text: `«${etiqueta}» admite como máximo ${ctx.maximo} caracteres.`, confirmButtonColor: BTN });

    case 'referencia_invalida':
      return Swal.fire({ icon: 'error', title: 'Valor no válido',
        text: `El valor elegido en «${etiqueta}» ya no existe. Recarga la página e inténtalo de nuevo.`, confirmButtonColor: BTN });

    case 'en_uso': {
      const sugerencia = campoDe('estado')
        ? ' Puedes cambiar su estado a Inactivo en lugar de eliminarlo.' : '';
      return Swal.fire({ icon: 'warning', title: 'No se puede eliminar',
        text: `Está asociado a ${ctx.detalle}.${sugerencia}`, confirmButtonColor: BTN });
    }

    case 'auto_eliminar':
      return Swal.fire({ icon: 'warning', title: 'No puedes eliminarte',
        text: 'No es posible eliminar la cuenta con la que iniciaste sesión.', confirmButtonColor: BTN });

    case 'auto_desactivar':
      return Swal.fire({ icon: 'warning', title: 'No puedes desactivarte',
        text: 'No es posible dejar inactiva la cuenta con la que iniciaste sesión.', confirmButtonColor: BTN });

    case 'auto_rol':
      return Swal.fire({ icon: 'warning', title: 'Cambio no permitido',
        text: 'Con este cambio perderías el permiso «Gestionar usuarios» y no podrías seguir administrando roles y usuarios.', confirmButtonColor: BTN });

    case 'auto_reiniciar':
      return Swal.fire({ icon: 'warning', title: 'Usa Configuraciones',
        text: 'Para cambiar tu propia contraseña usa la opción Configuraciones.', confirmButtonColor: BTN });

    case 'confirmar_eliminar':
      return Swal.fire({ icon: 'warning', title: `¿Eliminar ${CFG.singular}?`,
        text: 'Esta acción no se puede deshacer.', showCancelButton: true,
        confirmButtonText: 'Sí, eliminar', cancelButtonText: 'Cancelar', confirmButtonColor: BTN });

    case 'confirmar_reiniciar':
      return Swal.fire({ icon: 'question', title: '¿Restablecer contraseña?',
        text: `Se generará una contraseña temporal para ${ctx.nombre} y la actual dejará de funcionar.`,
        showCancelButton: true, confirmButtonText: 'Restablecer', cancelButtonText: 'Cancelar', confirmButtonColor: BTN });

    case 'credenciales':
      return Swal.fire({ icon: 'success', title: ctx.titulo,
        html: `<p>Usuario: <b>${esc(ctx.usuario)}</b></p>
               <p>Contraseña temporal: <b style="font-family:'IBM Plex Mono',monospace;user-select:all;">${esc(ctx.password)}</b></p>
               <p style="font-size:13px;color:#666;">Cópiala ahora: no volverá a mostrarse. También se envió al correo del usuario.</p>`,
        confirmButtonText: 'Entendido', confirmButtonColor: BTN });

    case 'guardado':
      return Swal.fire({ icon: 'success', title: ctx.nuevo ? 'Registro creado' : 'Cambios guardados',
        timer: 1200, showConfirmButton: false });

    case 'eliminado':
      return Swal.fire({ icon: 'success', title: 'Registro eliminado', timer: 1200, showConfirmButton: false });

    case 'error_generico':
      return Swal.fire({ icon: 'error', title: 'No se pudo completar la acción',
        text: 'Revisa los datos e inténtalo nuevamente.', confirmButtonColor: BTN });
  }
}

/** Traduce un error de la API al popup que corresponde. */
// Los errores de la directiva llegan como 'directiva.<cargo>.<nombre|rut>'.
function etiquetaCampo(clave){
  const m = /^directiva\.(\w+)\.(nombre|rut|telefono)$/.exec(clave || '');
  if(m){
    const cargo = (CARGOS_DIRECTIVA.find(([k]) => k === m[1]) || [])[1] || m[1];
    const que = { rut: 'RUT', nombre: 'Nombre', telefono: 'Teléfono' }[m[2]];
    return { label: `${que} ${cargo}`, id: `f_dir_${m[1]}_${m[2]}` };
  }
  return null;
}

function manejarError(err){
  const dir = etiquetaCampo(err.campo);
  const campo = dir || campoDe(err.campo) || { label: err.campo || '' };
  if(dir){
    const el = document.getElementById(dir.id);
    if(el){ el.classList.add('field-invalid'); el.focus(); }
  }
  switch(err.error){
    case 'campo_vacio':
    case 'sin_seleccion':
    case 'correo_invalido':
    case 'telefono_invalido':
    case 'rut_repetido':
      return Swal.fire({ icon: 'error', title: 'RUT repetido en la directiva',
        text: 'Presidente, tesorero y secretario deben ser personas distintas: sus RUT no se pueden repetir.', confirmButtonColor: BTN });

    case 'rut_invalido':
      return Swal.fire({ icon: 'error', title: 'RUT inválido',
        text: `El RUT de «${etiqueta}» no es válido: revisa los números y el dígito verificador.`, confirmButtonColor: BTN });

    case 'nombre_invalido':
      return Swal.fire({ icon: 'error', title: 'Nombre inválido',
        text: `Escribe un nombre en «${etiqueta}», no solo números o símbolos.`, confirmButtonColor: BTN });

    case 'numero_invalido':
    case 'duplicado':
    case 'referencia_invalida':
    case 'texto_largo':
      return mostrarAlerta(err.error, { campo, maximo: err.detalle });
    case 'en_uso':
      return mostrarAlerta('en_uso', { detalle: err.detalle });
    case 'auto_eliminar':
    case 'auto_desactivar':
    case 'auto_rol':
    case 'auto_reiniciar':
      return mostrarAlerta(err.error);
  }
  if(SGR.alertaComun(err)){
    if(err.error === 'no_encontrado') cargarDatos();
    return;
  }
  return mostrarAlerta('error_generico');
}

/* ---------- Lectura de valores para mostrar ---------- */
const nombreRef = (api, id) => {
  const r = (referencias[api] || []).find((x) => x.id === id);
  return r ? r.nombre : null;
};

function valorLegible(campo, fila){
  const v = fila[campo.key];
  switch(campo.tipo){
    case 'ref':
      return nombreRef(campo.refApi, v) || '—';
    case 'multiref':
      return (v || []).map((id) => nombreRef(campo.refApi, id)).filter(Boolean);
    case 'multiopcion':
      return v || [];
    case 'directiva':
      return '';
    default:
      return v ?? '';
  }
}

function celdaHtml(campo, fila){
  const val = valorLegible(campo, fila);
  if(campo.tipo === 'estado'){
    return `<span class="badge ${val === 'Activo' ? 'activo' : 'inactivo'}"><span class="dot"></span>${esc(val)}</span>`;
  }
  if(campo.tipo === 'directiva'){
    const p = (fila.directiva || {}).presidente || {};
    return p.nombre ? `${esc(p.nombre)}<span class="due-note">Presidente(a) · ${esc(p.rut || 'sin RUT')}${p.telefono ? ` · ${esc(p.telefono)}` : ''}</span>` : '—';
  }
  if(campo.tipo === 'verificacion'){
    return `<span class="badge ${val === 'Verificado' ? 'aprobada' : 'pendiente'}"><span class="dot"></span>${esc(val)}</span>`;
  }
  if(val === '') return '—';
  if(Array.isArray(val)){
    return val.length
      ? `<div class="chip-list">${val.map((x) => `<span class="chip">${esc(x)}</span>`).join('')}</div>`
      : '—';
  }
  if(campo.key === 'codigo') return `<span class="code-cell">${esc(val)}</span>`;
  return esc(val);
}

function textoFila(fila){
  const extra = fila.directiva ? Object.values(fila.directiva).map((p) => `${p.nombre} ${p.rut} ${p.telefono || ''}`).join(' ') : '';
  return extra + ' ' + CFG.columnas.map((k) => {
    const v = valorLegible(campoDe(k), fila);
    return Array.isArray(v) ? v.join(' ') : v;
  }).join(' ');
}

/* ---------- Tabla ---------- */
function renderTabla(){
  const term = buscarInput.value.trim().toLowerCase();
  const filtro = CFG.filtros && filtroExtra ? CFG.filtros[Number(filtroExtra.value) || 0][1] : () => true;
  const activa = CFG.porDelegacion ? SGR.delegacionActiva() : null;
  const visibles = filas.filter((f) => (!activa || f.delegacionId === activa) &&
    filtro(f) && (!term || textoFila(f).toLowerCase().includes(term)));
  const extras = (CFG.accionesExtra || []);

  tablaBody.innerHTML = visibles.map((f) => `
    <tr>
      ${CFG.columnas.map((k) => `<td>${celdaHtml(campoDe(k), f)}</td>`).join('')}
      ${SOLO_LECTURA ? '' : `<td class="row-actions">
        <button class="btn-table" data-accion="editar" data-id="${f.id}">Editar</button>
        ${extras.map((x) => `<button class="btn-table" data-accion="${x.accion}" data-id="${f.id}" title="${esc(x.ayuda || x.label)}">${esc(x.label)}</button>`).join('')}
        <button class="btn-table danger" data-accion="eliminar" data-id="${f.id}">Eliminar</button>
      </td>`}
    </tr>`).join('');

  emptyState.style.display = visibles.length ? 'none' : 'block';
  contador.textContent = `${visibles.length} registro${visibles.length === 1 ? '' : 's'}`;
}

tablaBody.addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-accion]');
  if(!btn) return;
  const id = Number(btn.dataset.id);
  if(btn.dataset.accion === 'editar') abrirModal(id);
  if(btn.dataset.accion === 'eliminar') eliminar(id);
  if(btn.dataset.accion === 'reiniciar') reiniciarPassword(id);
});

buscarInput.addEventListener('input', renderTabla);

/* ---------- Carga de datos desde la API ---------- */
async function cargarDatos(){
  const apis = new Set(CFG.campos.filter((c) => c.refApi).map((c) => c.refApi));
  try {
    const [propios, ...refs] = await Promise.all([
      SGR.listar(CFG.api),
      ...[...apis].map((a) => SGR.listar(a))
    ]);
    filas = propios;
    [...apis].forEach((a, i) => { referencias[a] = refs[i]; });
  } catch(err) {
    if(!SGR.alertaComun(err)) mostrarAlerta('error_generico');
    return;
  }
  renderTabla();
}

/* ---------- Formulario ---------- */
function opcionesRef(campo, seleccionado){
  return (referencias[campo.refApi] || []).map((r) =>
    `<option value="${r.id}" ${r.id === seleccionado ? 'selected' : ''}>${esc(r.nombre)}${r.estado === 'Inactivo' ? ' (inactivo)' : ''}</option>`
  ).join('');
}

/* Atributos para la validación en vivo (validacion.js). */
function attrsValidacion(c){
  const regla = c.validar || (c.tipo === 'correo' ? 'correo' : c.tipo === 'numero' ? 'entero' : '');
  return `${regla ? ` data-validar="${regla}"` : ''}${c.requerido && !c.auto ? ' data-requerido' : ''}`;
}

function campoHtml(c, valor, esNuevo){
  const id = `f_${c.key}`;
  const va = attrsValidacion(c);
  const req = c.requerido ? ' <span class="required">*</span>' : '';
  let control = '';

  switch(c.tipo){
    case 'textarea':
      control = `<textarea id="${id}" rows="2"${va}>${esc(valor || '')}</textarea>`;
      break;
    case 'estado':
      control = `<select id="${id}">
        <option ${valor !== 'Inactivo' ? 'selected' : ''}>Activo</option>
        <option ${valor === 'Inactivo' ? 'selected' : ''}>Inactivo</option>
      </select>`;
      break;
    case 'opcion':
      control = `<select id="${id}"${va}><option value="">Selecciona…</option>${
        c.opciones.map((o) => `<option ${o === valor ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`;
      break;
    case 'verificacion':
      control = `<select id="${id}">${
        c.opciones.map((o) => `<option ${o === (valor || c.opciones[0]) ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`;
      break;
    case 'ref':
      control = `<select id="${id}"${va}><option value="">Selecciona…</option>${opcionesRef(c, valor)}</select>`;
      break;
    case 'multiref':
      control = `<div class="checkbox-grid" id="${id}">${(referencias[c.refApi] || []).map((r) => `
        <label class="check-item"><input type="checkbox" name="${c.key}" value="${r.id}" ${(valor || []).includes(r.id) ? 'checked' : ''}>
        ${esc(r.nombre)}${r.estado === 'Inactivo' ? ' (inactiva)' : ''}</label>`).join('')}</div>`;
      break;
    case 'multiopcion':
      control = `<div class="checkbox-grid" id="${id}">${c.opciones.map((o) => `
        <label class="check-item"><input type="checkbox" name="${c.key}" value="${esc(o)}" ${(valor || []).includes(o) ? 'checked' : ''}>
        ${esc(o)}</label>`).join('')}</div>`;
      break;
    case 'correo':
      control = `<input type="email" id="${id}" value="${esc(valor || '')}" autocomplete="off"${va}>`;
      break;
    case 'directiva': {
      const d = valor || {};
      control = `<div class="directiva-grid" id="${id}">
        <span class="directiva-head">Cargo</span><span class="directiva-head">Nombre *</span><span class="directiva-head">RUT *</span><span class="directiva-head">Teléfono *</span>
        ${CARGOS_DIRECTIVA.map(([cargo, etiqueta]) => `
          <span class="directiva-cargo">${etiqueta}</span>
          <div class="field"><input type="text" id="f_dir_${cargo}_nombre" aria-label="Nombre ${etiqueta}" maxlength="150"
            value="${esc((d[cargo] || {}).nombre || '')}" data-validar="nombre" data-requerido autocomplete="off"></div>
          <div class="field"><input type="text" id="f_dir_${cargo}_rut" aria-label="RUT ${etiqueta}" maxlength="12"
            placeholder="12.345.678-5" value="${esc((d[cargo] || {}).rut || '')}" data-validar="rut" data-requerido autocomplete="off"></div>
          <div class="field"><input type="tel" id="f_dir_${cargo}_telefono" aria-label="Teléfono ${etiqueta}" maxlength="30"
            placeholder="+56 9 1234 5678" value="${esc((d[cargo] || {}).telefono || '')}" data-validar="telefono" data-requerido autocomplete="off"></div>`).join('')}
      </div>`;
      break;
    }
    case 'numero':
      control = `<input type="number" id="${id}" value="${esc(valor ?? '')}" min="${c.min ?? ''}" max="${c.max ?? ''}" step="1"${va}>`;
      break;
    default:
      // El código se genera en el servidor al crear (DEL-001, ITM-001, ...).
      control = (c.auto && esNuevo)
        ? `<input type="text" id="${id}" value="" placeholder="Se genera automáticamente" disabled>`
        : `<input type="text" id="${id}" value="${esc(valor || '')}" autocomplete="off"${va}>`;
  }
  // Los campos largos (descripciones y listas de casillas) ocupan las dos columnas del modal.
  const ancho = ['textarea', 'multiref', 'multiopcion', 'directiva'].includes(c.tipo) ? ' ancho-completo' : '';
  if(c.tipo === 'directiva'){
    return `<fieldset class="field directiva${ancho}"><legend>${esc(c.label)}${req}
      <span class="field-hint" style="display:inline;margin-left:6px;">Nombre, RUT y teléfono de cada cargo; los tres RUT deben ser distintos</span></legend>${control}</fieldset>`;
  }
  return `<div class="field${ancho}"><label for="${id}">${esc(c.label)}${req}</label>${control}</div>`;
}

function abrirModal(id){
  editandoId = id ?? null;
  const fila = editandoId ? filas.find((r) => r.id === editandoId) : null;
  modalTitle.textContent = fila ? `Editar ${CFG.singular}` : CFG.nuevoLabel;

  crudForm.classList.toggle('crud-grid-3', CFG.columnasModal === 3);
  modalOverlay.querySelector('.modal').classList.toggle('modal-xl', CFG.columnasModal === 3);
  crudForm.innerHTML = CFG.campos.map((c) => campoHtml(c, fila ? fila[c.key] : undefined, !fila)).join('');
  actualizarDependientes();

  modalOverlay.classList.add('open');
  const primero = crudForm.querySelector('input[type="text"]:not(:disabled), input[type="email"], textarea, select');
  if(primero) primero.focus();
}

/* Campos que solo aplican según otro campo (p. ej. la subfamilia, solo para organizaciones funcionales). */
function actualizarDependientes(){
  CFG.campos.filter((c) => c.activoSi).forEach((c) => {
    const control = document.getElementById(`f_${c.key}`);
    const origen = document.getElementById(`f_${c.activoSi.key}`);
    const activo = origen && origen.value === c.activoSi.valor;
    control.disabled = !activo;
    if(!activo) control.value = '';
    const label = crudForm.querySelector(`label[for="f_${c.key}"]`);
    if(label) label.innerHTML = esc(c.label) + (activo ? ' <span class="required">*</span>' : '');
  });
}
/* Directiva: avisa al instante si un RUT se repite entre presidente, tesorero y secretario.
   Corre después de la validación general (validacion.js), por eso el setTimeout. */
function revisarRutsRepetidos(){
  const campos = CARGOS_DIRECTIVA.map(([cargo, etiqueta]) => [document.getElementById(`f_dir_${cargo}_rut`), etiqueta]);
  if(!campos[0][0]) return;
  campos.forEach(([el, etiqueta], i) => {
    const valor = SGRValidar.limpiarRut(el.value);
    const otro = campos.find(([o], j) => j < i && valor && SGRValidar.limpiarRut(o.value) === valor);
    const msg = document.getElementById(`${el.id}-msg`);
    if(otro && SGRValidar.esRutValido(el.value)){
      el.classList.remove('field-valid');
      el.classList.add('field-invalid');
      if(msg){ msg.textContent = `Repetido: es el RUT del ${otro[1].toLowerCase()}`; msg.className = 'field-msg error'; }
    }
  });
}
document.addEventListener('input', (e) => {
  if(e.target.id && e.target.id.startsWith('f_dir_')) setTimeout(revisarRutsRepetidos);
});
document.addEventListener('focusout', (e) => {
  if(e.target.id && e.target.id.startsWith('f_dir_')) setTimeout(revisarRutsRepetidos);
});

crudForm.addEventListener('change', (e) => {
  if(CFG.campos.some((c) => c.activoSi && `f_${c.activoSi.key}` === e.target.id)) actualizarDependientes();
});

function cerrarModal(){
  modalOverlay.classList.remove('open');
  crudForm.innerHTML = '';
  editandoId = null;
}

function leerFormulario(){
  const datos = {};
  CFG.campos.forEach((c) => {
    switch(c.tipo){
      case 'multiref':
        datos[c.key] = [...crudForm.querySelectorAll(`input[name="${c.key}"]:checked`)].map((i) => Number(i.value));
        break;
      case 'multiopcion':
        datos[c.key] = [...crudForm.querySelectorAll(`input[name="${c.key}"]:checked`)].map((i) => i.value);
        break;
      case 'directiva':
        datos[c.key] = Object.fromEntries(CARGOS_DIRECTIVA.map(([cargo]) => [cargo, {
          nombre: document.getElementById(`f_dir_${cargo}_nombre`).value.trim(),
          rut: document.getElementById(`f_dir_${cargo}_rut`).value.trim(),
          telefono: document.getElementById(`f_dir_${cargo}_telefono`).value.trim()
        }]));
        break;
      case 'ref': {
        const v = document.getElementById(`f_${c.key}`).value;
        datos[c.key] = v ? Number(v) : null;
        break;
      }
      default:
        datos[c.key] = document.getElementById(`f_${c.key}`).value.trim();
    }
  });
  return datos;
}

/* Validación rápida en el navegador. Devuelve { caso, campo } o null.
   El servidor vuelve a validar todo (unicidad, referencias, permisos). */
function validar(datos){
  for(const c of CFG.campos){
    const v = datos[c.key];
    if(c.tipo === 'directiva'){
      // RUT repetidos dentro de la misma directiva
      const ruts = CARGOS_DIRECTIVA.map(([cargo]) => SGRValidar.limpiarRut(v[cargo].rut)).filter(Boolean);
      if(new Set(ruts).size !== ruts.length) return { caso: 'rut_repetido', campo: c };
      continue;
    }
    const esLista = Array.isArray(v);
    const vacio = esLista ? v.length === 0 : (v === null || v === '');

    const requerido = c.requerido || (c.activoSi && datos[c.activoSi.key] === c.activoSi.valor);
    if(requerido && vacio) return { caso: esLista ? 'sin_seleccion' : 'campo_vacio', campo: c };
    if(c.tipo === 'correo' && v && !correoRe.test(v)) return { caso: 'correo_invalido', campo: c };
    if(c.tipo === 'numero' && v !== '' && (!/^\d+$/.test(v) || Number(v) < (c.min ?? 0) || Number(v) > (c.max ?? Infinity))){
      return { caso: 'numero_invalido', campo: c };
    }
  }
  return null;
}

saveBtn.addEventListener('click', async () => {
  if(guardando) return;
  const campoMalo = SGRValidar.validarTodo(crudForm);
  if(campoMalo){
    const dirMatch = /^f_dir_([a-z]+)_(nombre|rut|telefono)$/.exec(campoMalo.id);
    const campo = (dirMatch && etiquetaCampo(`directiva.${dirMatch[1]}.${dirMatch[2]}`))
      || campoDe(campoMalo.id.replace(/^f_/, '')) || { label: '' };
    Swal.fire({ icon: 'error', title: `Revisa «${campo.label}»`,
      text: (document.getElementById(`${campoMalo.id}-msg`) || {}).textContent || 'El dato no es válido.', confirmButtonColor: BTN })
      .then(() => campoMalo.focus());
    return;
  }
  const datos = leerFormulario();
  const problema = validar(datos);
  if(problema){
    mostrarAlerta(problema.caso, { campo: problema.campo });
    return;
  }

  const esNuevo = editandoId === null;
  guardando = true;
  saveBtn.disabled = true;
  try {
    const guardado = esNuevo
      ? await SGR.crear(CFG.api, datos)
      : await SGR.actualizar(CFG.api, editandoId, datos);
    cerrarModal();
    await cargarDatos();
    if(esNuevo && guardado.passwordTemporal){
      mostrarAlerta('credenciales', { titulo: 'Usuario creado', usuario: guardado.usuario, password: guardado.passwordTemporal });
    } else {
      mostrarAlerta('guardado', { nuevo: esNuevo });
    }
  } catch(err) {
    manejarError(err);
  } finally {
    guardando = false;
    saveBtn.disabled = false;
  }
});

/* ---------- Eliminar ---------- */
async function eliminar(id){
  const fila = filas.find((r) => r.id === id);
  if(!fila) return;

  const res = await mostrarAlerta('confirmar_eliminar');
  if(!res.isConfirmed) return;
  try {
    await SGR.eliminar(CFG.api, id);
    await cargarDatos();
    mostrarAlerta('eliminado');
  } catch(err) {
    manejarError(err);
  }
}

/* ---------- Restablecer contraseña (solo usuarios) ---------- */
async function reiniciarPassword(id){
  const fila = filas.find((r) => r.id === id);
  if(!fila) return;

  const res = await mostrarAlerta('confirmar_reiniciar', { nombre: fila.nombre });
  if(!res.isConfirmed) return;
  try {
    const r = await SGR.post(`usuarios/${id}/reiniciar-password/`);
    mostrarAlerta('credenciales', { titulo: 'Contraseña restablecida', usuario: r.usuario, password: r.passwordTemporal });
  } catch(err) {
    manejarError(err);
  }
}

/* ---------- Eventos generales ---------- */
if(CFG.filtros && filtroExtra){
  filtroExtra.innerHTML = CFG.filtros.map(([etiqueta], i) => `<option value="${i}">${esc(etiqueta)}</option>`).join('');
  filtroExtra.addEventListener('change', renderTabla);
}

nuevoBtn.addEventListener('click', () => abrirModal(null));
closeModalBtn.addEventListener('click', cerrarModal);
cancelModalBtn.addEventListener('click', cerrarModal);
modalOverlay.addEventListener('click', (e) => { if(e.target === modalOverlay) cerrarModal(); });
document.addEventListener('keydown', (e) => { if(e.key === 'Escape' && modalOverlay.classList.contains('open')) cerrarModal(); });

/* ---------- Init ---------- */
document.title = `SGR Municipal — ${CFG.titulo}`;
crudTitulo.textContent = CFG.titulo;
crudSubtitulo.textContent = CFG.subtitulo;
nuevoLabel.textContent = CFG.nuevoLabel;
tablaHead.innerHTML = '<tr>' +
  CFG.columnas.map((k) => `<th>${esc(campoDe(k).label)}</th>`).join('') +
  (SOLO_LECTURA ? '' : `<th style="width:${(CFG.accionesExtra || []).length ? 250 : 170}px;">Acciones</th>`) + '</tr>';
cargarDatos();
