const modalOverlay = document.getElementById('modalOverlay');
const openModalBtn = document.getElementById('openModalBtn');
const closeModalBtn = document.getElementById('closeModalBtn');
const cancelModalBtn = document.getElementById('cancelModalBtn');
const saveCompromisoBtn = document.getElementById('saveCompromisoBtn');
const compromisoForm = document.getElementById('compromisoForm');
const agendaBody = document.getElementById('agendaBody');
const emptyState = document.getElementById('emptyState');

const filtroTerritorio = document.getElementById('filtroTerritorio');
const filtroResponsable = document.getElementById('filtroResponsable');
const filtroEstado = document.getElementById('filtroEstado');
const filtroVencidos = document.getElementById('filtroVencidos');

let nextId = 43;

/* ---------- Modal ---------- */
function openModal(){ modalOverlay.classList.add('open'); }
function closeModal(){
  modalOverlay.classList.remove('open');
  compromisoForm.reset();
}

openModalBtn.addEventListener('click', openModal);
closeModalBtn.addEventListener('click', closeModal);
cancelModalBtn.addEventListener('click', closeModal);
modalOverlay.addEventListener('click', (e) => { if(e.target === modalOverlay) closeModal(); });

saveCompromisoBtn.addEventListener('click', () => {
  const territorio = document.getElementById('cTerritorio').value;
  const solicitante = document.getElementById('cSolicitante').value.trim();
  const descripcion = document.getElementById('cDescripcion').value.trim();
  const responsable = document.getElementById('cResponsable').value;
  const fechaLimite = document.getElementById('cFechaLimite').value;

  if(solicitante === ''){
    Swal.fire({icon:'error', title:'Falta el solicitante', text:'Ingresa quién solicita el compromiso.', confirmButtonColor:'var(--red-primary)'});
    document.getElementById('cSolicitante').focus();
    return;
  }
  if(descripcion === ''){
    Swal.fire({icon:'error', title:'Falta la descripción', text:'Describe el compromiso a registrar.', confirmButtonColor:'var(--red-primary)'});
    document.getElementById('cDescripcion').focus();
    return;
  }
  if(fechaLimite === ''){
    Swal.fire({icon:'error', title:'Falta la fecha límite', text:'Selecciona la fecha límite del compromiso.', confirmButtonColor:'var(--red-primary)'});
    document.getElementById('cFechaLimite').focus();
    return;
  }

  const [year, month, day] = fechaLimite.split('-');
  const fechaFormateada = `${day}/${month}/${year}`;
  const code = `CMP-0${nextId}`;

  const row = document.createElement('tr');
  row.className = 'new-row';
  row.dataset.territorio = territorio;
  row.dataset.responsable = responsable;
  row.dataset.estado = 'pendiente';
  row.innerHTML = `
    <td class="code-cell">${code}</td>
    <td>${territorio}</td>
    <td>${solicitante}</td>
    <td>${descripcion}</td>
    <td>${responsable}</td>
    <td>${fechaFormateada}</td>
    <td><span class="badge pendiente"><span class="dot"></span>Pendiente</span></td>
    <td><button class="btn-table">Editar</button></td>
  `;
  agendaBody.prepend(row);
  nextId++;

  Swal.fire({icon:'success', title:'Compromiso registrado', timer:1200, showConfirmButton:false});
  closeModal();
  applyFilters();
});

/* ---------- Filtros ---------- */
function applyFilters(){
  const territorio = filtroTerritorio.value;
  const responsable = filtroResponsable.value;
  const estado = filtroEstado.value;
  const soloVencidos = filtroVencidos.checked;

  const rows = agendaBody.querySelectorAll('tr');
  let visibleCount = 0;

  rows.forEach((row) => {
    const matchTerritorio = !territorio || row.dataset.territorio === territorio;
    const matchResponsable = !responsable || row.dataset.responsable === responsable;
    const matchEstado = !estado || row.dataset.estado === estado;
    const matchVencido = !soloVencidos || row.dataset.estado === 'vencido';

    const visible = matchTerritorio && matchResponsable && matchEstado && matchVencido;
    row.style.display = visible ? '' : 'none';
    if(visible) visibleCount++;
  });

  emptyState.style.display = visibleCount === 0 ? 'block' : 'none';
}

filtroTerritorio.addEventListener('change', applyFilters);
filtroResponsable.addEventListener('change', applyFilters);
filtroEstado.addEventListener('change', applyFilters);
filtroVencidos.addEventListener('change', applyFilters);
