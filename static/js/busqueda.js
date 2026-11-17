/* ============================================================
   busqueda.js — Búsqueda avanzada de atenciones (RF-032).
   Los filtros, la paginación y la exportación se resuelven en el
   servidor (api/busqueda/), respetando el alcance del rol.
   ============================================================ */
(() => {
  const BTN = 'var(--red-primary)';
  const API_BASE = document.body.dataset.api || '/api/';
  const IMPRIMIR_URL = document.body.dataset.imprimirUrl || '';

  const $ = (id) => document.getElementById(id);
  const resultsBody = $('resultsBody');
  const emptyState = $('emptyState');
  const resultsCount = $('resultsCount');
  const paginationInfo = $('paginationInfo');
  const paginationControls = $('paginationControls');

  const f = {
    delegacion: $('fDelegacion'), periodo: $('fPeriodo'), funcionario: $('fFuncionario'),
    tipo: $('fTipo'), sub: $('fSub'), clasificacion: $('fClasificacion'), item: $('fItem'), estado: $('fEstado'), desde: $('fFechaDesde'), hasta: $('fFechaHasta'), q: $('fPalabras')
  };
  const applyBtn = $('applyFiltersBtn');
  const clearBtn = $('clearFiltersBtn');
  const pdfBtn = $('exportPdfBtn');
  const excelBtn = $('exportExcelBtn');

  let subatenciones = [];
  let filtrosAplicados = {};   // los filtros de la última búsqueda (se usan al paginar y exportar)
  let paginaActual = 1;
  let cargando = false;

  /* ---------- Opciones de los filtros ---------- */
  function opciones(select, items, etiquetaTodos){
    select.innerHTML = `<option value="">${SGR.esc(etiquetaTodos)}</option>` +
      items.map(i => `<option value="${i.id}">${SGR.esc(i.nombre)}</option>`).join('');
  }

  function periodos(anios){
    const trimestres = [['01-01', '03-31'], ['04-01', '06-30'], ['07-01', '09-30'], ['10-01', '12-31']];
    let html = '<option value="">Todo el período</option>';
    anios.forEach(a => {
      html += `<option value="${a}-01-01|${a}-12-31">Año ${a}</option>`;
      for(let q = 3; q >= 0; q--){
        const [d, h] = trimestres[q];
        html += `<option value="${a}-${d}|${a}-${h}">Q${q + 1} ${a} (${d.slice(3)}/${d.slice(0, 2)} – ${h.slice(3)}/${h.slice(0, 2)})</option>`;
      }
    });
    f.periodo.innerHTML = html;
  }

  function opcionesSub(){
    const tipo = f.tipo.value;
    const visibles = tipo ? subatenciones.filter(s => String(s.tipoId) === tipo) : subatenciones;
    const actual = f.sub.value;
    opciones(f.sub, visibles, 'Todas las sub atenciones');
    if(visibles.some(s => String(s.id) === actual)) f.sub.value = actual;
  }

  f.tipo.addEventListener('change', opcionesSub);

  // El período rellena el rango de fechas; editar una fecha a mano lo deja en "personalizado".
  f.periodo.addEventListener('change', () => {
    const [desde, hasta] = f.periodo.value ? f.periodo.value.split('|') : ['', ''];
    f.desde.value = desde;
    f.hasta.value = hasta;
  });
  [f.desde, f.hasta].forEach(el => el.addEventListener('change', () => {
    const val = `${f.desde.value}|${f.hasta.value}`;
    f.periodo.value = [...f.periodo.options].some(o => o.value === val) ? val : '';
  }));

  /* ---------- Lectura de filtros ---------- */
  function leerFiltros(){
    const datos = {
      delegacion: f.delegacion.value, funcionario: f.funcionario.value, tipo: f.tipo.value,
      sub: f.sub.value, clasificacion: f.clasificacion.value, item: f.item.value, estado: f.estado.value, desde: f.desde.value, hasta: f.hasta.value, q: f.q.value.trim()
    };
    if(datos.desde && datos.hasta && datos.desde > datos.hasta){
      Swal.fire({ icon: 'warning', title: 'Rango de fechas inválido',
        text: 'La fecha "desde" no puede ser posterior a la fecha "hasta".', confirmButtonColor: BTN });
      return null;
    }
    return datos;
  }

  function query(filtros, extra){
    const p = new URLSearchParams();
    Object.entries({ ...filtros, ...(extra || {}) }).forEach(([k, v]) => { if(v !== '' && v != null) p.set(k, v); });
    return p.toString();
  }

  /* ---------- Errores ---------- */
  function mostrarError(err){
    if(SGR.alertaComun(err)) return;
    const textos = {
      fecha_invalida: ['Fecha inválida', 'Revisa el formato de las fechas del filtro.'],
      rango_invalido: ['Rango de fechas inválido', 'La fecha "desde" no puede ser posterior a la fecha "hasta".'],
      referencia_invalida: ['Filtro inválido', 'Uno de los filtros ya no existe. Se recargarán las opciones.'],
      sub_no_corresponde: ['Filtro inválido', 'La sub atención no corresponde al tipo de atención seleccionado.'],
      texto_largo: ['Búsqueda demasiado larga', 'Las palabras clave admiten hasta 100 caracteres.']
    };
    const [title, text] = textos[err && err.error] || ['No se pudo buscar', 'Ocurrió un problema al consultar los registros.'];
    Swal.fire({ icon: 'warning', title, text, confirmButtonColor: BTN });
    if(err && err.error === 'referencia_invalida') cargarOpciones();
  }

  /* ---------- Búsqueda ---------- */
  async function buscar(pagina){
    if(cargando) return;
    cargando = true;
    applyBtn.disabled = true;
    try {
      const r = await SGR.get('busqueda/?' + query(filtrosAplicados, { pagina }));
      paginaActual = r.pagina;
      render(r);
    } catch(err) {
      mostrarError(err);
    } finally {
      cargando = false;
      applyBtn.disabled = false;
    }
  }

  function aplicar(){
    const filtros = leerFiltros();
    if(!filtros) return;
    filtrosAplicados = filtros;
    buscar(1);
  }

  function limpiar(){
    Object.values(f).forEach(el => { el.value = ''; });
    opcionesSub();
    filtrosAplicados = {};
    buscar(1);
  }

  applyBtn.addEventListener('click', aplicar);
  clearBtn.addEventListener('click', limpiar);
  f.q.addEventListener('keydown', (e) => { if(e.key === 'Enter') aplicar(); });

  /* ---------- Render ---------- */
  function render(r){
    resultsCount.textContent = r.total;
    emptyState.style.display = r.total === 0 ? 'block' : 'none';

    resultsBody.innerHTML = r.resultados.map(a => `
      <tr>
        <td class="code-cell">${SGR.esc(a.codigo)}</td>
        <td>${SGR.formatearFecha(a.fecha)}</td>
        <td>${SGR.esc(a.responsableNombre)}</td>
        <td>${SGR.esc(a.delegacionNombre)}</td>
        <td>${SGR.esc(a.tipoNombre)}<br><span class="cell-sub">${SGR.esc(a.subNombre)}</span></td>
        <td>${SGR.esc(a.solicitante)}${a.telefono ? `<br><span class="cell-sub">${SGR.esc(a.telefono)}</span>` : ''}${
          a.clasificacion === 'Otra gestión' ? '<br><span class="tag-otra-gestion">Otra gestión</span>' : ''}</td>
        <td>${a.itemNombre ? SGR.esc(a.itemNombre) : '<span class="cell-sub">Sin ítem</span>'}<br>${
          a.estado !== 'Ejecutada' ? '<span class="cell-sub">En preparación</span>'
            : a.puntaje ? '<span class="puntaje-cell">+1 pto</span>' : '<span class="cell-sub">0 pts</span>'}</td>
        <td>${SGR.esc(a.descripcion)}</td>
      </tr>
    `).join('');

    const inicio = (r.pagina - 1) * r.porPagina;
    paginationInfo.textContent = r.total === 0
      ? 'Sin registros'
      : `Mostrando registros ${inicio + 1}-${inicio + r.resultados.length} de ${r.total}`;

    renderPaginacion(r.pagina, r.paginas);
  }

  function renderPaginacion(actual, total){
    // Ventana de páginas alrededor de la actual (1 … 4 5 [6] 7 8 … 20)
    const paginas = new Set([1, total]);
    for(let i = actual - 2; i <= actual + 2; i++) if(i >= 1 && i <= total) paginas.add(i);
    const lista = [...paginas].sort((a, b) => a - b);

    let html = `<button class="page-btn" data-page="${actual - 1}" ${actual === 1 ? 'disabled' : ''}>&lt; Anterior</button>`;
    lista.forEach((p, i) => {
      if(i > 0 && p - lista[i - 1] > 1) html += '<span class="page-gap">…</span>';
      html += `<button class="page-btn ${p === actual ? 'active' : ''}" data-page="${p}">${p}</button>`;
    });
    html += `<button class="page-btn" data-page="${actual + 1}" ${actual === total ? 'disabled' : ''}>Siguiente &gt;</button>`;
    paginationControls.innerHTML = html;
  }

  paginationControls.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-page]');
    if(!btn || btn.disabled) return;
    const pagina = parseInt(btn.dataset.page, 10);
    if(pagina !== paginaActual) buscar(pagina);
  });

  /* ---------- Exportación ---------- */
  function sinResultados(){
    if(resultsCount.textContent !== '0') return false;
    Swal.fire({ icon: 'info', title: 'Sin registros para exportar',
      text: 'Ajusta los filtros para obtener resultados antes de exportar.', confirmButtonColor: BTN });
    return true;
  }

  excelBtn.addEventListener('click', async () => {
    if(sinResultados()) return;
    excelBtn.disabled = true;
    try {
      const res = await fetch(API_BASE + 'busqueda/exportar/?' + query(filtrosAplicados),
        { credentials: 'same-origin' });
      if(!res.ok){
        let cuerpo = {};
        try { cuerpo = await res.json(); } catch(e) { /* sin JSON */ }
        throw { ...cuerpo, error: cuerpo.error || 'error_servidor', status: res.status };
      }
      const blob = await res.blob();
      const nombre = (/filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') || '') || [])[1]
        || 'busqueda_atenciones.xlsx';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = nombre;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch(err) {
      mostrarError(err && err.status !== undefined ? err : { error: 'sin_conexion' });
    } finally {
      excelBtn.disabled = false;
    }
  });

  pdfBtn.addEventListener('click', () => {
    if(sinResultados()) return;
    const ventana = window.open(IMPRIMIR_URL + '?' + query(filtrosAplicados), '_blank');
    if(!ventana){
      Swal.fire({ icon: 'warning', title: 'Ventana bloqueada',
        text: 'Permite las ventanas emergentes para generar el PDF.', confirmButtonColor: BTN });
    }
  });

  /* ---------- Init ---------- */
  async function cargarOpciones(){
    try {
      const op = await SGR.get('busqueda/opciones/');
      opciones(f.delegacion, op.delegaciones, op.delegaciones.length > 1 ? 'Todas mis delegaciones' : 'Todas');
      opciones(f.funcionario, op.funcionarios, 'Todos los funcionarios');
      opciones(f.tipo, op.tipos, 'Todos los tipos');
      f.clasificacion.innerHTML = '<option value="">Todas</option>' +
        op.clasificaciones.map(c => `<option value="${SGR.esc(c)}">${SGR.esc(c)}</option>`).join('');
      opciones(f.item, op.items, 'Todos los ítems');
      f.estado.innerHTML = '<option value="">Todos</option>' +
        op.estados.map(e => `<option value="${SGR.esc(e)}">${SGR.esc(e)}</option>`).join('');
      subatenciones = op.subatenciones;
      opcionesSub();
      periodos(op.anios);
      pdfBtn.hidden = !op.puedeExportar;
      excelBtn.hidden = !op.puedeExportar;
    } catch(err) {
      mostrarError(err);
    }
  }

  cargarOpciones().then(() => buscar(1));
})();
