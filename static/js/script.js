const modalOverlay = document.getElementById('modalOverlay');
const openModalBtn = document.getElementById('openModalBtn');
const closeModalBtn = document.getElementById('closeModalBtn');
const cancelModalBtn = document.getElementById('cancelModalBtn');
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const saveActivityBtn = document.getElementById('saveActivityBtn');
const historyBody = document.getElementById('historyBody');
const activityForm = document.getElementById('activityForm');

const UPLOAD_DEFAULT_HTML = `
  <span class="upload-main">Arrastra un archivo aquí o haz clic para subir</span>
  <span class="upload-caption">JPG, PNG o PDF (Máx. 10MB)</span>
`;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'application/pdf'];

let selectedFile = null;
let nextCode = 103;

/**
 * Muestra un popup de SweetAlert2 según el caso de validación del formulario
 * de nueva actividad.
 */
function mostrarAlertaActividad(caso){
  switch(caso){
    case 'solicitud_vacia':
      Swal.fire({
        icon: 'error',
        title: 'Falta la solicitud',
        text: 'Describe la solicitud o el problema atendido.',
        confirmButtonColor: 'var(--red-primary)'
      });
      break;

    case 'accion_vacia':
      Swal.fire({
        icon: 'error',
        title: 'Falta la acción ejecutada',
        text: 'Describe la acción que se ejecutó para esta actividad.',
        confirmButtonColor: 'var(--red-primary)'
      });
      break;

    case 'fecha_vacia':
      Swal.fire({
        icon: 'error',
        title: 'Falta la fecha',
        text: 'Selecciona la fecha en que se realizó la actividad.',
        confirmButtonColor: 'var(--red-primary)'
      });
      break;

    case 'evidencia_vacia':
      Swal.fire({
        icon: 'error',
        title: 'Falta la evidencia fotográfica',
        text: 'Sube un archivo como evidencia antes de guardar.',
        confirmButtonColor: 'var(--red-primary)'
      });
      break;

    case 'evidencia_tipo_invalido':
      Swal.fire({
        icon: 'error',
        title: 'Formato no permitido',
        text: 'Solo se aceptan archivos JPG, PNG o PDF.',
        confirmButtonColor: 'var(--red-primary)'
      });
      break;

    case 'evidencia_muy_grande':
      Swal.fire({
        icon: 'error',
        title: 'Archivo muy pesado',
        text: 'El archivo no puede superar los 10MB.',
        confirmButtonColor: 'var(--red-primary)'
      });
      break;

    case 'guardado':
      Swal.fire({
        icon: 'success',
        title: 'Actividad registrada',
        text: 'Se generó el código ACT correctamente.',
        timer: 1400,
        showConfirmButton: false
      });
      break;
  }
}

function openModal(){ modalOverlay.classList.add('open'); }

function closeModal(){
  modalOverlay.classList.remove('open');
  activityForm.reset();
  uploadZone.innerHTML = UPLOAD_DEFAULT_HTML;
  uploadZone.classList.remove('has-file');
  selectedFile = null;
}

openModalBtn.addEventListener('click', openModal);
closeModalBtn.addEventListener('click', closeModal);
cancelModalBtn.addEventListener('click', closeModal);
modalOverlay.addEventListener('click', (e) => { if(e.target === modalOverlay) closeModal(); });

uploadZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
  if(!fileInput.files.length) return;

  const file = fileInput.files[0];

  if(!ALLOWED_TYPES.includes(file.type)){
    mostrarAlertaActividad('evidencia_tipo_invalido');
    fileInput.value = '';
    return;
  }
  if(file.size > MAX_FILE_SIZE){
    mostrarAlertaActividad('evidencia_muy_grande');
    fileInput.value = '';
    return;
  }

  selectedFile = file;
  uploadZone.innerHTML = `
    <span class="upload-main">${file.name}</span>
    <span class="upload-caption">${(file.size / 1024 / 1024).toFixed(1)} MB · listo para subir</span>
  `;
  uploadZone.classList.add('has-file');
});

saveActivityBtn.addEventListener('click', () => {
  const tipoSelect = document.getElementById('tipoActividad');
  const tipo = tipoSelect.options[tipoSelect.selectedIndex].value;
  const solicitud = document.getElementById('solicitudActividad').value.trim();
  const accion = document.getElementById('accionActividad').value.trim();
  const contactoNombre = document.getElementById('contactoNombre').value.trim();
  const contactoTelefono = document.getElementById('contactoTelefono').value.trim();
  const fecha = document.getElementById('fechaActividad').value;
  const derivar = document.getElementById('derivarAgenda').checked;

  // Validación secuencial: se detiene en el primer campo requerido que falte.
  if(solicitud === ''){
    mostrarAlertaActividad('solicitud_vacia');
    document.getElementById('solicitudActividad').focus();
    return;
  }
  if(accion === ''){
    mostrarAlertaActividad('accion_vacia');
    document.getElementById('accionActividad').focus();
    return;
  }
  if(fecha === ''){
    mostrarAlertaActividad('fecha_vacia');
    document.getElementById('fechaActividad').focus();
    return;
  }
  if(!selectedFile){
    mostrarAlertaActividad('evidencia_vacia');
    return;
  }

  const code = `ACT-${nextCode}`;
  const row = document.createElement('tr');
  row.className = 'new-row';
  row.innerHTML = `
    <td class="code-cell">${code}</td>
    <td>${solicitud}</td>
    <td>
      <span class="evidence-link">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
        ${selectedFile.name}
      </span>
    </td>
    <td><span class="badge pendiente"><span class="dot"></span>Pendiente</span></td>
  `;
  historyBody.prepend(row);
  nextCode++;

  mostrarAlertaActividad('guardado');
  closeModal();

  // Datos disponibles para cuando conectes esto a tu backend de Django:
  // { code, tipo, solicitud, accion, contactoNombre, contactoTelefono, fecha, derivar, selectedFile }
});
