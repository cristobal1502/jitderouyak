const esc = SGR.esc;
const BTN = 'var(--red-primary)';

const form = document.getElementById('atencionForm'); // null si el rol no tiene permiso para registrar
const fSolicitante = document.getElementById('aSolicitante');
const fTelefono = document.getElementById('aTelefono');
const fEsDelegado = document.getElementById('aEsDelegado');
const fechaAyuda = document.getElementById('fechaAyuda');
const fFecha = document.getElementById('aFecha');
const fTipo = document.getElementById('aTipo');
const fItem = document.getElementById('aItem');
const estadoElegido = () => (document.querySelector('input[name="aEstado"]:checked') || {}).value || 'Ejecutada';
const fSub = document.getElementById('aSub');
const fDelegacion = document.getElementById('aDelegacion');
const fResponsable = document.getElementById('aResponsable');
const fDescripcion = document.getElementById('aDescripcion');
const limpiarBtn = document.getElementById('limpiarBtn');
const tablaBody = document.getElementById('tablaBody');
const emptyState = document.getElementById('emptyState');
const contador = document.getElementById('contador');

const hoy = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD en hora local

/* Catálogos y atenciones vienen de la base de datos (API) */
let opcionesApi = { tipos: [], subatenciones: [], items: [], delegaciones: [], responsables: [], fechaMinima: '', maxPorDia: 7 };
const telefonoValido = (t) => /^[0-9+()\s-]+$/.test(t) && t.replace(/\D/g, '').length >= 8 && t.replace(/\D/g, '').length <= 15;
let atenciones = [];

/* ---------- Selects que dependen del catálogo de Administración ---------- */
function opciones(lista, placeholder){
  return `<option value="">${placeholder}</option>` +
    lista.map((r) => `<option value="${r.id}">${esc(r.nombre)}</option>`).join('');
}

function cargarTipos(){
  fTipo.innerHTML = opciones(opcionesApi.tipos, 'Selecciona un tipo…');
  fItem.innerHTML = opciones(opcionesApi.items, 'Selecciona el ítem…');
}

function cargarSubatenciones(){
  const tipoId = Number(fTipo.value);
  if(!tipoId){
    fSub.innerHTML = '<option value="">Primero selecciona un tipo…</option>';
    fSub.disabled = true;
    return;
  }
  const subs = opcionesApi.subatenciones.filter((s) => s.tipoId === tipoId);
  fSub.innerHTML = opciones(subs, subs.length ? 'Selecciona una sub atención…' : 'Este tipo no tiene sub atenciones activas');
  fSub.disabled = subs.length === 0;
}

function cargarDelegaciones(){
  fDelegacion.innerHTML = opciones(opcionesApi.delegaciones, 'Selecciona una delegación…');
}

function cargarResponsables(){
  const delId = Number(fDelegacion.value);
  if(!delId){
    fResponsable.innerHTML = '<option value="">Primero selecciona una delegación…</option>';
    fResponsable.disabled = true;
    return;
  }
  const usuarios = opcionesApi.responsables.filter((u) => u.delegaciones.includes(delId));
  fResponsable.innerHTML = opciones(usuarios, usuarios.length ? 'Selecciona un responsable…' : 'Sin usuarios activos en esta delegación');
  fResponsable.disabled = usuarios.length === 0;
}

if(form){
  fTipo.addEventListener('change', cargarSubatenciones);
  fDelegacion.addEventListener('change', cargarResponsables);
}

/* ---------- Alertas (un case por situación) ---------- */
function marcar(el){ el.classList.add('field-invalid'); el.focus(); }

function mostrarAlerta(caso, ctx = {}){
  switch(caso){
    case 'solicitante_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el nombre del vecino(a)', text: 'Sin el nombre del usuario la actividad no se puede guardar ni suma puntaje.', confirmButtonColor: BTN });
      marcar(fSolicitante); break;
    case 'telefono_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el teléfono del vecino(a)', text: 'Sin el teléfono del usuario la actividad no se puede guardar ni suma puntaje.', confirmButtonColor: BTN });
      marcar(fTelefono); break;
    case 'telefono_invalido':
      Swal.fire({ icon: 'error', title: 'Teléfono inválido', text: 'Ingresa un teléfono de 8 a 15 dígitos (puedes usar espacios y los signos + ( ) -).', confirmButtonColor: BTN });
      marcar(fTelefono); break;
    case 'semana_cerrada':
      Swal.fire({ icon: 'warning', title: 'Semana cerrada',
        text: `Las actividades de esa semana se podían ingresar hasta el lunes ${ctx.limite ? SGR.formatearFecha(ctx.limite) : 'siguiente'}. Ya no se aceptan ingresos para esa fecha.`,
        confirmButtonColor: BTN });
      marcar(fFecha); break;
    case 'limite_diario':
      Swal.fire({ icon: 'warning', title: 'Límite diario alcanzado',
        text: `El funcionario responsable ya tiene ${ctx.max || opcionesApi.maxPorDia} actividades registradas ese día, que es el máximo permitido.`,
        confirmButtonColor: BTN });
      marcar(fFecha); break;
    case 'tipo_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el tipo de atención', text: 'Selecciona el tipo de atención.', confirmButtonColor: BTN });
      marcar(fTipo); break;
    case 'item_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el ítem', text: 'Selecciona el ítem de la matriz SGR al que corresponde la actividad.', confirmButtonColor: BTN });
      marcar(fItem); break;
    case 'tope':
      Swal.fire({ icon: 'warning', title: `«${ctx.alerta.item}» ya está en ${ctx.alerta.cumplimiento}%`,
        html: `<p>La actividad <b>${esc(ctx.codigo)}</b> quedó registrada, pero <b>no suma puntaje</b>: el ítem superó el tope de 120% del mes.</p>` +
          (ctx.alerta.sugeridos.length
            ? `<p style="margin-top:10px;">Enfócate en los ítems más bajos:</p><ul style="text-align:left;margin:8px auto 0;display:inline-block;">${
                ctx.alerta.sugeridos.map((x) => `<li>${esc(x.item)} — ${x.cumplimiento}%</li>`).join('')}</ul>`
            : ''),
        confirmButtonColor: BTN });
      break;
    case 'ejecutada':
      Swal.fire({ icon: 'success', title: 'Actividad ejecutada',
        text: ctx.puntaje ? `${ctx.codigo} ahora suma 1 punto.` : `${ctx.codigo} quedó ejecutada, pero no suma puntaje (${ctx.motivo}).`,
        timer: ctx.puntaje ? 1600 : 3200, showConfirmButton: false });
      break;
    case 'ejecucion_anterior':
      Swal.fire({ icon: 'warning', title: 'Fecha no válida', text: 'La ejecución no puede ser anterior a la fecha en que se registró la actividad.', confirmButtonColor: BTN });
      break;
    case 'sub_vacia':
      Swal.fire({ icon: 'error', title: 'Falta la sub atención', text: 'Selecciona la sub atención correspondiente al tipo elegido.', confirmButtonColor: BTN });
      marcar(fSub); break;
    case 'descripcion_vacia':
      Swal.fire({ icon: 'error', title: 'Falta la descripción', text: 'Describe la atención realizada (mínimo 10 caracteres).', confirmButtonColor: BTN });
      marcar(fDescripcion); break;
    case 'delegacion_vacia':
      Swal.fire({ icon: 'error', title: 'Falta la delegación', text: 'Selecciona la delegación.', confirmButtonColor: BTN });
      marcar(fDelegacion); break;
    case 'responsable_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el responsable', text: 'Selecciona el usuario responsable de la atención.', confirmButtonColor: BTN });
      marcar(fResponsable); break;
    case 'fecha_vacia':
      Swal.fire({ icon: 'error', title: 'Falta la fecha', text: 'Indica la fecha de registro.', confirmButtonColor: BTN });
      marcar(fFecha); break;
    case 'fecha_futura':
      Swal.fire({ icon: 'warning', title: 'Fecha no válida', text: 'La fecha de registro no puede ser posterior a hoy.', confirmButtonColor: BTN });
      marcar(fFecha); break;
    case 'dato_desactualizado':
      Swal.fire({ icon: 'warning', title: 'Datos desactualizados',
        text: 'Alguna de las opciones elegidas cambió mientras completabas el formulario. Se recargaron las listas; revisa y vuelve a intentar.',
        confirmButtonColor: BTN });
      break;
    case 'guardado': {
      let nota = '';
      if(ctx.otraGestion) nota = ' Quedó como «Otra gestión» porque el solicitante es el Delegado: no suma puntaje.';
      else if(ctx.preparacion) nota = ' Quedó en preparación: sumará puntaje cuando la marques como ejecutada.';
      else if(ctx.puntaje) nota = ' Sumó 1 punto a la matriz.';
      Swal.fire({ icon: 'success', title: 'Atención registrada', text: `Se generó el código ${ctx.codigo}.${nota}`,
        timer: nota && !ctx.puntaje ? 3400 : 1800, showConfirmButton: false });
      break;
    }
    default:
      Swal.fire({ icon: 'error', title: 'No se pudo registrar', text: 'Revisa los datos e inténtalo nuevamente.', confirmButtonColor: BTN });
  }
}

/** Traduce un error de la API al popup que corresponde. */
const CASO_CAMPO_VACIO = {
  solicitante: 'solicitante_vacio', telefono: 'telefono_vacio', itemId: 'item_vacio', tipoId: 'tipo_vacio', subId: 'sub_vacia',
  delegacionId: 'delegacion_vacia', responsableId: 'responsable_vacio', fecha: 'fecha_vacia'
};

function manejarError(err){
  switch(err.error){
    case 'campo_vacio':
      return mostrarAlerta(CASO_CAMPO_VACIO[err.campo] || 'error');
    case 'descripcion_corta':
      return mostrarAlerta('descripcion_vacia');
    case 'fecha_futura':
      return mostrarAlerta('fecha_futura');
    case 'telefono_invalido':
      return mostrarAlerta('telefono_invalido');
    case 'semana_cerrada':
      return mostrarAlerta('semana_cerrada', { limite: err.detalle });
    case 'limite_diario':
      return mostrarAlerta('limite_diario', { max: err.detalle });
    case 'ejecucion_anterior':
      return mostrarAlerta('ejecucion_anterior');
    case 'ya_ejecutada':
      cargarAtenciones();
      return;
    case 'referencia_invalida':
    case 'sub_no_corresponde':
    case 'responsable_invalido':
      recargarOpciones();
      return mostrarAlerta('dato_desactualizado');
  }
  if(SGR.alertaComun(err)) return;
  mostrarAlerta('error');
}

/* ---------- Tabla de atenciones registradas ---------- */
function motivoSinPuntaje(a){
  if(a.estado !== 'Ejecutada') return 'en preparación';
  if(a.clasificacion === 'Otra gestión') return 'otra gestión';
  if(!a.telefono) return 'sin teléfono del vecino';
  if(!a.itemId) return 'sin ítem';
  if(a.topeAlcanzado) return 'ítem sobre 120%';
  return '';
}

function celdaPuntaje(a){
  const item = a.itemNombre ? esc(a.itemNombre) : '<span class="due-note">Sin ítem</span>';
  let estado;
  if(a.estado !== 'Ejecutada'){
    estado = `<span class="badge pendiente"><span class="dot"></span>En preparación</span>` +
      (form ? `<br><button type="button" class="btn-table" data-ejecutar="${a.id}" style="margin-top:6px;">Marcar ejecutada</button>` : '');
  } else if(a.puntaje){
    estado = '<span class="puntaje-cell">+1 pto</span>';
  } else {
    estado = `<span class="due-note">0 pts · ${esc(motivoSinPuntaje(a))}</span>`;
  }
  return `${item}<br>${estado}`;
}
function renderTabla(){
  tablaBody.innerHTML = atenciones.map((a) => `
    <tr>
      <td class="code-cell">${esc(a.codigo)}</td>
      <td>${SGR.formatearFecha(a.fecha)}</td>
      <td>${esc(a.solicitante)}${a.telefono ? `<span class="due-note">${esc(a.telefono)}</span>` : ''}${
        a.clasificacion === 'Otra gestión' ? '<br><span class="tag-otra-gestion">Otra gestión</span>' : ''}</td>
      <td>${esc(a.tipoNombre)}<span class="due-note">${esc(a.subNombre)}</span></td>
      <td>${celdaPuntaje(a)}</td>
      <td>${esc(a.descripcion)}</td>
      <td>${esc(a.delegacionNombre)}</td>
      <td>${esc(a.responsableNombre)}</td>
    </tr>`).join('');

  emptyState.style.display = atenciones.length ? 'none' : 'block';
  contador.textContent = `${atenciones.length} registro${atenciones.length === 1 ? '' : 's'}`;
}

/* ---------- Carga desde la API ---------- */
tablaBody.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-ejecutar]');
  if(!btn) return;
  const a = atenciones.find((x) => x.id === Number(btn.dataset.ejecutar));
  if(!a) return;
  const res = await Swal.fire({
    icon: 'question', title: `¿Marcar ${a.codigo} como ejecutada?`,
    html: '<p>Indica la fecha en que se realizó la actividad.</p>' +
      `<input type="date" id="fechaEjecucion" class="swal2-input" value="${hoy()}" min="${a.fecha}" max="${hoy()}">`,
    showCancelButton: true, confirmButtonText: 'Marcar ejecutada', cancelButtonText: 'Cancelar', confirmButtonColor: BTN,
    preConfirm: () => document.getElementById('fechaEjecucion').value
  });
  if(!res.isConfirmed) return;
  btn.disabled = true;
  try {
    const r = await SGR.post(`atenciones/${a.id}/ejecutar/`, { fecha: res.value || hoy() });
    await cargarAtenciones();
    if(r.alerta) mostrarAlerta('tope', { alerta: r.alerta, codigo: r.codigo });
    else mostrarAlerta('ejecutada', { codigo: r.codigo, puntaje: r.puntaje, motivo: motivoSinPuntaje(r) });
  } catch(err) {
    btn.disabled = false;
    manejarError(err);
  }
});

async function cargarAtenciones(){
  try {
    atenciones = await SGR.get('atenciones/');
    renderTabla();
  } catch(err) {
    if(!SGR.alertaComun(err)) mostrarAlerta('error');
  }
}

async function recargarOpciones(){
  if(!form) return;
  try {
    opcionesApi = await SGR.get('opciones-atencion/');
  } catch(err) {
    if(!SGR.alertaComun(err)) mostrarAlerta('error');
    return;
  }
  cargarTipos();
  cargarDelegaciones();
  if(opcionesApi.fechaMinima){
    fFecha.min = opcionesApi.fechaMinima;
    fechaAyuda.textContent = `Puedes ingresar actividades desde el ${SGR.formatearFecha(opcionesApi.fechaMinima)}. ` +
      'Lo de lunes a viernes se acepta hasta el lunes siguiente.';
  }
  limpiar();
}

/* ---------- Guardar ---------- */
function limpiar(){
  form.reset();
  form.querySelectorAll('.field-invalid').forEach((el) => el.classList.remove('field-invalid'));
  fFecha.value = hoy();
  cargarSubatenciones();
  cargarResponsables();
}

if(form){
  let enviando = false;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if(enviando) return;
    form.querySelectorAll('.field-invalid').forEach((el) => el.classList.remove('field-invalid'));

    const solicitante = fSolicitante.value.trim();
    const telefono = fTelefono.value.trim();
    const descripcion = fDescripcion.value.trim();

    // Validación secuencial: se detiene en el primer caso que falle.
    if(solicitante === ''){ mostrarAlerta('solicitante_vacio'); return; }
    if(telefono === ''){ mostrarAlerta('telefono_vacio'); return; }
    if(!telefonoValido(telefono)){ mostrarAlerta('telefono_invalido'); return; }
    if(!fTipo.value){ mostrarAlerta('tipo_vacio'); return; }
    if(!fItem.value){ mostrarAlerta('item_vacio'); return; }
    if(!fSub.value){ mostrarAlerta('sub_vacia'); return; }
    if(descripcion.length < 10){ mostrarAlerta('descripcion_vacia'); return; }
    if(!fDelegacion.value){ mostrarAlerta('delegacion_vacia'); return; }
    if(!fResponsable.value){ mostrarAlerta('responsable_vacio'); return; }
    if(!fFecha.value){ mostrarAlerta('fecha_vacia'); return; }
    if(fFecha.value > hoy()){ mostrarAlerta('fecha_futura'); return; }
    if(opcionesApi.fechaMinima && fFecha.value < opcionesApi.fechaMinima){ mostrarAlerta('semana_cerrada'); return; }

    enviando = true;
    try {
      const registro = await SGR.post('atenciones/', {
        solicitante,
        telefono,
        solicitanteEsDelegado: fEsDelegado.checked,
        itemId: Number(fItem.value),
        estado: estadoElegido(),
        tipoId: Number(fTipo.value),
        subId: Number(fSub.value),
        descripcion,
        delegacionId: Number(fDelegacion.value),
        responsableId: Number(fResponsable.value),
        fecha: fFecha.value
      });
      limpiar();
      await cargarAtenciones();
      if(registro.alerta) mostrarAlerta('tope', { alerta: registro.alerta, codigo: registro.codigo });
      else mostrarAlerta('guardado', { codigo: registro.codigo, otraGestion: registro.clasificacion === 'Otra gestión',
        preparacion: registro.estado !== 'Ejecutada', puntaje: registro.puntaje });
    } catch(err) {
      manejarError(err);
    } finally {
      enviando = false;
    }
  });

  limpiarBtn.addEventListener('click', limpiar);
  fFecha.max = hoy();
}

/* ---------- Init ---------- */
recargarOpciones();
cargarAtenciones();
