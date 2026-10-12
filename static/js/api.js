/* ============================================================
   api.js — cliente de la API de Django (fetch) + utilidades comunes.
   Reemplaza al antiguo store.js: ya no hay datos en el navegador,
   todo se lee y se guarda en la base de datos a través de /api/.
   Lee de <body>: data-api (URL base), data-csrf y data-login-url.
   ============================================================ */
const SGR = (() => {
  const BASE = document.body.dataset.api || '/api/';
  const CSRF = document.body.dataset.csrf || '';
  const LOGIN_URL = document.body.dataset.loginUrl || '/';
  const BTN = 'var(--red-primary)';

  async function pedir(metodo, ruta, datos){
    const opciones = {
      method: metodo,
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json', 'X-CSRFToken': CSRF }
    };
    if(datos !== undefined){
      opciones.headers['Content-Type'] = 'application/json';
      opciones.body = JSON.stringify(datos);
    }

    let res;
    try {
      res = await fetch(BASE + ruta, opciones);
    } catch(e) {
      throw { error: 'sin_conexion', status: 0 };
    }

    let cuerpo = null;
    try { cuerpo = await res.json(); } catch(e) { /* respuesta sin JSON (p. ej. error 500) */ }

    if(!res.ok){
      throw { ...(cuerpo || {}), error: (cuerpo && cuerpo.error) || 'error_servidor', status: res.status };
    }
    return cuerpo;
  }

  /**
   * Errores que pueden ocurrir en cualquier pantalla (un case por situación).
   * Devuelve true si mostró el popup; false si el error es propio de la pantalla.
   */
  function alertaComun(err){
    switch(err && err.error){
      case 'no_autenticado':
        Swal.fire({ icon: 'warning', title: 'Sesión expirada',
          text: 'Tu sesión terminó. Inicia sesión nuevamente.', confirmButtonColor: BTN })
          .then(() => { window.location.href = LOGIN_URL; });
        return true;
      case 'sin_conexion':
        Swal.fire({ icon: 'error', title: 'Sin conexión',
          text: 'No pudimos comunicarnos con el servidor. Revisa tu conexión e inténtalo de nuevo.', confirmButtonColor: BTN });
        return true;
      case 'prohibido':
        Swal.fire({ icon: 'error', title: 'Sin permiso',
          text: 'Tu rol no permite realizar esta acción.', confirmButtonColor: BTN });
        return true;
      case 'no_encontrado':
        Swal.fire({ icon: 'warning', title: 'Registro no encontrado',
          text: 'El registro ya no existe. Se recargarán los datos.', confirmButtonColor: BTN });
        return true;
      case 'error_servidor':
        Swal.fire({ icon: 'error', title: 'Error del servidor',
          text: 'Ocurrió un problema al procesar la solicitud. Intenta nuevamente.', confirmButtonColor: BTN });
        return true;
    }
    return false;
  }

  function esc(s){
    return String(s ?? '').replace(/[&<>"']/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
  }

  function formatearFecha(iso){
    if(!iso) return '';
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
  }

  return {
    listar:      (entidad) => pedir('GET', entidad + '/'),
    crear:       (entidad, datos) => pedir('POST', entidad + '/', datos),
    actualizar:  (entidad, id, datos) => pedir('PUT', `${entidad}/${id}/`, datos),
    eliminar:    (entidad, id) => pedir('DELETE', `${entidad}/${id}/`),
    get:         (ruta) => pedir('GET', ruta),
    post:        (ruta, datos) => pedir('POST', ruta, datos || {}),
    put:         (ruta, datos) => pedir('PUT', ruta, datos),
    alertaComun, esc, formatearFecha
  };
})();
