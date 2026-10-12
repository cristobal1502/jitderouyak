const esc = SGR.esc;
const BTN = 'var(--red-primary)';

const form = document.getElementById('atencionForm'); // null si el rol no tiene permiso para registrar
const fSolicitante = document.getElementById('aSolicitante');
const fFecha = document.getElementById('aFecha');
const fTipo = document.getElementById('aTipo');
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
let opcionesApi = { tipos: [], subatenciones: [], delegaciones: [], responsables: [] };
let atenciones = [];

/* ---------- Selects que dependen del catálogo de Administración ---------- */
function opciones(lista, placeholder){
  return `<option value="">${placeholder}</option>` +
    lista.map((r) => `<option value="${r.id}">${esc(r.nombre)}</option>`).join('');
}

function cargarTipos(){
  fTipo.innerHTML = opciones(opcionesApi.tipos, 'Selecciona un tipo…');
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
      Swal.fire({ icon: 'error', title: 'Falta el solicitante', text: 'Ingresa el nombre o RUT de quien solicita la atención.', confirmButtonColor: BTN });
      marcar(fSolicitante); break;
    case 'tipo_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el tipo de atención', text: 'Selecciona el tipo de atención.', confirmButtonColor: BTN });
      marcar(fTipo); break;
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
    case 'guardado':
      Swal.fire({ icon: 'success', title: 'Atención registrada', text: `Se generó el código ${ctx.codigo}.`, timer: 1600, showConfirmButton: false });
      break;
    default:
      Swal.fire({ icon: 'error', title: 'No se pudo registrar', text: 'Revisa los datos e inténtalo nuevamente.', confirmButtonColor: BTN });
  }
}

/** Traduce un error de la API al popup que corresponde. */
const CASO_CAMPO_VACIO = {
  solicitante: 'solicitante_vacio', tipoId: 'tipo_vacio', subId: 'sub_vacia',
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
function renderTabla(){
  tablaBody.innerHTML = atenciones.map((a) => `
    <tr>
      <td class="code-cell">${esc(a.codigo)}</td>
      <td>${SGR.formatearFecha(a.fecha)}</td>
      <td>${esc(a.solicitante)}</td>
      <td>${esc(a.tipoNombre)}<span class="due-note">${esc(a.subNombre)}</span></td>
      <td>${esc(a.descripcion)}</td>
      <td>${esc(a.delegacionNombre)}</td>
      <td>${esc(a.responsableNombre)}</td>
    </tr>`).join('');

  emptyState.style.display = atenciones.length ? 'none' : 'block';
  contador.textContent = `${atenciones.length} registro${atenciones.length === 1 ? '' : 's'}`;
}

/* ---------- Carga desde la API ---------- */
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
    const descripcion = fDescripcion.value.trim();

    // Validación secuencial: se detiene en el primer caso que falle.
    if(solicitante === ''){ mostrarAlerta('solicitante_vacio'); return; }
    if(!fTipo.value){ mostrarAlerta('tipo_vacio'); return; }
    if(!fSub.value){ mostrarAlerta('sub_vacia'); return; }
    if(descripcion.length < 10){ mostrarAlerta('descripcion_vacia'); return; }
    if(!fDelegacion.value){ mostrarAlerta('delegacion_vacia'); return; }
    if(!fResponsable.value){ mostrarAlerta('responsable_vacio'); return; }
    if(!fFecha.value){ mostrarAlerta('fecha_vacia'); return; }
    if(fFecha.value > hoy()){ mostrarAlerta('fecha_futura'); return; }

    enviando = true;
    try {
      const registro = await SGR.post('atenciones/', {
        solicitante,
        tipoId: Number(fTipo.value),
        subId: Number(fSub.value),
        descripcion,
        delegacionId: Number(fDelegacion.value),
        responsableId: Number(fResponsable.value),
        fecha: fFecha.value
      });
      limpiar();
      await cargarAtenciones();
      mostrarAlerta('guardado', { codigo: registro.codigo });
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
