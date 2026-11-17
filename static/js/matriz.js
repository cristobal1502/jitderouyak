/* ============================================================
   matriz.js — Vista de equipo de la Matriz SGR.
   Muestra el avance grupal por ítem y por funcionario (semáforo),
   y permite al Delegado registrar ausencias y felicitaciones.
   ============================================================ */
(() => {
  const BTN = 'var(--red-primary)';
  const esc = SGR.esc;
  const $ = (id) => document.getElementById(id);

  const fDelegacion = $('mDelegacion');
  const fMes = $('mMes');
  const ausenciaBtn = $('ausenciaBtn');
  const felicitacionBtn = $('felicitacionBtn');

  let datos = null;

  const hoy = () => new Date().toLocaleDateString('en-CA');
  const SEM_TXT = { verde: 'Verde', amarillo: 'Amarillo', rojo: 'Rojo' };
  const sem = (s, txt) => `<span class="sem ${s}">${esc(txt)}</span>`;
  const ancho = (pct) => Math.min(100, Math.round(pct / 120 * 100));  // la barra llega hasta 120%

  /* ---------- Carga ---------- */
  async function cargar(){
    const p = new URLSearchParams();
    const delegacion = fDelegacion.value || SGR.delegacionActiva();  // la primera vez: la elegida arriba
    if(delegacion) p.set('delegacion', delegacion);
    if(fMes.value) p.set('mes', fMes.value);
    try {
      datos = await SGR.get('matriz/?' + p.toString());
    } catch(err) {
      if(err.error === 'sin_delegacion'){
        Swal.fire({ icon: 'info', title: 'Sin delegación', text: 'Tu usuario no tiene delegaciones asignadas.', confirmButtonColor: BTN });
        return;
      }
      if(!SGR.alertaComun(err)) Swal.fire({ icon: 'error', title: 'No se pudo cargar la matriz', confirmButtonColor: BTN });
      return;
    }
    render();
  }

  function render(){
    if(!fDelegacion.options.length){
      fDelegacion.innerHTML = datos.delegaciones.map((d) => `<option value="${d.id}">${esc(d.nombre)}</option>`).join('');
    }
    fDelegacion.value = String(datos.delegacion.id);
    fMes.value = datos.mes;
    ausenciaBtn.hidden = felicitacionBtn.hidden = !datos.puedeGestionar;

    const g = datos.grupo;
    $('kAvance').innerHTML = sem(g.semaforo, `${g.cumplimiento}%`);
    $('kPuntos').textContent = `${g.puntos} / ${g.meta}`;
    $('kSemaforo').innerHTML = ['verde', 'amarillo', 'rojo']
      .map((c) => `${sem(c, String(g.conteo[c]))}`).join(' ');
    $('kEquilibrio').innerHTML = datos.equipo.length
      ? `${g.equilibrado ? 'Equilibrado' : 'Desbalanceado'}<div class="nota-equilibrio">Brecha entre funcionarios: ${g.brecha} puntos porcentuales</div>`
      : '—';

    // Avance por ítem
    $('itemsEquipo').innerHTML = datos.items.length ? datos.items.map((i) => `
      <div class="goal-row">
        <div class="goal-top"><span class="goal-name">${esc(i.item)}</span>
          <span class="goal-figures"><b>${i.puntos}</b> / ${i.meta} pts · ${sem(i.semaforo, i.cumplimiento + '%')}</span></div>
        <div class="meta-track"><div class="meta-fill ${i.semaforo}" style="width:${ancho(i.cumplimiento)}%"></div></div>
        <div class="meta-escala"><span>0%</span><span>100%</span><span>${datos.tope}%</span></div>
      </div>`).join('') : '<div class="empty-state">No hay ítems activos. Créalos en Administración → Ítems y metas.</div>';

    // Tabla por funcionario
    $('equipoHead').innerHTML = '<tr><th>Funcionario</th>' +
      datos.items.map((i) => `<th>${esc(i.item)}</th>`).join('') +
      '<th>Total</th><th>Disponibilidad</th></tr>';
    $('equipoBody').innerHTML = datos.equipo.map((m) => `
      <tr>
        <td class="funcionario">${esc(m.nombre)}<small>${esc(m.cargo)}</small>
          ${m.ausenteHoy ? '<span class="chip-ausente">Ausente hoy</span>' : ''}
          ${m.felicitaciones ? `<span class="chip">★ ${m.felicitaciones} felicitación${m.felicitaciones === 1 ? '' : 'es'}</span>` : ''}</td>
        ${m.items.map((c) => `<td class="celda-item">${sem(c.semaforo, c.cumplimiento + '%')}
          <small>${c.puntos} / ${c.meta}${c.enTope ? ' · tope' : ''}</small></td>`).join('')}
        <td class="celda-item">${sem(m.semaforo, m.cumplimiento + '%')}<small>${m.puntos} / ${m.meta}</small></td>
        <td class="celda-item">${m.disponibilidad}%<small>${m.diasAusente} día${m.diasAusente === 1 ? '' : 's'} ausente</small></td>
      </tr>`).join('');
    $('equipoVacio').style.display = datos.equipo.length ? 'none' : 'block';

    // Ausencias
    $('listaAusencias').innerHTML = datos.ausencias.length ? datos.ausencias.map((a) => `
      <li>
        <div class="linea1"><span>${esc(a.funcionario)}</span><span>${esc(a.tipo)}</span></div>
        <div class="linea3">${SGR.formatearFecha(a.desde)} – ${SGR.formatearFecha(a.hasta)}${a.observacion ? ' · ' + esc(a.observacion) : ''}</div>
        ${datos.puedeGestionar ? `<button type="button" class="btn-table danger" data-borrar-ausencia="${a.id}" style="margin-top:8px;">Eliminar</button>` : ''}
      </li>`).join('') : '<li class="vacio">Sin ausencias registradas en el mes.</li>';

    // Felicitaciones
    $('listaFelicitaciones').innerHTML = datos.felicitaciones.length ? datos.felicitaciones.map((f) => `
      <li>
        <div class="linea1"><span>${esc(f.funcionario)}</span><span>${SGR.formatearFecha(f.fecha)}</span></div>
        <div class="linea2">${esc(f.motivo)} — <i>${esc(f.emisor)}</i></div>
        <div class="linea3">Respaldo: ${esc(f.respaldoTipo)} · ${esc(f.respaldoReferencia)}</div>
      </li>`).join('') : '<li class="vacio">Sin felicitaciones registradas en el mes.</li>';
  }

  fDelegacion.addEventListener('change', cargar);
  fMes.addEventListener('change', cargar);

  /* ---------- Errores de los formularios ---------- */
  const TEXTOS = {
    campo_vacio: ['Faltan datos', 'Completa todos los campos obligatorios.'],
    fecha_invalida: ['Fecha inválida', 'Revisa las fechas ingresadas.'],
    fecha_futura: ['Fecha no válida', 'La fecha no puede ser posterior a hoy.'],
    rango_invalido: ['Rango inválido', 'La fecha "hasta" debe ser igual o posterior a "desde" (máximo un año).'],
    ausencia_traslapada: ['Ausencia repetida', 'Ese funcionario ya tiene una ausencia registrada que se cruza con esas fechas.'],
    respaldo_informal: ['Respaldo no válido', 'La felicitación necesita un respaldo formal (carta, correo formal, oficio o libro). Los mensajes por WhatsApp, chat o redes sociales no valen.'],
    solo_delegado: ['Solo el Delegado', 'Únicamente el Delegado puede registrar ausencias y felicitaciones.'],
    referencia_invalida: ['Dato no válido', 'Revisa el funcionario y las opciones elegidas.'],
    texto_largo: ['Texto demasiado largo', 'Acorta el texto ingresado.']
  };
  function errorFormulario(err){
    if(err.error === 'prohibido' || err.error === 'no_autenticado' || err.error === 'sin_conexion'){
      if(SGR.alertaComun(err)) return;
    }
    const [title, text] = TEXTOS[err.error] || ['No se pudo guardar', 'Revisa los datos e inténtalo nuevamente.'];
    Swal.fire({ icon: 'warning', title, text, confirmButtonColor: BTN });
  }

  const opcionesEquipo = () => datos.equipo.map((m) => `<option value="${m.id}">${esc(m.nombre)}</option>`).join('');
  const opcionesLista = (lista) => lista.map((x) => `<option>${esc(x)}</option>`).join('');
  const campo = (label, control) => `<div class="field" style="text-align:left;"><label>${label}</label>${control}</div>`;

  // Valida el formulario del popup con las mismas reglas en vivo; si falla, el popup no se cierra.
  function formularioInvalido(){
    const malo = SGRValidar.validarTodo(Swal.getHtmlContainer());
    if(!malo) return false;
    Swal.showValidationMessage('Revisa los campos marcados en rojo.');
    malo.focus();
    return true;
  }

  /* ---------- Ausencias (solo Delegado) ---------- */
  ausenciaBtn.addEventListener('click', async () => {
    const res = await Swal.fire({
      title: 'Registrar ausencia', width: 640, customClass: { popup: 'swal-form' },
      html: '<div class="field-group-2">' +
        campo('Funcionario *', `<select id="sFun">${opcionesEquipo()}</select>`) +
        campo('Tipo *', `<select id="sTipo">${opcionesLista(datos.tiposAusencia)}</select>`) + '</div>' +
        '<div class="field-group-2">' +
        campo('Desde *', `<input type="date" id="sDesde" value="${hoy()}" data-requerido>`) +
        campo('Hasta *', `<input type="date" id="sHasta" value="${hoy()}" data-requerido>`) + '</div>' +
        campo('Observación', '<input type="text" id="sObs" maxlength="200" placeholder="Opcional">') +
        '<p class="field-hint" style="text-align:left;">La meta del funcionario se rebaja en proporción a los días hábiles ausentes.</p>',
      showCancelButton: true, confirmButtonText: 'Guardar', cancelButtonText: 'Cancelar', confirmButtonColor: BTN,
      preConfirm: () => (formularioInvalido() ? false : {
        delegacionId: datos.delegacion.id, funcionarioId: Number($('sFun').value), tipo: $('sTipo').value,
        desde: $('sDesde').value, hasta: $('sHasta').value, observacion: $('sObs').value.trim()
      })
    });
    if(!res.isConfirmed) return;
    try {
      await SGR.post('ausencias/', res.value);
      await cargar();
      Swal.fire({ icon: 'success', title: 'Ausencia registrada', text: 'La meta del mes se ajustó automáticamente.', timer: 1800, showConfirmButton: false });
    } catch(err) { errorFormulario(err); }
  });

  $('listaAusencias').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-borrar-ausencia]');
    if(!btn) return;
    const ok = await Swal.fire({ icon: 'warning', title: '¿Eliminar la ausencia?', text: 'La meta del funcionario volverá a calcularse.',
      showCancelButton: true, confirmButtonText: 'Eliminar', cancelButtonText: 'Cancelar', confirmButtonColor: BTN });
    if(!ok.isConfirmed) return;
    try {
      await SGR.eliminar('ausencias', Number(btn.dataset.borrarAusencia));
      await cargar();
    } catch(err) { errorFormulario(err); }
  });

  /* ---------- Felicitaciones (solo Delegado, con respaldo formal) ---------- */
  felicitacionBtn.addEventListener('click', async () => {
    const res = await Swal.fire({
      title: 'Registrar felicitación', width: 640, customClass: { popup: 'swal-form' },
      html: '<div class="field-group-2">' +
        campo('Funcionario felicitado *', `<select id="sFun">${opcionesEquipo()}</select>`) +
        campo('Fecha *', `<input type="date" id="sFecha" value="${hoy()}" max="${hoy()}">`) + '</div>' +
        campo('Quién felicita *', '<input type="text" id="sEmisor" maxlength="150" placeholder="Vecino(a), junta de vecinos, institución…" data-validar="nombre" data-requerido>') +
        campo('Motivo *', '<textarea id="sMotivo" rows="2" placeholder="Qué destacó del funcionario" data-validar="texto:10" data-requerido></textarea>') +
        '<div class="field-group-2">' +
        campo('Tipo de respaldo *', `<select id="sResp">${opcionesLista(datos.tiposRespaldo)}</select>`) +
        campo('Referencia del respaldo *', '<input type="text" id="sRef" maxlength="120" placeholder="Folio, N° de oficio, fecha…" data-validar="texto:4" data-requerido>') + '</div>' +
        '<p class="field-hint" style="text-align:left;">No valen mensajes informales por WhatsApp, chat o redes sociales.</p>',
      showCancelButton: true, confirmButtonText: 'Guardar', cancelButtonText: 'Cancelar', confirmButtonColor: BTN,
      preConfirm: () => (formularioInvalido() ? false : {
        delegacionId: datos.delegacion.id, funcionarioId: Number($('sFun').value), fecha: $('sFecha').value,
        emisor: $('sEmisor').value.trim(), motivo: $('sMotivo').value.trim(),
        respaldoTipo: $('sResp').value, respaldoReferencia: $('sRef').value.trim()
      })
    });
    if(!res.isConfirmed) return;
    try {
      await SGR.post('felicitaciones/', res.value);
      await cargar();
      Swal.fire({ icon: 'success', title: 'Felicitación registrada', timer: 1500, showConfirmButton: false });
    } catch(err) { errorFormulario(err); }
  });

  /* ---------- Init ---------- */
  cargar();
})();
