const forgotForm = document.getElementById('forgotForm');
const emailInput = document.getElementById('email');

function mostrarAlertaForgot(caso){
  switch(caso){
    case 'email_vacio':
      Swal.fire({
        icon: 'error',
        title: 'Falta el correo',
        text: 'Ingresa tu correo institucional.',
        confirmButtonColor: 'var(--red-primary)'
      });
      emailInput.classList.add('field-invalid');
      break;

    case 'email_invalido':
      Swal.fire({
        icon: 'error',
        title: 'Correo inválido',
        text: 'Ingresa un correo electrónico con formato válido.',
        confirmButtonColor: 'var(--red-primary)'
      });
      emailInput.classList.add('field-invalid');
      break;

    case 'correo_no_registrado':
      Swal.fire({
        icon: 'error',
        title: 'Correo no registrado',
        text: 'No encontramos una cuenta activa con ese correo. Revisa que esté bien escrito o consulta a un administrador.',
        confirmButtonColor: 'var(--red-primary)'
      });
      emailInput.classList.add('field-invalid');
      break;
  }
}

forgotForm.addEventListener('submit', (e) => {
  emailInput.classList.remove('field-invalid');

  const email = emailInput.value.trim();
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if(email === ''){
    e.preventDefault();
    mostrarAlertaForgot('email_vacio');
    emailInput.focus();
    return;
  }
  if(!emailPattern.test(email)){
    e.preventDefault();
    mostrarAlertaForgot('email_invalido');
    emailInput.focus();
    return;
  }
  // Si pasa las validaciones, el form sigue su envío normal (POST a Django).
});

/* Error que devuelve el servidor (por ejemplo, correo no registrado) */
if(document.body.dataset.error){
  mostrarAlertaForgot(document.body.dataset.error);
}
