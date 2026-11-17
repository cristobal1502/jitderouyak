/* ============================================================
   sidebar.js — botón para contraer el menú lateral a solo íconos.
   La preferencia se guarda en el navegador (localStorage); la clase
   se aplica antes de pintar con un script corto en el <head>.
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
