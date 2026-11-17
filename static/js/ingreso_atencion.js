const esc = SGR.esc;
const BTN = 'var(--red-primary)';

const form = document.getElementById('atencionForm'); // null si el rol no tiene permiso para registrar
const fSolicitante = document.getElementById('aSolicitante');
const fTelefono = document.getElementById('aTelefono');
const fRut = document.getElementById('aRut');
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
const fOrganizacion = document.getElementById('aOrganizacion');
const campoOrganizacion = document.getElementById('campoOrganizacion');
const fPlazo = document.getElementById('aPlazo');
const rutOrgs = document.getElementById('rutOrgs');
const beneficiarioElegido = () => (document.querySelector('input[name="aBeneficiario"]:checked') || {}).value || 'Persona natural';
const limpiarBtn = document.getElementById('limpiarBtn');
const tablaBody = document.getElementById('tablaBody');
const emptyState = document.getElementById('emptyState');
const contador = document.getElementById('contador');

const hoy = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD en hora local

/* Catálogos y atenciones vienen de la base de datos (API) */
let opcionesApi = { tipos: [], subatenciones: [], items: [], delegaciones: [], responsables: [], organizaciones: [],
  fechaMinima: '', maxPorDia: 7, plazoDias: 7 };
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

/* ---------- Persona natural u organización ---------- */
function cargarOrganizaciones(){
  const delId = Number(fDelegacion.value);
  const actual = fOrganizacion.value;
  const lista = opcionesApi.organizaciones.filter((o) => !delId || o.delegacionId === delId);
  fOrganizacion.innerHTML = opciones(lista, lista.length ? 'Selecciona la organización…' : 'Esta delegación no tiene organizaciones activas');
  if(lista.some((o) => String(o.id) === actual)) fOrganizacion.value = actual;
}

function mostrarCampoOrganizacion(){
  const esOrg = beneficiarioElegido() === 'Organización';
  campoOrganizacion.hidden = !esOrg;
  if(esOrg) fOrganizacion.setAttribute('data-requerido', ''); else fOrganizacion.removeAttribute('data-requerido');
}

function elegirOrganizacion(org){
  // Si la organización es de otra delegación del usuario, se cambia la delegación también.
  if(org.delegacionId && String(org.delegacionId) !== fDelegacion.value &&
     opcionesApi.delegaciones.some((d) => d.id === org.delegacionId)){
    fDelegacion.value = String(org.delegacionId);
    cargarResponsables();
  }
  cargarOrganizaciones();
  document.querySelector('input[name="aBeneficiario"][value="Organización"]').checked = true;
  mostrarCampoOrganizacion();
  fOrganizacion.value = String(org.id);
  SGRValidar.validarCampo(fOrganizacion, true);
}

/* ---------- RUT: ¿es dirigente de alguna organización? ---------- */
let consultaRut = 0;
async function buscarOrganizacionesPorRut(){
  const rut = fRut.value.trim();
  const turno = ++consultaRut;
  if(!rut || !SGRValidar.esRutValido(rut)){ rutOrgs.hidden = true; rutOrgs.innerHTML = ''; return; }
  let r;
  try { r = await SGR.get(`organizaciones/por-rut/?rut=${encodeURIComponent(rut)}`); }
  catch(err) { rutOrgs.hidden = true; return; }
  if(turno !== consultaRut) return;  // llegó una respuesta vieja
  if(!r.organizaciones.length){ rutOrgs.hidden = true; rutOrgs.innerHTML = ''; return; }
  const nombre = r.organizaciones[0].personaNombre;
  rutOrgs.innerHTML = `<p class="rut-orgs-titulo">${esc(nombre)} está registrado(a) en ${r.organizaciones.length === 1 ? 'una organización' : `${r.organizaciones.length} organizaciones`}:</p>` +
    r.organizaciones.map((o) => `
      <div class="rut-org">
        <span><b>${esc(o.cargo)}</b> de ${esc(o.nombre)}<span class="due-note">${esc(o.delegacionNombre)} · ${esc(o.verificacion)}</span></span>
        <button type="button" class="btn-table" data-org="${o.id}" data-delegacion="${o.delegacionId}">Atención para esta organización</button>
      </div>`).join('');
  rutOrgs.dataset.orgs = JSON.stringify(r.organizaciones);
  rutOrgs.hidden = false;
  if(!fSolicitante.value.trim() && nombre){
    fSolicitante.value = nombre;  // completa el nombre con el de la directiva
    SGRValidar.validarCampo(fSolicitante, true);
  }
  const telefono = r.organizaciones[0].personaTelefono;
  if(!fTelefono.value.trim() && telefono){
    fTelefono.value = telefono;   // y el teléfono registrado en la directiva
    SGRValidar.validarCampo(fTelefono, true);
  }
}

if(form){
  fTipo.addEventListener('change', cargarSubatenciones);
  fDelegacion.addEventListener('change', () => { cargarResponsables(); cargarOrganizaciones(); });
  form.querySelectorAll('input[name="aBeneficiario"]').forEach((r) => r.addEventListener('change', mostrarCampoOrganizacion));
  let espera;
  fRut.addEventListener('input', () => { clearTimeout(espera); espera = setTimeout(buscarOrganizacionesPorRut, 350); });
  rutOrgs.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-org]');
    if(!btn) return;
    const org = JSON.parse(rutOrgs.dataset.orgs || '[]').find((o) => String(o.id) === btn.dataset.org);
    if(!org) return;
    if(!opcionesApi.organizaciones.some((o) => o.id === org.id)){
      Swal.fire({ icon: 'info', title: 'Organización de otra delegación',
        text: `${org.nombre} pertenece a ${org.delegacionNombre}, que no está entre tus delegaciones.`, confirmButtonColor: BTN });
      return;
    }
    elegirOrganizacion({ id: org.id, delegacionId: org.delegacionId });
  });
  // El plazo sigue a la fecha de la actividad mientras no se cambie a mano.
  fFecha.addEventListener('change', () => {
    fPlazo.min = fFecha.value;
    if(!fPlazo.dataset.manual && fFecha.value) fPlazo.value = sumarDias(fFecha.value, opcionesApi.plazoDias);
  });
  fPlazo.addEventListener('change', () => { fPlazo.dataset.manual = '1'; });
}

function sumarDias(iso, dias){
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + dias)).toISOString().slice(0, 10);
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
    case 'campos_invalidos':
      Swal.fire({ icon: 'error', title: ctx.titulo || 'Revisa los campos marcados',
        text: ctx.detalle || 'Hay datos con errores; el mensaje aparece bajo cada campo.', confirmButtonColor: BTN });
      if(ctx.campo) ctx.campo.focus();
      break;
    case 'rut_invalido':
      Swal.fire({ icon: 'error', title: 'RUT inválido', text: 'El RUT no es válido: revisa los números y el dígito verificador.', confirmButtonColor: BTN });
      marcar(fRut); break;
    case 'nombre_invalido':
      Swal.fire({ icon: 'error', title: 'Nombre inválido', text: 'Escribe el nombre del vecino(a), no solo números o símbolos.', confirmButtonColor: BTN });
      marcar(fSolicitante); break;
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
    case 'organizacion_vacia':
      Swal.fire({ icon: 'error', title: 'Falta la organización', text: 'Elegiste que la atención es para una organización: selecciona cuál.', confirmButtonColor: BTN });
      marcar(fOrganizacion); break;
    case 'plazo_anterior':
      Swal.fire({ icon: 'warning', title: 'Plazo no válido', text: 'El plazo del compromiso no puede ser anterior a la fecha de la actividad.', confirmButtonColor: BTN });
      marcar(fPlazo); break;
    case 'item_vacio':
      Swal.fire({ icon: 'error', title: 'Falta el ítem', text: 'Selecciona el ítem de la matriz SGR al que corresponde la actividad.', confirmButtonColor: BTN });
      marcar(fItem); break;
    case 'tope':
      Swal.fire({ icon: 'warning', title: `«${ctx.alerta.item}» ya está en ${ctx.alerta.cumplimiento}%`,
        html: `<p>La actividad <b>${esc(ctx.codigo)}</b> quedó registrada, pero <b>no suma puntaje</b>: el ítem superó el tope de 120% del ${esc(ctx.alerta.trimestre || 'trimestre')}.</p>` +
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
      nota += ctx.preparacion ? ' Entró al tubo en «Ingresado».' : ' Quedó en el tubo como «Realizado».';
      Swal.fire({ icon: 'success', title: 'Atención registrada', text: `Se generó el código ${ctx.codigo}.${nota}`,
        timer: 3400, showConfirmButton: false });
      break;
    }
    default:
      Swal.fire({ icon: 'error', title: 'No se pudo registrar', text: 'Revisa los datos e inténtalo nuevamente.', confirmButtonColor: BTN });
  }
}

/** Traduce un error de la API al popup que corresponde. */
const CASO_CAMPO_VACIO = {
  solicitante: 'solicitante_vacio', telefono: 'telefono_vacio', itemId: 'item_vacio', tipoId: 'tipo_vacio', subId: 'sub_vacia',
  delegacionId: 'delegacion_vacia', responsableId: 'responsable_vacio', fecha: 'fecha_vacia',
  organizacionId: 'organizacion_vacia'
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
    case 'rut_invalido':
    case 'nombre_invalido':
      return mostrarAlerta(err.error);
    case 'semana_cerrada':
      return mostrarAlerta('semana_cerrada', { limite: err.detalle });
    case 'limite_diario':
      return mostrarAlerta('limite_diario', { max: err.detalle });
    case 'ejecucion_anterior':
      return mostrarAlerta('ejecucion_anterior');
    case 'plazo_anterior':
      return mostrarAlerta('plazo_anterior');
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

function badgeEtapa(a){
  const clase = a.vencido ? 'vencido' : { 'Realizado': 'realizado', 'En proceso': 'en-proceso', 'Pendiente': 'pendiente' }[a.etapa] || 'aprobada';
  return `<a class="enlace-tubo" href="/dashboard/agenda/" title="Ver en el tubo"><span class="badge ${clase}"><span class="dot"></span>${a.vencido ? 'Vencido' : esc(a.etapa)}</span></a>`;
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
      <td>${esc(a.solicitante)}${a.rut ? `<span class="due-note">${esc(a.rut)}</span>` : ''}${
        a.organizacionNombre ? `<span class="due-note">Para: ${esc(a.organizacionNombre)}</span>` : ''}${a.telefono ? `<span class="due-note">${esc(a.telefono)}</span>` : ''}${
        a.clasificacion === 'Otra gestión' ? '<br><span class="tag-otra-gestion">Otra gestión</span>' : ''}</td>
      <td>${esc(a.tipoNombre)}<span class="due-note">${esc(a.subNombre)}</span></td>
      <td>${celdaPuntaje(a)}</td>
      <td>${badgeEtapa(a)}</td>
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
  cargarOrganizaciones();
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
  delete fPlazo.dataset.manual;
  fPlazo.min = fFecha.value;
  fPlazo.value = sumarDias(fFecha.value, opcionesApi.plazoDias || 7);
  rutOrgs.hidden = true;
  rutOrgs.innerHTML = '';
  const activa = SGR.delegacionActiva();  // la delegación elegida arriba queda preseleccionada
  if(activa && opcionesApi.delegaciones.some((d) => d.id === activa)) fDelegacion.value = String(activa);
  cargarSubatenciones();
  cargarResponsables();
  cargarOrganizaciones();
  mostrarCampoOrganizacion();
}

if(form){
  let enviando = false;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if(enviando) return;
    form.querySelectorAll('.field-invalid').forEach((el) => el.classList.remove('field-invalid'));

    // Primero la validación en vivo: deja el mensaje bajo cada campo con error.
    const campoMalo = SGRValidar.validarTodo(form);
    if(campoMalo){
      const label = form.querySelector(`label[for="${campoMalo.id}"]`);
      const detalle = (document.getElementById(`${campoMalo.id}-msg`) || {}).textContent;
      mostrarAlerta('campos_invalidos', { campo: campoMalo,
        titulo: label ? `Revisa: ${label.textContent.replace(/\*|opcional/g, '').trim()}` : '', detalle });
      return;
    }

    const solicitante = fSolicitante.value.trim();
    const rut = fRut.value.trim();
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
    const beneficiario = beneficiarioElegido();
    if(beneficiario === 'Organización' && !fOrganizacion.value){ mostrarAlerta('organizacion_vacia'); return; }
    if(fPlazo.value && fPlazo.value < fFecha.value){ mostrarAlerta('plazo_anterior'); return; }

    enviando = true;
    try {
      const registro = await SGR.post('atenciones/', {
        solicitante,
        rut,
        telefono,
        solicitanteEsDelegado: fEsDelegado.checked,
        itemId: Number(fItem.value),
        estado: estadoElegido(),
        tipoId: Number(fTipo.value),
        subId: Number(fSub.value),
        descripcion,
        delegacionId: Number(fDelegacion.value),
        responsableId: Number(fResponsable.value),
        fecha: fFecha.value,
        beneficiario,
        organizacionId: beneficiario === 'Organización' ? Number(fOrganizacion.value) : null,
        fechaCompromiso: fPlazo.value || null
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
