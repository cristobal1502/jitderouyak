/* ============================================================
   Casos sociales — conectado a la API (/api/casos/).
   Cada caso se crea junto con su primera gestión en una sola
   transacción del servidor; las gestiones 2 y 3 se agregan después.
   ============================================================ */
const esc = SGR.esc;
const BTN = 'var(--red-primary)';
const PUEDE_REGISTRAR = document.body.dataset.puedeRegistrar === '1';

let casos = [];
let opciones = { tipos: [], delegaciones: [] };
const abiertos = new Set();      // ids de casos desplegados
let modalMode = 'nuevo-caso';    // 'nuevo-caso' | 'nueva-gestion'
let casoActivo = null;
let enviando = false;

const casosContainer = document.getElementById('casosContainer');
const emptyState = document.getElementById('emptyState');
const buscarUsuario = document.getElementById('buscarUsuario');
const buscarBtn = document.getElementById('buscarBtn');

const modalOverlay = document.getElementById('modalOverlay');
const modalTitle = document.getElementById('modalTitle');
const openModalBtn = document.getElementById('openModalBtn');   // null si el rol no puede registrar
const closeModalBtn = document.getElementById('closeModalBtn');
const cancelModalBtn = document.getElementById('cancelModalBtn');
const saveCasoBtn = document.getElementById('saveCasoBtn');
const casoForm = document.getElementById('casoForm');
const datosUsuarioFields = document.getElementById('datosUsuarioFields');

const fNombre = document.getElementById('uNombre');
const fRut = document.getElementById('uRut');
const fTelefono = document.getElementById('uTelefono');
const fSector = document.getElementById('uSector');
const fDelegacion = document.getElementById('uDelegacion');
const fTipo = document.getElementById('gTipo');
const fDetalle = document.getElementById('gDetalle');
const fFecha = document.getElementById('gFecha');

const hoy = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD en hora local

/* ---------- Alertas (un case por situación) ---------- */
function marcar(el){ el.classList.add('field-invalid'); el.focus(); }

function mostrarAlerta(caso, ctx = {}){
  switch(caso){
    case 'nombre_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el nombre', text: 'Ingresa el nombre completo del usuario.', confirmButtonColor: BTN });
      marcar(fNombre); break;
    case 'nombre_corto':
      Swal.fire({ icon: 'error', title: 'Nombre incompleto', text: 'Ingresa el nombre y apellido de la persona (mínimo 5 caracteres).', confirmButtonColor: BTN });
      marcar(fNombre); break;
    case 'rut_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el RUT', text: 'Ingresa el RUT del usuario.', confirmButtonColor: BTN });
      marcar(fRut); break;
    case 'rut_invalido':
      Swal.fire({ icon: 'error', title: 'RUT no válido', text: 'Revisa el RUT: el dígito verificador no corresponde (ej: 12.345.678-5).', confirmButtonColor: BTN });
      marcar(fRut); break;
    case 'rut_duplicado':
      Swal.fire({ icon: 'warning', title: 'La persona ya tiene un caso',
        text: ctx.codigo
          ? `Ya existe el caso ${ctx.codigo} con ese RUT. Búscalo en la lista y registra ahí la siguiente gestión.`
          : 'Ya existe un caso registrado con ese RUT.',
        confirmButtonColor: BTN });
      marcar(fRut); break;
    case 'sector_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el sector', text: 'Ingresa el sector del usuario.', confirmButtonColor: BTN });
      marcar(fSector); break;
    case 'telefono_invalido':
      Swal.fire({ icon: 'error', title: 'Teléfono no válido', text: 'Usa solo números, espacios, +, paréntesis o guiones.', confirmButtonColor: BTN });
      marcar(fTelefono); break;
    case 'delegacion_vacia':
      Swal.fire({ icon: 'error', title: 'Falta la delegación', text: 'Selecciona la delegación que abre el caso.', confirmButtonColor: BTN });
      marcar(fDelegacion); break;
    case 'tipo_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el tipo de gestión', text: 'Selecciona el tipo de gestión.', confirmButtonColor: BTN });
      marcar(fTipo); break;
    case 'detalle_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el detalle', text: 'Describe la gestión realizada (mínimo 10 caracteres).', confirmButtonColor: BTN });
      marcar(fDetalle); break;
    case 'fecha_vacia':
      Swal.fire({ icon: 'error', title: 'Falta la fecha', text: 'Selecciona la fecha de la gestión.', confirmButtonColor: BTN });
      marcar(fFecha); break;
    case 'fecha_futura':
      Swal.fire({ icon: 'warning', title: 'Fecha no válida', text: 'La fecha de la gestión no puede ser posterior a hoy.', confirmButtonColor: BTN });
      marcar(fFecha); break;
    case 'fecha_anterior':
      Swal.fire({ icon: 'warning', title: 'Fecha anterior a la gestión previa',
        text: `La gestión no puede tener una fecha anterior a la gestión anterior (${SGR.formatearFecha(ctx.minima)}).`, confirmButtonColor: BTN });
      marcar(fFecha); break;
    case 'gestiones_completas':
      Swal.fire({ icon: 'info', title: 'Caso completo',
        text: 'Este caso ya tiene sus 3 gestiones registradas (máximo permitido).', confirmButtonColor: BTN });
      break;
    case 'dato_desactualizado':
      Swal.fire({ icon: 'warning', title: 'Datos desactualizados',
        text: 'Algo cambió mientras completabas el formulario. Se recargaron los datos; revisa y vuelve a intentar.', confirmButtonColor: BTN });
      break;
    case 'guardado':
      Swal.fire({ icon: 'success', title: ctx.nuevo ? 'Caso registrado' : 'Gestión guardada',
        text: ctx.nuevo ? `Se generó el caso ${ctx.codigo} con su primera gestión.` : `Gestión registrada en el caso ${ctx.codigo}.`,
        timer: 1600, showConfirmButton: false });
      break;
    default:
      Swal.fire({ icon: 'error', title: 'No se pudo guardar', text: 'Revisa los datos e inténtalo nuevamente.', confirmButtonColor: BTN });
  }
}

const CASO_CAMPO_VACIO = {
  nombre: 'nombre_vacio', rut: 'rut_vacio', sector: 'sector_vacio', delegacionId: 'delegacion_vacia',
  tipoId: 'tipo_vacio', detalle: 'detalle_vacio', fecha: 'fecha_vacia'
};

/** Traduce un error de la API al popup que corresponde. */
function manejarError(err){
  switch(err.error){
    case 'campo_vacio':          return mostrarAlerta(CASO_CAMPO_VACIO[err.campo] || 'error');
    case 'nombre_corto':         return mostrarAlerta('nombre_corto');
    case 'rut_invalido':         return mostrarAlerta('rut_invalido');
    case 'duplicado':
      if(err.campo === 'rut')    return mostrarAlerta('rut_duplicado', { codigo: err.detalle });
      break;
    case 'telefono_invalido':    return mostrarAlerta('telefono_invalido');
    case 'detalle_corto':        return mostrarAlerta('detalle_vacio');
    case 'fecha_futura':         return mostrarAlerta('fecha_futura');
    case 'fecha_invalida':       return mostrarAlerta('fecha_vacia');
    case 'fecha_anterior':       return mostrarAlerta('fecha_anterior', { minima: err.detalle });
    case 'gestiones_completas':
      cargarCasos();
      return mostrarAlerta('gestiones_completas');
    case 'conflicto':
    case 'referencia_invalida':
      recargarTodo();
      return mostrarAlerta('dato_desactualizado');
  }
  if(SGR.alertaComun(err)) return;
  mostrarAlerta('error');
}

/* ---------- Render ---------- */
function filtrar(){
  const term = buscarUsuario.value.trim().toLowerCase();
  if(!term) return casos;
  const termRut = term.replace(/[.\-\s]/g, '');
  return casos.filter((c) =>
    c.nombre.toLowerCase().includes(term) ||
    c.rut.replace(/[.\-]/g, '').toLowerCase().includes(termRut) ||
    c.codigo.toLowerCase().includes(term));
}

function renderCasos(){
  const lista = filtrar();
  emptyState.textContent = casos.length === 0
    ? 'Aún no hay casos sociales registrados.'
    : 'No se encontraron casos para esa búsqueda.';
  emptyState.style.display = lista.length === 0 ? 'block' : 'none';
  casosContainer.innerHTML = lista.map(renderCasoCard).join('');

  casosContainer.querySelectorAll('.caso-header, .caso-collapsed-hint').forEach((el) => {
    el.addEventListener('click', () => toggleCaso(Number(el.dataset.id)));
  });
  casosContainer.querySelectorAll('.btn-register-gestion').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      abrirModalNuevaGestion(Number(btn.dataset.id));
    });
  });
}

function cabecera(c){
  return `
      <div class="caso-header" data-id="${c.id}">
        <span class="caso-id">CASO #${esc(c.codigo)}:</span>
        <span class="caso-nombre">${esc(c.nombre)}</span>
        <span class="caso-meta-item">RUT: <b>${esc(c.rut)}</b></span>
        <span class="caso-meta-item">Sector: <b>${esc(c.sector)}</b></span>
        <span class="caso-meta-item">Tel: <b>${esc(c.telefono || '—')}</b></span>
        <span class="caso-meta-item">Delegación: <b>${esc(c.delegacionNombre)}</b></span>
        <span class="caso-toggle-icon">${chevronIcon()}</span>
      </div>`;
}

function renderCasoCard(c){
  const n = c.gestiones.length;
  if(!abiertos.has(c.id)){
    return `
      <div class="caso-card" data-id="${c.id}">
        ${cabecera(c)}
        <div class="caso-collapsed-hint" data-id="${c.id}">
          Desplegar historial de ${n} gestion${n === 1 ? '' : 'es'} registrada${n === 1 ? '' : 's'}
        </div>
      </div>`;
  }
  const pasos = c.gestiones.map((g) => renderGestion(g));
  if(n < c.maxGestiones) pasos.push(renderPendiente(c, n + 1));
  return `
    <div class="caso-card expanded" data-id="${c.id}">
      ${cabecera(c)}
      <div class="caso-body">
        <div class="caso-body-label">Secuencia de atenciones (RF-015: máximo ${c.maxGestiones} gestiones vinculadas)</div>
        <div class="gestion-timeline">${pasos.join('')}</div>
      </div>
    </div>`;
}

function renderGestion(g){
  return `
    <div class="gestion-step">
      <div class="step-marker-col">
        <div class="step-marker">${g.numero}</div>
        <div class="step-connector"></div>
      </div>
      <div class="step-content">
        <div class="step-title-row">
          <span class="step-title">${esc(g.tipoNombre)}</span>
          <span class="step-date">Gestión ${g.numero} — ${SGR.formatearFecha(g.fecha)}</span>
        </div>
        <div class="step-detail">${esc(g.detalle)}</div>
        <div class="step-atendido">Atendido por: ${esc(g.atendidoPor)}</div>
      </div>
    </div>`;
}

function renderPendiente(c, numero){
  return `
    <div class="gestion-step">
      <div class="step-marker-col">
        <div class="step-marker pending">${numero}</div>
      </div>
      <div class="step-content">
        <div class="step-title-row">
          <span class="step-title">Siguiente gestión</span>
          <span class="step-date pendiente">Gestión ${numero} — Pendiente</span>
        </div>
        <div class="step-detail">Aún no se registra esta gestión.</div>
        ${PUEDE_REGISTRAR ? `<button class="btn-register-gestion" data-id="${c.id}">+ Registrar gestión ${numero}</button>` : ''}
      </div>
    </div>`;
}

function chevronIcon(){
  return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>`;
}

function toggleCaso(id){
  if(abiertos.has(id)) abiertos.delete(id); else abiertos.add(id);
  renderCasos();
}

/* ---------- Búsqueda ---------- */
buscarBtn.addEventListener('click', renderCasos);
buscarUsuario.addEventListener('keydown', (e) => { if(e.key === 'Enter') renderCasos(); });
buscarUsuario.addEventListener('input', () => { if(buscarUsuario.value.trim() === '') renderCasos(); });

/* ---------- Modal ---------- */
function opcionesHtml(lista, placeholder){
  return `<option value="">${placeholder}</option>` +
    lista.map((r) => `<option value="${r.id}">${esc(r.nombre)}</option>`).join('');
}

function cargarSelects(){
  fTipo.innerHTML = opcionesHtml(opciones.tipos, 'Selecciona un tipo…');
  fDelegacion.innerHTML = opcionesHtml(opciones.delegaciones, 'Selecciona una delegación…');
  if(opciones.delegaciones.length === 1) fDelegacion.value = String(opciones.delegaciones[0].id);
}

function limpiarForm(){
  casoForm.reset();
  casoForm.querySelectorAll('.field-invalid').forEach((el) => el.classList.remove('field-invalid'));
  cargarSelects();
  fFecha.value = hoy();
  fFecha.max = hoy();
  fFecha.min = '';
}

function abrirModalNuevoCaso(){
  modalMode = 'nuevo-caso';
  casoActivo = null;
  modalTitle.textContent = 'Nueva atención social';
  datosUsuarioFields.style.display = 'block';
  limpiarForm();
  modalOverlay.classList.add('open');
}

function abrirModalNuevaGestion(id){
  const c = casos.find((x) => x.id === id);
  if(!c) return;
  modalMode = 'nueva-gestion';
  casoActivo = c;
  modalTitle.textContent = `Registrar gestión ${c.gestiones.length + 1} — CASO #${c.codigo}`;
  datosUsuarioFields.style.display = 'none';
  limpiarForm();
  const ultima = c.gestiones[c.gestiones.length - 1];
  if(ultima) fFecha.min = ultima.fecha;   // no puede ser anterior a la gestión previa
  modalOverlay.classList.add('open');
}

function cerrarModal(){
  modalOverlay.classList.remove('open');
  casoActivo = null;
}

if(openModalBtn) openModalBtn.addEventListener('click', abrirModalNuevoCaso);
closeModalBtn.addEventListener('click', cerrarModal);
cancelModalBtn.addEventListener('click', cerrarModal);
modalOverlay.addEventListener('click', (e) => { if(e.target === modalOverlay) cerrarModal(); });

/* ---------- Guardar ---------- */
saveCasoBtn.addEventListener('click', async () => {
  if(enviando) return;
  casoForm.querySelectorAll('.field-invalid').forEach((el) => el.classList.remove('field-invalid'));

  const detalle = fDetalle.value.trim();
  const nuevo = modalMode === 'nuevo-caso';

  // Validación secuencial: se detiene en el primer caso que falle.
  if(nuevo){
    const nombre = fNombre.value.trim();
    if(nombre === ''){ mostrarAlerta('nombre_vacio'); return; }
    if(nombre.length < 5){ mostrarAlerta('nombre_corto'); return; }
    if(fRut.value.trim() === ''){ mostrarAlerta('rut_vacio'); return; }
    if(fSector.value.trim() === ''){ mostrarAlerta('sector_vacio'); return; }
    if(!/^[0-9+()\s-]{0,30}$/.test(fTelefono.value.trim())){ mostrarAlerta('telefono_invalido'); return; }
    if(!fDelegacion.value){ mostrarAlerta('delegacion_vacia'); return; }
  }
  if(!fTipo.value){ mostrarAlerta('tipo_vacio'); return; }
  if(detalle.length < 10){ mostrarAlerta('detalle_vacio'); return; }
  if(!fFecha.value){ mostrarAlerta('fecha_vacia'); return; }
  if(fFecha.value > hoy()){ mostrarAlerta('fecha_futura'); return; }

  const gestion = { tipoId: Number(fTipo.value), detalle, fecha: fFecha.value };
  enviando = true;
  try {
    let caso;
    if(nuevo){
      caso = await SGR.post('casos/', {
        nombre: fNombre.value.trim(), rut: fRut.value.trim(), telefono: fTelefono.value.trim(),
        sector: fSector.value.trim(), delegacionId: Number(fDelegacion.value), ...gestion
      });
      casos.unshift(caso);
    } else {
      caso = await SGR.post(`casos/${casoActivo.id}/gestiones/`, gestion);
      casos = casos.map((c) => (c.id === caso.id ? caso : c));
    }
    abiertos.add(caso.id);
    cerrarModal();
    renderCasos();
    mostrarAlerta('guardado', { nuevo, codigo: caso.codigo });
  } catch(err) {
    manejarError(err);
  } finally {
    enviando = false;
  }
});

/* ---------- Carga desde la API ---------- */
async function cargarCasos(){
  try {
    casos = await SGR.get('casos/');
    renderCasos();
  } catch(err) {
    if(!SGR.alertaComun(err)) mostrarAlerta('error');
  }
}

async function cargarOpciones(){
  if(!PUEDE_REGISTRAR) return;
  try {
    opciones = await SGR.get('opciones-atencion/');
    cargarSelects();
  } catch(err) {
    if(!SGR.alertaComun(err)) mostrarAlerta('error');
  }
}

async function recargarTodo(){
  await Promise.all([cargarOpciones(), cargarCasos()]);
}

recargarTodo();
