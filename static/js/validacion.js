/* ============================================================
   validacion.js — validación de campos MIENTRAS SE ESCRIBE.

   Se activa con atributos en el HTML (sirve también para campos que
   se crean después, como los modales de Administración):
     data-validar="rut"        RUT chileno: se formatea solo (12.345.678-5)
                               y se revisa el dígito verificador (módulo 11)
     data-validar="telefono"   8 a 15 dígitos; solo números, espacios y + ( ) -
     data-validar="correo"     formato nombre@dominio.cl
     data-validar="nombre"     al menos 2 letras
     data-validar="texto:10"   al menos 10 caracteres (muestra el conteo)
     data-validar="entero"     número entero entre min y max del input
     data-validar="clave"      8+ caracteres, mayúscula, número y símbolo
     data-validar="igual:ID"   debe coincidir con el campo de ese id
     data-requerido            no puede quedar vacío

   El servidor vuelve a validar todo: esto solo avisa antes.
   Expone window.SGRValidar para usarlo al enviar un formulario.
   ============================================================ */
(() => {
  /* ---------- RUT ---------- */
  function limpiarRut(valor){
    let l = String(valor || '').toUpperCase().replace(/[^0-9K]/g, '');
    l = l.replace(/K(?!$)/g, '');          // la K solo puede ir al final (dígito verificador)
    return l.slice(0, 9);
  }
  function digitoVerificador(cuerpo){
    let suma = 0, factor = 2;
    for(let i = cuerpo.length - 1; i >= 0; i--){
      suma += Number(cuerpo[i]) * factor;
      factor = factor === 7 ? 2 : factor + 1;
    }
    const resto = 11 - (suma % 11);
    return resto === 11 ? '0' : resto === 10 ? 'K' : String(resto);
  }
  function formatearRut(valor){
    const l = limpiarRut(valor);
    if(l.length < 2) return l;
    const cuerpo = l.slice(0, -1).replace(/^0+/, '') || '0';
    return cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + '-' + l.slice(-1);
  }
  function esRutValido(valor){
    const l = limpiarRut(valor);
    if(!/^\d{7,8}[0-9K]$/.test(l)) return false;
    return digitoVerificador(l.slice(0, -1)) === l.slice(-1);
  }

  const CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  const digitos = (v) => v.replace(/\D/g, '').length;

  /* ---------- Reglas ----------
     Cada regla recibe (valor, input, terminado) y devuelve:
       { ok:true, msg? }  válido      { ok:false, msg }  error
       null               aún incompleto: no se marca mientras escribe */
  const REGLAS = {
    rut(v, _el, terminado){
      const l = limpiarRut(v);
      if(l.length < 8 && !terminado) return null;
      if(!/^\d{7,8}[0-9K]$/.test(l)) return { ok: false, msg: 'RUT incompleto. Ejemplo: 12.345.678-5' };
      if(!esRutValido(l)) return { ok: false, msg: 'El dígito verificador no corresponde: revisa el RUT.' };
      return { ok: true, msg: 'RUT válido' };
    },
    telefono(v, _el, terminado){
      if(/[^0-9+()\s-]/.test(v)) return { ok: false, msg: 'Usa solo números, espacios y + ( ) -' };
      const n = digitos(v);
      if(n < 8) return terminado ? { ok: false, msg: `Faltan dígitos: tiene ${n}, mínimo 8.` } : null;
      if(n > 15) return { ok: false, msg: `Demasiados dígitos: tiene ${n}, máximo 15.` };
      return { ok: true };
    },
    correo(v, _el, terminado){
      if(/\s/.test(v)) return { ok: false, msg: 'El correo no puede tener espacios.' };
      if(!CORREO.test(v)) return terminado || v.includes('@') && v.split('@')[1].includes('.')
        ? { ok: false, msg: 'Correo inválido. Ejemplo: nombre@municipalidad.cl' } : null;
      return { ok: true };
    },
    nombre(v, _el, terminado){
      const letras = (v.match(/\p{L}/gu) || []).length;
      if(/[<>{}\[\]]/.test(v)) return { ok: false, msg: 'El nombre tiene caracteres no permitidos.' };
      if(letras < 2) return terminado ? { ok: false, msg: 'Escribe un nombre (al menos 2 letras).' } : null;
      return { ok: true };
    },
    texto(v, _el, terminado, minimo){
      const n = v.trim().length;
      if(n < minimo) return { ok: false, pendiente: !terminado, msg: `${n} de ${minimo} caracteres mínimos` };
      return { ok: true, msg: `${n} caracteres` };
    },
    entero(v, el){
      if(!/^\d+$/.test(v)) return { ok: false, msg: 'Ingresa un número entero, sin puntos ni decimales.' };
      const n = Number(v), min = el.min !== '' ? Number(el.min) : -Infinity, max = el.max !== '' ? Number(el.max) : Infinity;
      if(n < min || n > max) return { ok: false, msg: `Debe estar entre ${el.min} y ${el.max}.` };
      return { ok: true };
    },
    clave(v, _el, terminado){
      const falta = [];
      if(v.length < 8) falta.push('8 caracteres');
      if(!/[A-Z]/.test(v)) falta.push('una mayúscula');
      if(!/\d/.test(v)) falta.push('un número');
      if(!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(v)) falta.push('un símbolo (!@#$%…)');
      if(falta.length) return { ok: false, pendiente: !terminado, msg: 'Falta: ' + falta.join(', ') };
      return { ok: true, msg: 'Contraseña segura' };
    },
    igual(v, _el, terminado, idOtro){
      const otro = document.getElementById(idOtro);
      if(!otro) return { ok: true };
      if(v !== otro.value) return terminado || v.length >= otro.value.length ? { ok: false, msg: 'No coincide.' } : null;
      return { ok: true, msg: 'Coincide' };
    }
  };

  /* ---------- Mensaje bajo el campo ---------- */
  function mensajeDe(el){
    let msg = el.parentElement.querySelector(`.field-msg[data-para="${el.id || el.name}"]`);
    if(!msg){
      msg = document.createElement('span');
      msg.className = 'field-msg';
      msg.dataset.para = el.id || el.name || '';
      msg.setAttribute('aria-live', 'polite');
      if(el.id){
        msg.id = `${el.id}-msg`;
        el.setAttribute('aria-describedby', msg.id);
      }
      el.insertAdjacentElement('afterend', msg);
    }
    return msg;
  }

  function pintar(el, resultado){
    const msg = mensajeDe(el);
    el.classList.remove('field-invalid', 'field-valid');
    msg.classList.remove('error', 'ok');
    el.removeAttribute('aria-invalid');
    if(!resultado){ msg.textContent = ''; return; }
    if(resultado.ok){
      if(el.value !== '') el.classList.add('field-valid');
      msg.textContent = resultado.msg || '';
      if(resultado.msg) msg.classList.add('ok');
    } else if(resultado.pendiente){
      msg.textContent = resultado.msg;     // aviso neutro mientras escribe
    } else {
      el.classList.add('field-invalid');
      el.setAttribute('aria-invalid', 'true');
      msg.textContent = resultado.msg;
      msg.classList.add('error');
    }
  }

  /** Valida un campo. terminado = salió del campo o se intenta enviar. Devuelve true si es válido. */
  function validarCampo(el, terminado){
    if(el.disabled) { pintar(el, null); return true; }
    const valor = el.value || '';
    if(valor.trim() === ''){
      const falta = el.hasAttribute('data-requerido');
      pintar(el, falta && terminado ? { ok: false, msg: 'Campo obligatorio.' } : null);
      return !falta;
    }
    const regla = el.dataset.validar;
    if(!regla) { pintar(el, terminado ? { ok: true } : null); return true; }
    const [nombre, param] = regla.split(':');
    const fn = REGLAS[nombre];
    if(!fn) return true;
    const resultado = fn(valor, el, terminado, nombre === 'texto' ? Number(param) : param);
    pintar(el, resultado);
    return !resultado || resultado.ok || false;
  }

  /** Valida todos los campos de un formulario o contenedor. Devuelve el primero inválido o null. */
  function validarTodo(contenedor){
    let primero = null;
    contenedor.querySelectorAll('[data-validar], [data-requerido]').forEach((el) => {
      const ok = validarCampo(el, true);
      if(!ok && !primero) primero = el;
    });
    return primero;
  }

  const objetivo = (e) => e.target && e.target.matches && e.target.matches('[data-validar], [data-requerido]') ? e.target : null;

  document.addEventListener('input', (e) => {
    const el = objetivo(e);
    if(!el) return;
    if(el.dataset.validar === 'rut'){
      const antes = el.value, formateado = formatearRut(antes);
      if(formateado !== antes){
        const alFinal = el.selectionStart === antes.length;
        el.value = formateado;
        if(alFinal) el.setSelectionRange(formateado.length, formateado.length);
      }
    }
    validarCampo(el, el.dataset.tocado === '1');
  });
  document.addEventListener('focusout', (e) => {
    const el = objetivo(e);
    if(!el) return;
    el.dataset.tocado = '1';
    validarCampo(el, true);
  });
  // Al limpiar un formulario se borran los mensajes.
  document.addEventListener('reset', (e) => {
    setTimeout(() => e.target.querySelectorAll('[data-validar], [data-requerido]').forEach((el) => {
      delete el.dataset.tocado;
      pintar(el, null);
    }));
  });

  window.SGRValidar = { esRutValido, formatearRut, limpiarRut, validarCampo, validarTodo };
})();
