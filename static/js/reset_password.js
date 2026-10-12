const resetForm = document.getElementById('resetForm');
const password1Input = document.getElementById('password1');
const password2Input = document.getElementById('password2');
const toggleButtons = document.querySelectorAll('.toggle-visibility');

toggleButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    const targetId = btn.getAttribute('data-target');
    const input = document.getElementById(targetId);
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    btn.classList.toggle('active', isPassword);
  });
});

function mostrarAlertaReset(caso){
  switch(caso){
    case 'password_corto':
      Swal.fire({
        icon: 'warning',
        title: 'Contraseña muy corta',
        text: 'La contraseña debe tener al menos 8 caracteres.',
        confirmButtonColor: 'var(--red-primary)'
      });
      password1Input.classList.add('field-invalid');
      break;

    case 'password_sin_mayuscula':
      Swal.fire({
        icon: 'warning',
        title: 'Falta una mayúscula',
        text: 'La contraseña debe incluir al menos una letra mayúscula.',
        confirmButtonColor: 'var(--red-primary)'
      });
      password1Input.classList.add('field-invalid');
      break;

    case 'password_sin_numero':
      Swal.fire({
        icon: 'warning',
        title: 'Falta un número',
        text: 'La contraseña debe incluir al menos un número.',
        confirmButtonColor: 'var(--red-primary)'
      });
      password1Input.classList.add('field-invalid');
      break;

    case 'password_sin_especial':
      Swal.fire({
        icon: 'warning',
        title: 'Falta un carácter especial',
        text: 'La contraseña debe incluir al menos un carácter especial (ej: ! @ # $ % &).',
        confirmButtonColor: 'var(--red-primary)'
      });
      password1Input.classList.add('field-invalid');
      break;

    case 'no_coinciden':
      Swal.fire({
        icon: 'error',
        title: 'Las contraseñas no coinciden',
        text: 'Verifica que ambos campos tengan la misma contraseña.',
        confirmButtonColor: 'var(--red-primary)'
      });
      password1Input.classList.add('field-invalid');
      password2Input.classList.add('field-invalid');
      break;
  }
}

if(resetForm){
  resetForm.addEventListener('submit', (e) => {
    password1Input.classList.remove('field-invalid');
    password2Input.classList.remove('field-invalid');

    const password1 = password1Input.value;
    const password2 = password2Input.value;

    if(password1.length < 8){
      e.preventDefault();
      mostrarAlertaReset('password_corto');
      password1Input.focus();
      return;
    }
    if(!/[A-Z]/.test(password1)){
      e.preventDefault();
      mostrarAlertaReset('password_sin_mayuscula');
      password1Input.focus();
      return;
    }
    if(!/[0-9]/.test(password1)){
      e.preventDefault();
      mostrarAlertaReset('password_sin_numero');
      password1Input.focus();
      return;
    }
    if(!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password1)){
      e.preventDefault();
      mostrarAlertaReset('password_sin_especial');
      password1Input.focus();
      return;
    }
    if(password1 !== password2){
      e.preventDefault();
      mostrarAlertaReset('no_coinciden');
      password2Input.focus();
      return;
    }
    // Si pasa todo, el form sigue su envío normal (POST a Django).
  });
}
