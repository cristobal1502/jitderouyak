const loginForm = document.getElementById('loginForm');
const usuarioInput = document.getElementById('usuario');
const passwordInput = document.getElementById('password');
const togglePassword = document.getElementById('togglePassword');
const submitBtn = document.getElementById('submitBtn');

/**
 * Muestra un popup de SweetAlert2 según el "caso" detectado en la validación.
 * Cada case define: ícono, título y texto del popup.
 */
function mostrarAlerta(caso){
  switch(caso){
    case 'usuario_vacio':
      Swal.fire({
        icon: 'error',
        title: 'Falta el usuario',
        text: 'Ingresa tu usuario o tu correo institucional.',
        confirmButtonColor: 'var(--red-primary)'
      });
      usuarioInput.classList.add('field-invalid');
      break;

    case 'usuario_invalido':
      Swal.fire({
        icon: 'error',
        title: 'Usuario o correo inválido',
        text: 'Ingresa un correo con formato válido o un usuario de al menos 3 caracteres (letras, números, punto, guion).',
        confirmButtonColor: 'var(--red-primary)'
      });
      usuarioInput.classList.add('field-invalid');
      break;

    case 'password_vacio':
      Swal.fire({
        icon: 'error',
        title: 'Falta la contraseña',
        text: 'Ingresa tu contraseña.',
        confirmButtonColor: 'var(--red-primary)'
      });
      passwordInput.classList.add('field-invalid');
      break;

    case 'password_corto':
      Swal.fire({
        icon: 'warning',
        title: 'Contraseña muy corta',
        text: 'La contraseña debe tener al menos 8 caracteres.',
        confirmButtonColor: 'var(--red-primary)'
      });
      passwordInput.classList.add('field-invalid');
      break;

    case 'password_sin_mayuscula':
      Swal.fire({
        icon: 'warning',
        title: 'Falta una mayúscula',
        text: 'La contraseña debe incluir al menos una letra mayúscula.',
        confirmButtonColor: 'var(--red-primary)'
      });
      passwordInput.classList.add('field-invalid');
      break;

    case 'password_sin_numero':
      Swal.fire({
        icon: 'warning',
        title: 'Falta un número',
        text: 'La contraseña debe incluir al menos un número.',
        confirmButtonColor: 'var(--red-primary)'
      });
      passwordInput.classList.add('field-invalid');
      break;

    case 'password_sin_especial':
      Swal.fire({
        icon: 'warning',
        title: 'Falta un carácter especial',
        text: 'La contraseña debe incluir al menos un carácter especial (ej: ! @ # $ % &).',
        confirmButtonColor: 'var(--red-primary)'
      });
      passwordInput.classList.add('field-invalid');
      break;

    case 'credenciales_invalidas':
      Swal.fire({
        icon: 'error',
        title: 'No pudimos iniciar sesión',
        text: 'Usuario o contraseña incorrectos. Inténtalo nuevamente.',
        confirmButtonColor: 'var(--red-primary)'
      });
      usuarioInput.classList.add('field-invalid');
      passwordInput.classList.add('field-invalid');
      break;

    case 'usuario_inactivo':
      Swal.fire({
        icon: 'warning',
        title: 'Cuenta inactiva',
        text: 'Tu cuenta está desactivada. Contacta a un administrador del sistema.',
        confirmButtonColor: 'var(--red-primary)'
      });
      usuarioInput.classList.add('field-invalid');
      break;

    case 'bloqueado':
      Swal.fire({
        icon: 'error',
        title: 'Demasiados intentos',
        text: 'Superaste el máximo de intentos fallidos. Espera 15 minutos o recupera tu contraseña.',
        confirmButtonColor: 'var(--red-primary)'
      });
      break;

    case 'password_actualizada':
      Swal.fire({
        icon: 'success',
        title: 'Contraseña actualizada',
        text: 'Ya puedes iniciar sesión con tu nueva contraseña.',
        confirmButtonColor: 'var(--red-primary)'
      });
      break;

    case 'validando':
      Swal.fire({
        icon: 'success',
        title: 'Credenciales válidas',
        text: 'Iniciando sesión…',
        timer: 1200,
        showConfirmButton: false
      });
      break;

    default:
      Swal.fire({
        icon: 'error',
        title: 'Ocurrió un problema',
        text: 'No pudimos validar tus datos. Intenta nuevamente.',
        confirmButtonColor: 'var(--red-primary)'
      });
  }
}

function clearFieldErrors(){
  usuarioInput.classList.remove('field-invalid');
  passwordInput.classList.remove('field-invalid');
}

togglePassword.addEventListener('click', () => {
  const isPassword = passwordInput.type === 'password';
  passwordInput.type = isPassword ? 'text' : 'password';
  togglePassword.classList.toggle('active', isPassword);
});

loginForm.addEventListener('submit', (e) => {
  clearFieldErrors();

  const usuario = usuarioInput.value.trim();
  const password = passwordInput.value;
  const correoPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const usernamePattern = /^[a-zA-Z0-9._-]{3,}$/;

  // Validación secuencial: se detiene en el primer caso que falle.
  if(usuario === ''){
    e.preventDefault();
    mostrarAlerta('usuario_vacio');
    usuarioInput.focus();
    return;
  }
  if(!correoPattern.test(usuario) && !usernamePattern.test(usuario)){
    e.preventDefault();
    mostrarAlerta('usuario_invalido');
    usuarioInput.focus();
    return;
  }
  if(password === ''){
    e.preventDefault();
    mostrarAlerta('password_vacio');
    passwordInput.focus();
    return;
  }
  if(password.length < 8){
    e.preventDefault();
    mostrarAlerta('password_corto');
    passwordInput.focus();
    return;
  }
  if(!/[A-Z]/.test(password)){
    e.preventDefault();
    mostrarAlerta('password_sin_mayuscula');
    passwordInput.focus();
    return;
  }
  if(!/[0-9]/.test(password)){
    e.preventDefault();
    mostrarAlerta('password_sin_numero');
    passwordInput.focus();
    return;
  }
  if(!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password)){
    e.preventDefault();
    mostrarAlerta('password_sin_especial');
    passwordInput.focus();
    return;
  }

  // Todo válido en el cliente: el formulario se envía a Django (POST) y el servidor
  // comprueba las credenciales. Si fallan, la página vuelve con data-error y se muestra el popup.
  submitBtn.disabled = true;
  submitBtn.textContent = 'Ingresando…';
});

/* Mensajes que vienen del servidor (credenciales inválidas, cuenta inactiva, etc.) */
(function mostrarMensajeDelServidor(){
  const { error, aviso } = document.body.dataset;
  if(error){
    mostrarAlerta(error);
    passwordInput.value = '';
  } else if(aviso){
    mostrarAlerta(aviso);
  }
})();
