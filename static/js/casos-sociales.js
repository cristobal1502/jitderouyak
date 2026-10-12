/* ---------- Datos de ejemplo (reemplazar por los datos reales del backend) ---------- */
let casos = [
  {
    id: 'CS-1082',
    nombre: 'María Morales Carrasco',
    rut: '12.345.678-9',
    sector: 'Tierras Blancas',
    telefono: '+56 9 8765 4321',
    expanded: true,
    gestiones: [
      {
        numero: 1,
        fecha: '02/08/2026',
        tipo: 'Atención inicial / Ficha FIBE',
        detalle: 'Entrevista en delegación y diagnóstico socioeconómico preliminar.',
        atendidoPor: 'J. Pérez',
        pendiente: false
      },
      {
        numero: 2,
        fecha: '20/08/2026',
        tipo: 'Visita a terreno / Verificación habitacional',
        detalle: 'Visita en domicilio para verificar condiciones de techumbre tras precipitaciones.',
        atendidoPor: 'J. Pérez',
        pendiente: false
      },
      {
        numero: 3,
        fecha: null,
        tipo: 'Entrega de beneficio municipal',
        detalle: 'Entrega de subsidio o materiales programada para fin de mes.',
        atendidoPor: null,
        pendiente: true
      }
    ]
  },
  {
    id: 'CS-1081',
    nombre: 'Carlos Araya Godoy',
    rut: '9.876.543-2',
    sector: 'Coquimbo Oriente',
    telefono: '+56 9 1122 3344',
    expanded: false,
    gestiones: [
      {
        numero: 1,
        fecha: '28/07/2026',
        tipo: 'Atención inicial / Ficha FIBE',
        detalle: 'Entrevista inicial y levantamiento de antecedentes.',
        atendidoPor: 'C. Tapia',
        pendiente: false
      },
      {
        numero: 2,
        fecha: '15/08/2026',
        tipo: 'Derivación a otra red',
        detalle: 'Derivación a red de apoyo comunal para seguimiento.',
        atendidoPor: 'C. Tapia',
        pendiente: false
      }
    ]
  }
];

let nextCsId = 1083;
let modalMode = 'nuevo-caso'; // 'nuevo-caso' | 'nueva-gestion'
let casoActivoId = null;

const casosContainer = document.getElementById('casosContainer');
const emptyState = document.getElementById('emptyState');
const buscarUsuario = document.getElementById('buscarUsuario');
const buscarBtn = document.getElementById('buscarBtn');

const modalOverlay = document.getElementById('modalOverlay');
const modalTitle = document.getElementById('modalTitle');
const openModalBtn = document.getElementById('openModalBtn');
const closeModalBtn = document.getElementById('closeModalBtn');
const cancelModalBtn = document.getElementById('cancelModalBtn');
const saveCasoBtn = document.getElementById('saveCasoBtn');
const casoForm = document.getElementById('casoForm');
const datosUsuarioFields = document.getElementById('datosUsuarioFields');

/* ---------- Render ---------- */
function renderCasos(filtro){
  const term = (filtro || '').trim().toLowerCase();
  const casosFiltrados = term
    ? casos.filter(c => c.nombre.toLowerCase().includes(term) || c.rut.toLowerCase().includes(term))
    : casos;

  emptyState.style.display = casosFiltrados.length === 0 ? 'block' : 'none';
  casosContainer.innerHTML = casosFiltrados.map(renderCasoCard).join('');

  // Re-enganchar eventos después de reconstruir el HTML
  casosContainer.querySelectorAll('.caso-header').forEach(header => {
    header.addEventListener('click', () => toggleCaso(header.dataset.id));
  });
  casosContainer.querySelectorAll('.caso-collapsed-hint').forEach(hint => {
    hint.addEventListener('click', () => toggleCaso(hint.dataset.id));
  });
  casosContainer.querySelectorAll('.btn-register-gestion').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openModalNuevaGestion(btn.dataset.id);
    });
  });
}

function renderCasoCard(caso){
  const gestionesRegistradas = caso.gestiones.filter(g => !g.pendiente).length;

  if(!caso.expanded){
    return `
      <div class="caso-card" data-id="${caso.id}">
        <div class="caso-header" data-id="${caso.id}">
          <span class="caso-id">CASO #${caso.id}:</span>
          <span class="caso-nombre">${caso.nombre}</span>
          <span class="caso-meta-item">RUT: <b>${caso.rut}</b></span>
          <span class="caso-meta-item">Sector: <b>${caso.sector}</b></span>
          <span class="caso-meta-item">Tel: <b>${caso.telefono}</b></span>
          <span class="caso-toggle-icon">${chevronIcon()}</span>
        </div>
        <div class="caso-collapsed-hint" data-id="${caso.id}">
          Desplegar historial de ${gestionesRegistradas} gestion${gestionesRegistradas === 1 ? '' : 'es'} registrada${gestionesRegistradas === 1 ? '' : 's'}
        </div>
      </div>
    `;
  }

  return `
    <div class="caso-card expanded" data-id="${caso.id}">
      <div class="caso-header" data-id="${caso.id}">
        <span class="caso-id">CASO #${caso.id}:</span>
        <span class="caso-nombre">${caso.nombre}</span>
        <span class="caso-meta-item">RUT: <b>${caso.rut}</b></span>
        <span class="caso-meta-item">Sector: <b>${caso.sector}</b></span>
        <span class="caso-meta-item">Tel: <b>${caso.telefono}</b></span>
        <span class="caso-toggle-icon">${chevronIcon()}</span>
      </div>
      <div class="caso-body">
        <div class="caso-body-label">Secuencia de atenciones (RF-015: máximo 3 gestiones vinculadas)</div>
        <div class="gestion-timeline">
          ${caso.gestiones.map(g => renderGestionStep(g, caso.id)).join('')}
        </div>
      </div>
    </div>
  `;
}

function renderGestionStep(g, casoId){
  if(g.pendiente){
    return `
      <div class="gestion-step">
        <div class="step-marker-col">
          <div class="step-marker pending">${g.numero}</div>
        </div>
        <div class="step-content">
          <div class="step-title-row">
            <span class="step-title">${g.tipo}</span>
            <span class="step-date pendiente">Gestión ${g.numero} — Pendiente</span>
          </div>
          <div class="step-detail">${g.detalle}</div>
          <button class="btn-register-gestion" data-id="${casoId}">+ Registrar gestión ${g.numero}</button>
        </div>
      </div>
    `;
  }

  return `
    <div class="gestion-step">
      <div class="step-marker-col">
        <div class="step-marker">${g.numero}</div>
        <div class="step-connector"></div>
      </div>
      <div class="step-content">
        <div class="step-title-row">
          <span class="step-title">${g.tipo}</span>
          <span class="step-date">Gestión ${g.numero} — ${g.fecha}</span>
        </div>
        <div class="step-detail">${g.detalle}</div>
        <div class="step-atendido">Atendido por: ${g.atendidoPor}</div>
      </div>
    </div>
  `;
}

function chevronIcon(){
  return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>`;
}

function toggleCaso(id){
  const caso = casos.find(c => c.id === id);
  if(caso){
    caso.expanded = !caso.expanded;
    renderCasos(buscarUsuario.value);
  }
}

/* ---------- Búsqueda ---------- */
buscarBtn.addEventListener('click', () => renderCasos(buscarUsuario.value));
buscarUsuario.addEventListener('keydown', (e) => {
  if(e.key === 'Enter') renderCasos(buscarUsuario.value);
});
buscarUsuario.addEventListener('input', () => {
  if(buscarUsuario.value.trim() === '') renderCasos('');
});

/* ---------- Modal ---------- */
function openModalNuevoCaso(){
  modalMode = 'nuevo-caso';
  casoActivoId = null;
  modalTitle.textContent = 'Nueva atención social';
  datosUsuarioFields.style.display = 'block';
  document.getElementById('gTipo').value = 'Atención inicial / Ficha FIBE';
  modalOverlay.classList.add('open');
}

function openModalNuevaGestion(casoId){
  const caso = casos.find(c => c.id === casoId);
  if(!caso) return;

  modalMode = 'nueva-gestion';
  casoActivoId = casoId;
  modalTitle.textContent = `Registrar gestión — CASO #${caso.id}`;
  datosUsuarioFields.style.display = 'none';
  modalOverlay.classList.add('open');
}

function closeModal(){
  modalOverlay.classList.remove('open');
  casoForm.reset();
  datosUsuarioFields.style.display = 'block';
}

openModalBtn.addEventListener('click', openModalNuevoCaso);
closeModalBtn.addEventListener('click', closeModal);
cancelModalBtn.addEventListener('click', closeModal);
modalOverlay.addEventListener('click', (e) => { if(e.target === modalOverlay) closeModal(); });

saveCasoBtn.addEventListener('click', () => {
  const tipo = document.getElementById('gTipo').value;
  const detalle = document.getElementById('gDetalle').value.trim();
  const fecha = document.getElementById('gFecha').value;

  if(detalle === ''){
    Swal.fire({icon:'error', title:'Falta el detalle', text:'Describe la gestión realizada.', confirmButtonColor:'var(--red-primary)'});
    document.getElementById('gDetalle').focus();
    return;
  }
  if(fecha === ''){
    Swal.fire({icon:'error', title:'Falta la fecha', text:'Selecciona la fecha de la gestión.', confirmButtonColor:'var(--red-primary)'});
    document.getElementById('gFecha').focus();
    return;
  }

  const [year, month, day] = fecha.split('-');
  const fechaFormateada = `${day}/${month}/${year}`;

  if(modalMode === 'nuevo-caso'){
    const nombre = document.getElementById('uNombre').value.trim();
    const rut = document.getElementById('uRut').value.trim();
    const sector = document.getElementById('uSector').value.trim();
    const telefono = document.getElementById('uTelefono').value.trim() || '—';

    if(nombre === ''){
      Swal.fire({icon:'error', title:'Falta el nombre', text:'Ingresa el nombre completo del usuario.', confirmButtonColor:'var(--red-primary)'});
      document.getElementById('uNombre').focus();
      return;
    }
    if(rut === ''){
      Swal.fire({icon:'error', title:'Falta el RUT', text:'Ingresa el RUT del usuario.', confirmButtonColor:'var(--red-primary)'});
      document.getElementById('uRut').focus();
      return;
    }
    if(sector === ''){
      Swal.fire({icon:'error', title:'Falta el sector', text:'Ingresa el sector del usuario.', confirmButtonColor:'var(--red-primary)'});
      document.getElementById('uSector').focus();
      return;
    }

    casos.unshift({
      id: `CS-${nextCsId}`,
      nombre, rut, sector, telefono,
      expanded: true,
      gestiones: [{
        numero: 1, fecha: fechaFormateada, tipo, detalle,
        atendidoPor: 'J. Pérez', pendiente: false
      }]
    });
    nextCsId++;

  } else {
    const caso = casos.find(c => c.id === casoActivoId);
    if(!caso) return;

    const pendingIndex = caso.gestiones.findIndex(g => g.pendiente);
    if(pendingIndex !== -1){
      caso.gestiones[pendingIndex] = {
        ...caso.gestiones[pendingIndex],
        fecha: fechaFormateada, tipo, detalle,
        atendidoPor: 'J. Pérez', pendiente: false
      };
    } else if(caso.gestiones.length < 3){
      caso.gestiones.push({
        numero: caso.gestiones.length + 1,
        fecha: fechaFormateada, tipo, detalle,
        atendidoPor: 'J. Pérez', pendiente: false
      });
    }
    caso.expanded = true;
  }

  Swal.fire({icon:'success', title:'Gestión guardada', timer:1200, showConfirmButton:false});
  closeModal();
  renderCasos(buscarUsuario.value);
});

/* ---------- Init ---------- */
renderCasos('');
