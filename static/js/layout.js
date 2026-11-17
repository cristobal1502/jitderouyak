/* ============================================================
   layout.js — partes comunes de todas las pantallas:
   1) botón para contraer el menú lateral a solo íconos (la preferencia
      se guarda en el navegador; la clase se aplica antes de pintar con
      un script corto en el <head>);
   2) selector de delegación de la barra superior (la elección se guarda
      en la sesión del servidor, así todas las pantallas la respetan).
   ============================================================ */
(() => {
  const CLAVE = 'sgr.menu';
  const raiz = document.documentElement;
  const boton = document.getElementById('sidebarToggle');

  // Al estar contraído no se ve el texto: cada ícono muestra su nombre al pasar el mouse.
  document.querySelectorAll('.sidebar .nav-item').forEach((item) => {
    const nombre = item.textContent.replace(/\s+/g, ' ').replace(/\badmin\b/, '').trim();
    if(nombre){
      item.setAttribute('aria-label', nombre);
      item.dataset.nombre = nombre;
    }
  });

  function aplicar(contraido){
    raiz.classList.toggle('sidebar-collapsed', contraido);
    document.querySelectorAll('.sidebar .nav-item').forEach((item) => {
      if(contraido && item.dataset.nombre) item.title = item.dataset.nombre;
      else item.removeAttribute('title');
    });
    if(boton){
      boton.setAttribute('aria-expanded', String(!contraido));
      boton.setAttribute('aria-label', contraido ? 'Expandir menú' : 'Contraer menú');
      boton.title = contraido ? 'Expandir menú' : 'Contraer menú';
    }
  }

  aplicar(raiz.classList.contains('sidebar-collapsed'));

  if(boton){
    boton.addEventListener('click', () => {
      const contraido = !raiz.classList.contains('sidebar-collapsed');
      aplicar(contraido);
      try { localStorage.setItem(CLAVE, contraido ? 'contraido' : 'expandido'); } catch(e) { /* sin almacenamiento: solo dura esta página */ }
    });
  }
})();

/* ---------- Selector de delegación ---------- */
(() => {
  const boton = document.getElementById('delegacionBtn');
  const menu = document.getElementById('delegacionMenu');
  if(!boton || !menu) return;
  const opciones = () => [...menu.querySelectorAll('.delegacion-opcion')];

  function abrir(){
    menu.hidden = false;
    boton.setAttribute('aria-expanded', 'true');
    (menu.querySelector('.delegacion-opcion.activa') || opciones()[0]).focus();
  }
  function cerrar(devolverFoco){
    menu.hidden = true;
    boton.setAttribute('aria-expanded', 'false');
    if(devolverFoco) boton.focus();
  }

  boton.addEventListener('click', () => (menu.hidden ? abrir() : cerrar(false)));
  document.addEventListener('click', (e) => {
    if(!menu.hidden && !menu.contains(e.target) && !boton.contains(e.target)) cerrar(false);
  });
  menu.addEventListener('keydown', (e) => {
    const lista = opciones();
    const i = lista.indexOf(document.activeElement);
    if(e.key === 'Escape'){ e.preventDefault(); cerrar(true); }
    if(e.key === 'ArrowDown'){ e.preventDefault(); lista.at((i + 1) % lista.length).focus(); }
    if(e.key === 'ArrowUp'){ e.preventDefault(); lista.at((i - 1 + lista.length) % lista.length).focus(); }
  });
  // Mientras se recarga la página, se marca la opción elegida para que se note el clic.
  menu.addEventListener('submit', (e) => {
    opciones().forEach((o) => o.classList.toggle('activa', o === e.submitter));
    boton.classList.add('cargando');
  });
})();
