const perfilForm = document.getElementById('perfilForm');
const passwordForm = document.getElementById('passwordForm');
const guardarPrefsBtn = document.getElementById('guardarPrefsBtn');

const pNombre = document.getElementById('pNombre');
const pCorreo = document.getElementById('pCorreo');
const pTelefono = document.getElementById('pTelefono');
const passActual = document.getElementById('passActual');
const passNueva = document.getElementById('passNueva');
const passConfirmar = document.getElementById('passConfirmar');

const BTN_COLOR = 'var(--red-primary)';

function alerta(icon, title, text, campo){
  Swal.fire({ icon, title, text, confirmButtonColor: BTN_COLOR });
  if(campo){
    campo.classList.add('field-invalid');
    campo.focus();
  }
}

/**
 * Valida el formulario de perfil según el caso detectado.
 */
function mostrarAlertaPerfil(caso){
  switch(caso){
    case 'nombre_vacio':
      alerta('error', 'Falta el nombre', 'Ingresa tu nombre completo.', pNombre);
      break;
    case 'correo_vacio':
      alerta('error', 'Falta el correo', 'Ingresa tu correo institucional.', pCorreo);
      break;
    case 'correo_invalido':
      alerta('error', 'Correo inválido', 'Ingresa un correo electrónico con formato válido.', pCorreo);
      break;
    case 'correo_duplicado':
      alerta('error', 'Correo en uso', 'Ya existe otra cuenta con ese correo.', pCorreo);
      break;
    case 'telefono_invalido':
      alerta('error', 'Teléfono inválido', 'Usa solo números, espacios y los símbolos + ( ) -.', pTelefono);
      break;
    case 'guardado':
      Swal.fire({ icon: 'success', title: 'Perfil actualizado', timer: 1300, showConfirmButton: false });
      break;
  }
}

/**
 * Valida el formulario de contraseña según el caso detectado.
 */
function mostrarAlertaPassword(caso){
  switch(caso){
    case 'actual_vacia':
      alerta('error', 'Falta la contraseña actual', 'Ingresa tu contraseña actual.', passActual);
      break;
    case 'nueva_corta':
      alerta('warning', 'Contraseña muy corta', 'La contraseña debe tener al menos 8 caracteres.', passNueva);
      break;
    case 'nueva_sin_mayuscula':
      alerta('warning', 'Falta una mayúscula', 'La contraseña debe incluir al menos una letra mayúscula.', passNueva);
      break;
    case 'nueva_sin_numero':
      alerta('warning', 'Falta un número', 'La contraseña debe incluir al menos un número.', passNueva);
      break;
    case 'nueva_sin_especial':
      alerta('warning', 'Falta un carácter especial', 'La contraseña debe incluir al menos un carácter especial (ej: ! @ # $ % &).', passNueva);
      break;
    case 'actual_incorrecta':
      alerta('error', 'Contraseña actual incorrecta', 'La contraseña actual no coincide. Verifícala e inténtalo nuevamente.', passActual);
      break;
    case 'igual_a_actual':
      alerta('warning', 'Contraseña repetida', 'La nueva contraseña debe ser distinta de la actual.', passNueva);
      break;
    case 'no_coinciden':
      alerta('error', 'Las contraseñas no coinciden', 'Verifica que ambos campos tengan la misma contraseña.', passConfirmar);
      break;
    case 'actualizada':
      Swal.fire({ icon: 'success', title: 'Contraseña actualizada', timer: 1300, showConfirmButton: false });
      break;
  }
}

function limpiarErrores(form){
  form.querySelectorAll('.field-invalid').forEach(el => el.classList.remove('field-invalid'));
}

/** Errores de la API que son propios de esta pantalla; el resto lo resuelve api.js. */
function manejarErrorPerfil(err){
  switch(err.error){
    case 'campo_vacio':
      return mostrarAlertaPerfil(err.campo === 'correo' ? 'correo_vacio' : 'nombre_vacio');
    case 'correo_invalido':
      return mostrarAlertaPerfil('correo_invalido');
    case 'duplicado':
      return mostrarAlertaPerfil('correo_duplicado');
    case 'telefono_invalido':
      return mostrarAlertaPerfil('telefono_invalido');
  }
  if(!SGR.alertaComun(err)){
    Swal.fire({ icon: 'error', title: 'No se pudo guardar', text: 'Inténtalo nuevamente.', confirmButtonColor: BTN_COLOR });
  }
}

function manejarErrorPassword(err){
  switch(err.error){
    case 'actual_vacia':
      return mostrarAlertaPassword('actual_vacia');
    case 'actual_incorrecta':
      return mostrarAlertaPassword('actual_incorrecta');
    case 'igual_a_actual':
      return mostrarAlertaPassword('igual_a_actual');
    case 'password_corto':
      return mostrarAlertaPassword('nueva_corta');
    case 'password_sin_mayuscula':
      return mostrarAlertaPassword('nueva_sin_mayuscula');
    case 'password_sin_numero':
      return mostrarAlertaPassword('nueva_sin_numero');
    case 'password_sin_especial':
      return mostrarAlertaPassword('nueva_sin_especial');
  }
  if(!SGR.alertaComun(err)){
    Swal.fire({ icon: 'error', title: 'No se pudo actualizar', text: 'Inténtalo nuevamente.', confirmButtonColor: BTN_COLOR });
  }
}

perfilForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  limpiarErrores(perfilForm);

  const nombre = pNombre.value.trim();
  const correo = pCorreo.value.trim();
  const correoPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if(nombre === ''){ mostrarAlertaPerfil('nombre_vacio'); return; }
  if(correo === ''){ mostrarAlertaPerfil('correo_vacio'); return; }
  if(!correoPattern.test(correo)){ mostrarAlertaPerfil('correo_invalido'); return; }

  try {
    const yo = await SGR.put('yo/', { nombre, correo, telefono: pTelefono.value.trim() });
    pNombre.value = yo.nombre;
    pCorreo.value = yo.correo;
    pTelefono.value = yo.telefono;
    document.querySelectorAll('.user-text .name').forEach((el) => { el.textContent = yo.nombre; });
    mostrarAlertaPerfil('guardado');
  } catch(err) {
    manejarErrorPerfil(err);
  }
});

passwordForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  limpiarErrores(passwordForm);

  const actual = passActual.value;
  const nueva = passNueva.value;
  const confirmar = passConfirmar.value;

  if(actual === ''){ mostrarAlertaPassword('actual_vacia'); return; }
  if(nueva.length < 8){ mostrarAlertaPassword('nueva_corta'); return; }
  if(!/[A-Z]/.test(nueva)){ mostrarAlertaPassword('nueva_sin_mayuscula'); return; }
  if(!/[0-9]/.test(nueva)){ mostrarAlertaPassword('nueva_sin_numero'); return; }
  if(!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(nueva)){ mostrarAlertaPassword('nueva_sin_especial'); return; }
  if(nueva === actual){ mostrarAlertaPassword('igual_a_actual'); return; }
  if(nueva !== confirmar){ mostrarAlertaPassword('no_coinciden'); return; }

  try {
    await SGR.post('yo/password/', { actual, nueva });
    mostrarAlertaPassword('actualizada');
    passwordForm.reset();
  } catch(err) {
    manejarErrorPassword(err);
  }
});

guardarPrefsBtn.addEventListener('click', async () => {
  try {
    await SGR.put('yo/', {
      prefVencidos: document.getElementById('prefVencidos').checked,
      prefEvidencias: document.getElementById('prefEvidencias').checked,
      prefResumen: document.getElementById('prefResumen').checked
    });
    Swal.fire({ icon: 'success', title: 'Preferencias guardadas', timer: 1300, showConfirmButton: false });
  } catch(err) {
    if(err.error === 'sin_perfil'){
      Swal.fire({ icon: 'info', title: 'Sin perfil asociado',
        text: 'Tu cuenta no tiene un perfil de rol, por lo que no guarda preferencias.', confirmButtonColor: BTN_COLOR });
    } else if(!SGR.alertaComun(err)){
      Swal.fire({ icon: 'error', title: 'No se pudo guardar', text: 'Inténtalo nuevamente.', confirmButtonColor: BTN_COLOR });
    }
  }
});
