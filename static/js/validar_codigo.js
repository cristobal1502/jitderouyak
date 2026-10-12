/* ============================================================
   validar_codigo.js — pantalla "Validar código".
   El código, su vigencia, los intentos fallidos y el reenvío los
   controla el servidor (login/views.py). Aquí solo se muestran
   los contadores y se traducen las respuestas a popups.
   ============================================================ */
const datos = document.body.dataset;
const URL_VALIDAR = datos.validarUrl;
const URL_REENVIAR = datos.reenviarUrl;
const MAX_INTENTOS = Number(datos.maxIntentos) || 3;
const COOLDOWN_REENVIO = 30;

const form = document.getElementById('codigoForm');
const codigoInput = document.getElementById('codigo');
const validarBtn = document.getElementById('validarBtn');
const reenviarBtn = document.getElementById('reenviarBtn');
const reenviarTimer = document.getElementById('reenviarTimer');
const vigenciaTexto = document.getElementById('vigenciaTexto');
const intentosRestantesEl = document.getElementById('intentosRestantes');
const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]').value;

// Estado inicial entregado por el servidor
let intentos = Number(datos.intentos);
let segundosVigencia = Number(datos.vigencia);
let segundosCooldown = Number(datos.cooldown);
let expirado = segundosVigencia <= 0;
let bloqueado = intentos <= 0;
let timerVigencia = null;
let timerCooldown = null;
let enviando = false;

const BTN = 'var(--red-primary)';

function fmt(seg){
  const m = String(Math.floor(seg / 60)).padStart(2, '0');
  const s = String(seg % 60).padStart(2, '0');
  return `${m}:${s}`;
}

function actualizarEstadoFormulario(){
  const deshabilitado = expirado || bloqueado;
  codigoInput.disabled = deshabilitado;
  validarBtn.disabled = deshabilitado;
}

function iniciarVigencia(){
  clearInterval(timerVigencia);
  if(segundosVigencia <= 0){
    expirado = true;
    vigenciaTexto.innerHTML = '<span class="expired">El código expiró</span>';
    actualizarEstadoFormulario();
    return;
  }
  expirado = false;
  vigenciaTexto.innerHTML = 'El código vence en <b id="vigenciaTimer">' + fmt(segundosVigencia) + '</b>';
  timerVigencia = setInterval(() => {
    segundosVigencia--;
    const el = document.getElementById('vigenciaTimer');
    if(segundosVigencia <= 0){
      clearInterval(timerVigencia);
      expirado = true;
      vigenciaTexto.innerHTML = '<span class="expired">El código expiró</span>';
      actualizarEstadoFormulario();
      mostrarAlerta('codigo_expirado');
      return;
    }
    if(el) el.textContent = fmt(segundosVigencia);
  }, 1000);
}

function iniciarCooldown(){
  clearInterval(timerCooldown);
  if(segundosCooldown <= 0){
    reenviarBtn.disabled = false;
    reenviarTimer.textContent = '';
    return;
  }
  reenviarBtn.disabled = true;
  reenviarTimer.textContent = `(${segundosCooldown}s)`;
  timerCooldown = setInterval(() => {
    segundosCooldown--;
    if(segundosCooldown <= 0){
      clearInterval(timerCooldown);
      reenviarBtn.disabled = false;
      reenviarTimer.textContent = '';
      return;
    }
    reenviarTimer.textContent = `(${segundosCooldown}s)`;
  }, 1000);
}

/**
 * Muestra el popup según el caso detectado al validar o reenviar el código.
 */
function mostrarAlerta(caso, extra){
  switch(caso){
    case 'codigo_vacio':
      Swal.fire({icon:'error', title:'Falta el código', text:'Ingresa el código de 6 dígitos que enviamos a tu correo.', confirmButtonColor: BTN});
      break;

    case 'codigo_formato':
      Swal.fire({icon:'error', title:'Código inválido', text:'El código debe tener exactamente 6 dígitos numéricos.', confirmButtonColor: BTN});
      break;

    case 'codigo_incorrecto':
      Swal.fire({
        icon:'error',
        title:'Código incorrecto',
        text:`El código no coincide. Te quedan ${extra} intento${extra === 1 ? '' : 's'}.`,
        confirmButtonColor: BTN
      });
      break;

    case 'intentos_agotados':
      Swal.fire({
        icon:'warning',
        title:'Intentos agotados',
        text:'Superaste el máximo de intentos fallidos. Solicita un nuevo código para continuar.',
        confirmButtonColor: BTN
      });
      break;

    case 'codigo_expirado':
      Swal.fire({
        icon:'warning',
        title:'Código expirado',
        text:'La vigencia del código terminó. Solicita uno nuevo para continuar.',
        confirmButtonColor: BTN
      });
      break;

    case 'espera':
      Swal.fire({icon:'info', title:'Espera un momento', text:`Podrás pedir otro código en ${extra} segundos.`, confirmButtonColor: BTN});
      break;

    case 'reenviado':
      Swal.fire({icon:'success', title:'Código reenviado', text:'Enviamos un nuevo código a tu correo. El anterior quedó sin efecto.', confirmButtonColor: BTN});
      break;

    case 'sesion_invalida':
      Swal.fire({icon:'warning', title:'Sesión de recuperación vencida', text:'Vuelve a solicitar el código desde el inicio.', confirmButtonColor: BTN})
        .then(() => { window.location.href = extra; });
      break;

    case 'sin_conexion':
      Swal.fire({icon:'error', title:'Sin conexión', text:'No pudimos comunicarnos con el servidor. Inténtalo de nuevo.', confirmButtonColor: BTN});
      break;

    case 'valido':
      Swal.fire({icon:'success', title:'Código verificado', text:'Ahora puedes crear tu nueva contraseña.', timer:1200, showConfirmButton:false});
      break;

    default:
      Swal.fire({icon:'error', title:'Ocurrió un problema', text:'No pudimos validar el código. Intenta nuevamente.', confirmButtonColor: BTN});
  }
}

async function enviarPost(url, cuerpo){
  let res;
  try {
    res = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrf, 'Accept': 'application/json' },
      body: cuerpo
    });
  } catch(e) {
    return { error: 'sin_conexion' };
  }
  try { return await res.json(); } catch(e) { return { error: 'error_servidor' }; }
}

function actualizarIntentos(n){
  intentos = n;
  intentosRestantesEl.textContent = n;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  if(enviando) return;
  codigoInput.classList.remove('field-invalid');

  const codigo = codigoInput.value.trim();

  if(codigo === ''){
    codigoInput.classList.add('field-invalid');
    mostrarAlerta('codigo_vacio');
    return;
  }
  if(!/^\d{6}$/.test(codigo)){
    codigoInput.classList.add('field-invalid');
    mostrarAlerta('codigo_formato');
    return;
  }

  enviando = true;
  const cuerpo = new FormData();
  cuerpo.append('codigo', codigo);
  const r = await enviarPost(URL_VALIDAR, cuerpo);
  enviando = false;

  if(r.ok){
    clearInterval(timerVigencia);
    mostrarAlerta('valido');
    setTimeout(() => { window.location.href = r.siguiente; }, 1200);
    return;
  }

  codigoInput.classList.add('field-invalid');
  codigoInput.value = '';

  switch(r.error){
    case 'codigo_incorrecto':
      actualizarIntentos(r.restantes);
      mostrarAlerta('codigo_incorrecto', r.restantes);
      codigoInput.focus();
      break;
    case 'intentos_agotados':
      actualizarIntentos(0);
      bloqueado = true;
      actualizarEstadoFormulario();
      mostrarAlerta('intentos_agotados');
      break;
    case 'codigo_expirado':
      clearInterval(timerVigencia);
      segundosVigencia = 0;
      iniciarVigencia();
      mostrarAlerta('codigo_expirado');
      break;
    case 'sesion_invalida':
      mostrarAlerta('sesion_invalida', r.redirect);
      break;
    case 'codigo_formato':
    case 'sin_conexion':
      mostrarAlerta(r.error);
      break;
    default:
      mostrarAlerta('error');
  }
});

reenviarBtn.addEventListener('click', async () => {
  reenviarBtn.disabled = true;
  const r = await enviarPost(URL_REENVIAR, new FormData());

  if(r.ok){
    // Un reenvío invalida el código anterior y reinicia vigencia, intentos y espera.
    actualizarIntentos(r.intentos);
    bloqueado = false;
    codigoInput.value = '';
    codigoInput.classList.remove('field-invalid');
    segundosVigencia = r.vigencia;
    segundosCooldown = r.cooldown;
    actualizarEstadoFormulario();
    iniciarVigencia();
    iniciarCooldown();
    mostrarAlerta('reenviado');
    return;
  }

  if(r.error === 'espera'){
    segundosCooldown = r.segundos;
    iniciarCooldown();
    mostrarAlerta('espera', r.segundos);
  } else if(r.error === 'sesion_invalida'){
    mostrarAlerta('sesion_invalida', r.redirect);
  } else {
    reenviarBtn.disabled = false;
    mostrarAlerta(r.error === 'sin_conexion' ? 'sin_conexion' : 'error');
  }
});

/* Solo dígitos mientras se escribe */
codigoInput.addEventListener('input', () => {
  codigoInput.value = codigoInput.value.replace(/\D/g, '').slice(0, 6);
});

actualizarEstadoFormulario();
iniciarVigencia();
iniciarCooldown();
if(!codigoInput.disabled) codigoInput.focus();
