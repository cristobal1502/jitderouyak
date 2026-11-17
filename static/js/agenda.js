/* ============================================================
   agenda.js — Tubo de trabajo (agenda colectiva).
   Cada atención ingresada entra al tubo. Dos vistas:
     · Lista: tabla con un selector de etapa por fila.
     · Tablero: columnas por etapa; las tarjetas se arrastran.
   Llevar una actividad a «Realizado» la marca como ejecutada en el
   servidor (y suma su punto si corresponde). «Vencido» no es una
   etapa que se elija: es una actividad no realizada con el plazo pasado.
   ============================================================ */
(() => {
  const BTN = 'var(--red-primary)';
  const esc = SGR.esc;
  const $ = (id) => document.getElementById(id);
  const ETAPAS = ['Ingresado', 'Pendiente', 'En proceso', 'Realizado'];
  const CLAVE_VISTA = 'sgr.tubo.vista';

  const f = { delegacion: $('filtroDelegacion'), responsable: $('filtroResponsable'), etapa: $('filtroEtapa'), texto: $('filtroTexto') };
  let datos = { actividades: [], conteo: {}, puedeMover: false };
  let vista = 'lista';
  let opcionesListas = false;

  const hoy = () => new Date().toLocaleDateString('en-CA');
  const claseEtapa = (a) => a.vencido ? 'vencido'
    : ({ 'Realizado': 'realizado', 'En proceso': 'en-proceso', 'Pendiente': 'pendiente' })[a.etapa] || 'aprobada';
  const quien = (a) => a.organizacionNombre
    ? `${esc(a.organizacionNombre)}<span class="due-note">por ${esc(a.solicitante)}</span>`
    : esc(a.solicitante);
  const plazo = (a) => a.fechaCompromiso
    ? `<span class="${a.vencido ? 'due-note vencido' : 'due-note'}">${a.vencido ? 'Venció ' : 'Hasta '}${SGR.formatearFecha(a.fechaCompromiso)}</span>`
    : '<span class="due-note">Sin plazo</span>';
  const puntaje = (a) => a.etapa === 'Realizado'
    ? (a.puntaje ? '<span class="puntaje-cell">+1 pto</span>' : '<span class="due-note">0 pts</span>') : '';

  /* ---------- Carga ---------- */
  async function cargar(){
    const p = new URLSearchParams();
    if(f.delegacion.value) p.set('delegacion', f.delegacion.value);
    if(f.responsable.value) p.set('responsable', f.responsable.value);
    if(f.etapa.value) p.set('etapa', f.etapa.value);
    if(f.texto.value.trim()) p.set('q', f.texto.value.trim());
    try {
      datos = await SGR.get('tubo/?' + p.toString());
    } catch(err) {
      if(!SGR.alertaComun(err)) Swal.fire({ icon: 'error', title: 'No se pudo cargar el tubo', confirmButtonColor: BTN });
      return;
    }
    if(!opcionesListas){
      f.delegacion.innerHTML = '<option value="">Todas</option>' +
        datos.delegaciones.map((d) => `<option value="${d.id}">${esc(d.nombre)}</option>`).join('');
      f.responsable.innerHTML = '<option value="">Todos</option>' +
        datos.responsables.map((r) => `<option value="${r.id}">${esc(r.nombre)}</option>`).join('');
      const activa = SGR.delegacionActiva();
      opcionesListas = true;
      if(activa && datos.delegaciones.some((d) => d.id === activa)){
        f.delegacion.value = String(activa);
        return cargar();  // vuelve a pedir con la delegación de la barra superior
      }
    }
    render();
  }

  function render(){
    const c = datos.conteo;
    $('cTotal').textContent = c.Total || 0;
    $('cIngresado').textContent = c['Ingresado'] || 0;
    $('cPendiente').textContent = c['Pendiente'] || 0;
    $('cEnProceso').textContent = c['En proceso'] || 0;
    $('cRealizado').textContent = c['Realizado'] || 0;
    $('cVencido').textContent = c['Vencido'] || 0;
    document.querySelectorAll('#resumen .summary-cell').forEach((b) =>
      b.classList.toggle('activo', b.dataset.etapa === f.etapa.value));
    $('emptyState').style.display = datos.actividades.length ? 'none' : 'block';
    $('tableroAyuda').hidden = !datos.puedeMover;
    renderLista();
    renderTablero();
  }

  /* ---------- Vista lista ---------- */
  function selectorEtapa(a){
    if(!datos.puedeMover || a.etapa === 'Realizado'){
      return `<span class="badge ${claseEtapa(a)}"><span class="dot"></span>${a.vencido ? `Vencido · ${esc(a.etapa)}` : esc(a.etapa)}</span> ${puntaje(a)}`;
    }
    return `<select class="etapa-select ${a.vencido ? 'vencido' : ''}" data-mover="${a.id}" aria-label="Etapa de ${esc(a.codigo)}">
      ${ETAPAS.map((e) => `<option ${e === a.etapa ? 'selected' : ''}>${e}</option>`).join('')}
    </select>${a.vencido ? '<span class="due-note vencido">Plazo vencido</span>' : ''}`;
  }

  function renderLista(){
    $('listaBody').innerHTML = datos.actividades.map((a) => `
      <tr>
        <td class="code-cell">${esc(a.codigo)}</td>
        <td>${quien(a)}${a.clasificacion === 'Otra gestión' ? '<br><span class="tag-otra-gestion">Otra gestión</span>' : ''}</td>
        <td>${esc(a.tipoNombre)} · ${esc(a.subNombre)}<span class="due-note">${esc(a.itemNombre || 'Sin ítem')} · ${esc(a.delegacionNombre)}</span></td>
        <td>${esc(a.responsableNombre)}</td>
        <td>${plazo(a)}</td>
        <td>${selectorEtapa(a)}</td>
      </tr>`).join('');
  }

  $('listaBody').addEventListener('change', (e) => {
    const sel = e.target.closest('[data-mover]');
    if(!sel) return;
    const a = datos.actividades.find((x) => x.id === Number(sel.dataset.mover));
    mover(a, sel.value).then((ok) => { if(!ok) sel.value = a.etapa; });
  });

  /* ---------- Vista tablero (canvas) ---------- */
  const COLUMNAS = [...ETAPAS, 'Vencido'];
  const enColumna = (a, col) => col === 'Vencido' ? a.vencido : (!a.vencido && a.etapa === col);

  function tarjeta(a){
    const arrastrable = datos.puedeMover && a.etapa !== 'Realizado';
    return `<article class="tarjeta ${a.vencido ? 'vencida' : ''}" data-id="${a.id}" ${arrastrable ? 'draggable="true" tabindex="0"' : ''}
        aria-label="${esc(a.codigo)}, ${esc(a.etapa)}">
      <div class="tarjeta-top"><span class="code-cell">${esc(a.codigo)}</span>${puntaje(a)}</div>
      <div class="tarjeta-quien">${quien(a)}</div>
      <div class="tarjeta-que">${esc(a.tipoNombre)} · ${esc(a.subNombre)}</div>
      <div class="tarjeta-pie"><span>${esc(a.responsableNombre)}</span>${plazo(a)}</div>
      ${a.vencido ? `<div class="tarjeta-etapa">Etapa: ${esc(a.etapa)}</div>` : ''}
      ${arrastrable ? `<select class="tarjeta-mover" data-mover="${a.id}" aria-label="Mover ${esc(a.codigo)} a otra etapa">
          <option value="">Mover a…</option>${ETAPAS.filter((e) => e !== a.etapa).map((e) => `<option>${e}</option>`).join('')}
        </select>` : ''}
    </article>`;
  }

  function renderTablero(){
    $('tablero').innerHTML = COLUMNAS.map((col) => {
      const lista = datos.actividades.filter((a) => enColumna(a, col));
      return `<section class="columna ${col === 'Vencido' ? 'columna-vencida' : ''}" data-columna="${col}">
        <header><h3>${col === 'Vencido' ? 'Vencidas' : col}</h3><span class="contador">${lista.length}</span></header>
        ${col === 'Vencido' ? '<p class="columna-nota">Plazo pasado y sin realizar</p>' : ''}
        <div class="columna-cuerpo" data-soltar="${col === 'Vencido' ? '' : col}">
          ${lista.map(tarjeta).join('') || '<p class="columna-vacia">Sin actividades</p>'}
        </div>
      </section>`;
    }).join('');
  }

  // Arrastrar y soltar
  let arrastrando = null;
  $('tablero').addEventListener('dragstart', (e) => {
    const t = e.target.closest('.tarjeta[draggable="true"]');
    if(!t) return;
    arrastrando = Number(t.dataset.id);
    t.classList.add('arrastrando');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', t.dataset.id);
  });
  $('tablero').addEventListener('dragend', (e) => {
    const t = e.target.closest('.tarjeta');
    if(t) t.classList.remove('arrastrando');
    document.querySelectorAll('.columna-cuerpo.sobre').forEach((c) => c.classList.remove('sobre'));
    arrastrando = null;
  });
  $('tablero').addEventListener('dragover', (e) => {
    const cuerpo = e.target.closest('.columna-cuerpo');
    if(!cuerpo || !arrastrando || !cuerpo.dataset.soltar) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    document.querySelectorAll('.columna-cuerpo.sobre').forEach((c) => c !== cuerpo && c.classList.remove('sobre'));
    cuerpo.classList.add('sobre');
  });
  $('tablero').addEventListener('drop', (e) => {
    const cuerpo = e.target.closest('.columna-cuerpo');
    if(!cuerpo || !cuerpo.dataset.soltar) return;
    e.preventDefault();
    cuerpo.classList.remove('sobre');
    const a = datos.actividades.find((x) => x.id === arrastrando);
    if(a && a.etapa !== cuerpo.dataset.soltar) mover(a, cuerpo.dataset.soltar);
  });
  // Alternativa sin mouse: el selector «Mover a…» de cada tarjeta
  $('tablero').addEventListener('change', (e) => {
    const sel = e.target.closest('[data-mover]');
    if(!sel || !sel.value) return;
    const a = datos.actividades.find((x) => x.id === Number(sel.dataset.mover));
    mover(a, sel.value).then((ok) => { if(!ok) sel.value = ''; });
  });

  /* ---------- Mover de etapa ---------- */
  async function mover(a, etapa){
    if(!a || etapa === a.etapa) return false;
    const cuerpo = { etapa };
    if(etapa === 'Realizado'){
      const res = await Swal.fire({
        icon: 'question', title: `¿${a.codigo} quedó realizada?`,
        html: '<p>Pasará a ejecutada y, si corresponde, sumará 1 punto. Ya no se podrá devolver a otra etapa.</p>' +
          `<label style="display:block;margin-top:12px;font-size:13px;">Fecha en que se realizó
           <input type="date" id="fechaRealizada" class="swal2-input" value="${hoy()}" min="${a.fecha}" max="${hoy()}"></label>`,
        showCancelButton: true, confirmButtonText: 'Marcar realizada', cancelButtonText: 'Cancelar', confirmButtonColor: BTN,
        preConfirm: () => document.getElementById('fechaRealizada').value
      });
      if(!res.isConfirmed) return false;
      cuerpo.fecha = res.value || hoy();
    }
    try {
      const r = await SGR.post(`atenciones/${a.id}/etapa/`, cuerpo);
      await cargar();
      if(r.alerta){
        Swal.fire({ icon: 'warning', title: `«${r.alerta.item}» ya está en ${r.alerta.cumplimiento}%`,
          html: `<p><b>${esc(r.codigo)}</b> quedó realizada, pero no suma puntaje: el ítem superó el tope de 120% del ${esc(r.alerta.trimestre)}.</p>` +
            (r.alerta.sugeridos.length ? `<p style="margin-top:8px;">Enfócate en: ${r.alerta.sugeridos.map((x) => `${esc(x.item)} (${x.cumplimiento}%)`).join(', ')}</p>` : ''),
          confirmButtonColor: BTN });
      } else if(etapa === 'Realizado'){
        Swal.fire({ icon: 'success', title: 'Actividad realizada',
          text: r.puntaje ? `${r.codigo} sumó 1 punto.` : `${r.codigo} quedó realizada sin puntaje (otra gestión, sin teléfono o sin ítem).`,
          timer: 2200, showConfirmButton: false });
      }
      return true;
    } catch(err) {
      const textos = {
        semana_cerrada: ['Semana cerrada', 'Esa fecha pertenece a una semana que ya se cerró: usa una fecha de esta semana.'],
        ejecucion_anterior: ['Fecha no válida', 'La fecha de realización no puede ser anterior a la fecha de la actividad.'],
        fecha_futura: ['Fecha no válida', 'La fecha de realización no puede ser posterior a hoy.'],
        ya_realizada: ['Ya está realizada', 'Una actividad realizada no se puede devolver a otra etapa.']
      };
      if(textos[err.error]){
        const [title, text] = textos[err.error];
        Swal.fire({ icon: 'warning', title, text, confirmButtonColor: BTN });
        cargar();
      } else if(!SGR.alertaComun(err)){
        Swal.fire({ icon: 'error', title: 'No se pudo mover la actividad', confirmButtonColor: BTN });
      }
      return false;
    }
  }

  /* ---------- Filtros y vista ---------- */
  ['delegacion', 'responsable', 'etapa'].forEach((k) => f[k].addEventListener('change', cargar));
  let espera;
  f.texto.addEventListener('input', () => { clearTimeout(espera); espera = setTimeout(cargar, 300); });
  $('resumen').addEventListener('click', (e) => {
    const b = e.target.closest('[data-etapa]');
    if(!b) return;
    f.etapa.value = f.etapa.value === b.dataset.etapa ? '' : b.dataset.etapa;
    cargar();
  });

  function ponerVista(v){
    vista = v === 'tablero' ? 'tablero' : 'lista';
    $('vistaLista').hidden = vista !== 'lista';
    $('vistaTablero').hidden = vista !== 'tablero';
    document.querySelectorAll('.vista-btn').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.vista === vista)));
    try { localStorage.setItem(CLAVE_VISTA, vista); } catch(e) { /* sin almacenamiento */ }
  }
  document.querySelectorAll('.vista-btn').forEach((b) => b.addEventListener('click', () => ponerVista(b.dataset.vista)));
  let guardada = 'lista';
  try { guardada = localStorage.getItem(CLAVE_VISTA) || 'lista'; } catch(e) { /* sin almacenamiento */ }
  ponerVista(guardada);

  cargar();
})();
