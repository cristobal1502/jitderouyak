/* ---------- Dataset de ejemplo (reemplazar por los datos reales del backend) ---------- */
const registros = [
  { codigo:'ACT-098', fecha:'2026-08-14', funcionario:'Juan Pérez', item:'Operativo en terreno', descripcion:'Retiro microbasural', evidencia:'foto1.jpg', validacion:'Aprobado', puntaje:1 },
  { codigo:'ACT-092', fecha:'2026-08-11', funcionario:'María Rojas', item:'Operativo en terreno', descripcion:'Despeje de calzada', evidencia:'foto2.jpg', validacion:'Aprobado', puntaje:1 },
  { codigo:'ACT-087', fecha:'2026-08-08', funcionario:'Juan Pérez', item:'Operativo en terreno', descripcion:'Inspección señalética', evidencia:'foto3.jpg', validacion:'Aprobado', puntaje:1 },
  { codigo:'ACT-084', fecha:'2026-08-06', funcionario:'C. Tapia', item:'Mediación vecinal', descripcion:'Mediación por cierre de pasaje', evidencia:'foto4.jpg', validacion:'Aprobado', puntaje:1 },
  { codigo:'ACT-081', fecha:'2026-08-05', funcionario:'Juan Pérez', item:'Atención social', descripcion:'Entrevista ficha FIBE', evidencia:'foto5.jpg', validacion:'Pendiente', puntaje:0 },
  { codigo:'ACT-079', fecha:'2026-08-04', funcionario:'María Rojas', item:'Inspección', descripcion:'Revisión luminarias peatonales', evidencia:'foto6.jpg', validacion:'Aprobado', puntaje:1 },
  { codigo:'ACT-076', fecha:'2026-08-03', funcionario:'Juan Pérez', item:'Operativo en terreno', descripcion:'Retiro de escombros', evidencia:'foto7.jpg', validacion:'Rechazado', puntaje:0 },
  { codigo:'ACT-073', fecha:'2026-08-02', funcionario:'C. Tapia', item:'Atención social', descripcion:'Visita verificación habitacional', evidencia:'foto8.jpg', validacion:'Aprobado', puntaje:1 },
  { codigo:'ACT-070', fecha:'2026-08-01', funcionario:'María Rojas', item:'Mediación vecinal', descripcion:'Mediación comunitaria vecinal', evidencia:'foto9.jpg', validacion:'Aprobado', puntaje:1 },
  { codigo:'ACT-068', fecha:'2026-07-31', funcionario:'Juan Pérez', item:'Operativo en terreno', descripcion:'Retiro microbasural sector norte', evidencia:'foto10.jpg', validacion:'Aprobado', puntaje:1 },
  { codigo:'ACT-065', fecha:'2026-07-29', funcionario:'C. Tapia', item:'Inspección', descripcion:'Inspección de luminaria', evidencia:'foto11.jpg', validacion:'Aprobado', puntaje:1 },
  { codigo:'ACT-061', fecha:'2026-07-27', funcionario:'María Rojas', item:'Atención social', descripcion:'Entrega de beneficio municipal', evidencia:'foto12.jpg', validacion:'Pendiente', puntaje:0 },
  { codigo:'ACT-058', fecha:'2026-07-25', funcionario:'Juan Pérez', item:'Mediación vecinal', descripcion:'Mediación por ruidos molestos', evidencia:'foto13.jpg', validacion:'Aprobado', puntaje:1 },
  { codigo:'ACT-054', fecha:'2026-07-22', funcionario:'C. Tapia', item:'Operativo en terreno', descripcion:'Despeje de vereda peatonal', evidencia:'foto14.jpg', validacion:'Aprobado', puntaje:1 }
];

const PAGE_SIZE = 10;
let resultadosFiltrados = [...registros];
let paginaActual = 1;

const resultsBody = document.getElementById('resultsBody');
const emptyState = document.getElementById('emptyState');
const resultsCount = document.getElementById('resultsCount');
const paginationInfo = document.getElementById('paginationInfo');
const paginationControls = document.getElementById('paginationControls');

const fDelegacion = document.getElementById('fDelegacion');
const fPeriodo = document.getElementById('fPeriodo');
const fFuncionario = document.getElementById('fFuncionario');
const fItem = document.getElementById('fItem');
const fEvidencia = document.getElementById('fEvidencia');
const fFechaDesde = document.getElementById('fFechaDesde');
const fFechaHasta = document.getElementById('fFechaHasta');
const fPalabras = document.getElementById('fPalabras');

const applyFiltersBtn = document.getElementById('applyFiltersBtn');
const clearFiltersBtn = document.getElementById('clearFiltersBtn');
const exportPdfBtn = document.getElementById('exportPdfBtn');
const exportExcelBtn = document.getElementById('exportExcelBtn');

/* ---------- Formato ---------- */
function formatearFecha(isoDate){
  const [y, m, d] = isoDate.split('-');
  return `${d}/${m}/${y}`;
}

function badgeValidacion(v){
  const clase = v === 'Aprobado' ? 'aprobada' : v === 'Rechazado' ? 'vencido' : 'pendiente';
  return `<span class="badge ${clase}"><span class="dot"></span>${v}</span>`;
}

/* ---------- Filtros ---------- */
function aplicarFiltros(){
  const funcionario = fFuncionario.value;
  const item = fItem.value;
  const evidencia = fEvidencia.value;
  const desde = fFechaDesde.value;
  const hasta = fFechaHasta.value;
  const palabras = fPalabras.value.trim().toLowerCase();

  resultadosFiltrados = registros.filter(r => {
    if(funcionario && r.funcionario !== funcionario) return false;
    if(item && r.item !== item) return false;
    if(evidencia && r.validacion !== evidencia) return false;
    if(desde && r.fecha < desde) return false;
    if(hasta && r.fecha > hasta) return false;
    if(palabras && !r.descripcion.toLowerCase().includes(palabras)) return false;
    return true;
  });

  paginaActual = 1;
  renderResultados();
}

function limpiarFiltros(){
  fFuncionario.value = '';
  fItem.value = '';
  fEvidencia.value = '';
  fFechaDesde.value = '';
  fFechaHasta.value = '';
  fPalabras.value = '';
  resultadosFiltrados = [...registros];
  paginaActual = 1;
  renderResultados();
}

applyFiltersBtn.addEventListener('click', aplicarFiltros);
clearFiltersBtn.addEventListener('click', limpiarFiltros);

/* ---------- Render tabla + paginación ---------- */
function renderResultados(){
  const total = resultadosFiltrados.length;
  const totalPaginas = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if(paginaActual > totalPaginas) paginaActual = totalPaginas;

  const inicio = (paginaActual - 1) * PAGE_SIZE;
  const pagina = resultadosFiltrados.slice(inicio, inicio + PAGE_SIZE);

  resultsCount.textContent = total;
  emptyState.style.display = total === 0 ? 'block' : 'none';

  resultsBody.innerHTML = pagina.map(r => `
    <tr>
      <td class="code-cell">${r.codigo}</td>
      <td>${formatearFecha(r.fecha)}</td>
      <td>${r.funcionario}</td>
      <td>${r.item}</td>
      <td>${r.descripcion}</td>
      <td class="evidencia-file">${r.evidencia}</td>
      <td>${badgeValidacion(r.validacion)}</td>
      <td class="puntaje-cell ${r.puntaje === 0 ? 'negativo' : ''}">${r.puntaje > 0 ? '+' + r.puntaje + ' pto' : '—'}</td>
    </tr>
  `).join('');

  const desdeN = total === 0 ? 0 : inicio + 1;
  const hastaN = Math.min(inicio + PAGE_SIZE, total);
  paginationInfo.textContent = total === 0
    ? 'Sin registros'
    : `Mostrando registros ${desdeN}-${hastaN} de ${total}`;

  renderPaginacion(totalPaginas);
}

function renderPaginacion(totalPaginas){
  let html = `<button class="page-btn" id="prevPageBtn" ${paginaActual === 1 ? 'disabled' : ''}>&lt; Anterior</button>`;
  for(let i = 1; i <= totalPaginas; i++){
    html += `<button class="page-btn ${i === paginaActual ? 'active' : ''}" data-page="${i}">${i}</button>`;
  }
  html += `<button class="page-btn" id="nextPageBtn" ${paginaActual === totalPaginas ? 'disabled' : ''}>Siguiente &gt;</button>`;
  paginationControls.innerHTML = html;

  document.getElementById('prevPageBtn').addEventListener('click', () => {
    if(paginaActual > 1){ paginaActual--; renderResultados(); }
  });
  document.getElementById('nextPageBtn').addEventListener('click', () => {
    if(paginaActual < totalPaginas){ paginaActual++; renderResultados(); }
  });
  paginationControls.querySelectorAll('[data-page]').forEach(btn => {
    btn.addEventListener('click', () => {
      paginaActual = parseInt(btn.dataset.page, 10);
      renderResultados();
    });
  });
}

/* ---------- Exportación (placeholder hasta conectar el backend) ---------- */
exportPdfBtn.addEventListener('click', () => {
  Swal.fire({
    icon: 'info',
    title: 'Exportar a PDF',
    text: 'Esta acción todavía no está conectada al backend. Aquí se generará el reporte de los registros filtrados.',
    confirmButtonColor: 'var(--red-primary)'
  });
});

exportExcelBtn.addEventListener('click', () => {
  Swal.fire({
    icon: 'info',
    title: 'Exportar a Excel',
    text: 'Esta acción todavía no está conectada al backend. Aquí se generará el archivo .xlsx de los registros filtrados.',
    confirmButtonColor: 'var(--red-primary)'
  });
});

/* ---------- Init ---------- */
renderResultados();
