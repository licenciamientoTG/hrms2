document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("formSearch");
  const formItems = document.querySelectorAll(".form-item");

  const tabDisponibles = document.getElementById("tab-disponibles");
  const tabEnProceso = document.getElementById("tab-en-proceso");
  const tabCompletados = document.getElementById("tab-completados");

  const contDisponibles = document.getElementById("contenedor-disponibles");
  const contEnProceso = document.getElementById("contenedor-en-proceso");
  const contCompletados = document.getElementById("contenedor-completados");

  // Función para aplicar búsqueda solo en el contenedor activo
  function aplicarFiltro() {
    const searchTerm = searchInput.value.toLowerCase();
    formItems.forEach(item => {
      const name = item.querySelector(".form-name").textContent.toLowerCase();
      const contenedor = item.closest("#contenedor-disponibles, #contenedor-completados, #contenedor-en-proceso");

      if (contenedor && contenedor.style.display !== "none") {
        item.style.display = name.includes(searchTerm) ? "flex" : "none";
      } else {
        item.style.display = ""; // reset
      }
    });
  }

  searchInput.addEventListener("input", aplicarFiltro);

  // Función para manejar visualización de tabs
  function activarTab(tabActiva, contenedorActivo) {
    // Reset tabs
    [tabDisponibles, tabEnProceso, tabCompletados].forEach(tab => tab.classList.remove("active"));
    tabActiva.classList.add("active");

    // Reset contenedores
    [contDisponibles, contEnProceso, contCompletados].forEach(cont => cont.style.display = "none");
    contenedorActivo.style.display = "block";

    aplicarFiltro();
  }

  tabDisponibles.addEventListener("click", () => activarTab(tabDisponibles, contDisponibles));
  tabEnProceso.addEventListener("click", () => activarTab(tabEnProceso, contEnProceso));
  tabCompletados.addEventListener("click", () => activarTab(tabCompletados, contCompletados));
});


function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("formGuarderia");
  const url = form.dataset.url;  // ✅ Obtenemos la URL desde el atributo data-url

  form.addEventListener("submit", function (e) {
    e.preventDefault(); // ⛔ Evita redirección

    const formData = new FormData(form);

    fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"), // ✅ CSRF desde cookies
      },
      body: formData,
    })
    .then(response => {
      if (!response.ok) {
        throw new Error("Respuesta no OK del servidor");
      }
      return response.json(); // ✅ Asegura que sea JSON
    })
    .then(data => {
      if (data.success) {
        Swal.fire({
          icon: 'success',
          title: '¡Éxito!',
          text: data.message || "Solicitud enviada correctamente.",
          confirmButtonColor: '#3085d6',
          confirmButtonText: 'Aceptar'
        }).then(() => {
          const modal = bootstrap.Modal.getInstance(document.getElementById("modalGuarderia"));
          modal.hide();
          form.reset();
          location.reload();
        });
      } else {
        Swal.fire({
          icon: 'error',
          title: 'Error',
          text: data.error || "⚠️ No se pudo guardar la constancia."
        });
      }
    })
    .catch(error => {
      console.error("❌ Error al guardar:", error);
      Swal.fire({
        icon: 'warning',
        title: 'Aviso',
        text: "❌ Ya cuenta con una solicitud en proceso"
      });
    });
  });
});


document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.btn-ver-solicitud');
  if (!btn) return;

  const url = btn.dataset.url;
  try {
    const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }});
    const data = await res.json();
    if (!data.ok) throw new Error('No se pudo cargar el detalle');

    const s = data.solicitud;
    document.getElementById('det-id').textContent = `#${s.id}`;
    document.getElementById('det-empleado').textContent = s.empleado || '—';
    document.getElementById('det-fecha').textContent = s.fecha_solicitud || '—';
    document.getElementById('det-dias').textContent = (s.dias_laborales || []).join(', ') || '—';
    document.getElementById('det-horario').textContent = (s.hora_entrada && s.hora_salida) ? `${s.hora_entrada} – ${s.hora_salida}` : '—';
    document.getElementById('det-guarderia').textContent = s.nombre_guarderia || '—';
    document.getElementById('det-direccion').textContent = s.direccion_guarderia || '—';
    document.getElementById('det-menor').textContent = s.nombre_menor ? `${s.nombre_menor} (nac. ${s.nacimiento_menor || '—'})` : '—';

    const estado = document.getElementById('det-estado');
    estado.textContent = s.estado || '—';
    estado.className = 'badge ' + (s.estado === 'completada' ? 'bg-success' :
                                   s.estado === 'rechazada' ? 'bg-danger' :
                                   'bg-warning text-dark');

    const modal = new bootstrap.Modal(document.getElementById('modalDetalleSolicitud'));
    modal.show();

  } catch (err) {
    console.error(err);
    alert('No se pudo cargar el detalle de la solicitud.');
  }
});

// abrir modal y enviar
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.btn-responder');
  if (!btn) return;
  const id = btn.dataset.id;
  document.getElementById('resp-id').value = id;
  document.getElementById('resp-id-label').textContent = `#${id}`;
  new bootstrap.Modal(document.getElementById('modalResponder')).show();
});

document.getElementById('formResponder').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('resp-id').value;
  const fd = new FormData(e.target); // incluye pdf_respuesta

  try {
    const res = await fetch(`/forms_requests/guarderia/${id}/responder/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: fd
    });
    const txt = await res.text();
    let data = null; try { data = JSON.parse(txt); } catch {}

    if (!res.ok || !data?.ok) throw new Error(data?.error || txt || 'Error al responder');

    // Actualiza la fila sin recargar
    const row = document.querySelector(`.btn-responder[data-id="${id}"]`)?.closest('tr');
    if (row) {
      // Estado → Completada
      const estadoCell = row.querySelector('td:nth-child(4)');
      if (estadoCell) estadoCell.innerHTML = '<span class="badge bg-success">Completada</span>';

      // PDF → Link
      const pdfCell = row.querySelector('td:nth-child(5)');
      if (pdfCell && data.pdf_url) {
        pdfCell.innerHTML = `<a href="${data.pdf_url}" target="_blank" rel="noopener">Ver PDF</a>`;
      }

      // Quitar botón "Responder"
      const btn = row.querySelector('.btn-responder');
      if (btn) btn.remove();
    }

    bootstrap.Modal.getInstance(document.getElementById('modalResponder')).hide();
  } catch (err) {
    console.error(err);
    alert('❌ ' + err.message);
  }
});

(function(){
  const $q = document.getElementById('filtro-q');
  const $estado = document.getElementById('filtro-estado');
  const $tbody = document.getElementById('tabla-solicitudes');
  const $contador = document.getElementById('contador');
  const $limpiar = document.getElementById('btn-limpiar');

  // Mapeo de sinónimos -> código
  const SYN = {
    'en proceso': 'pendiente',
    'pendientes': 'pendiente',
    'completados': 'completada',
    'completo': 'completada',
    'rechazados': 'rechazada',
  };

  function norm(s=''){
    try {
      return s.toString()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g,'')
        .toLowerCase()
        .trim();
    } catch(e){
      return (s+'').toLowerCase().trim();
    }
  }

  function toCode(value){
    const v = norm(value);
    return SYN[v] || v;  // si es sinónimo, devuelve el código; si no, deja tal cual
  }

  function filtrar(){
    const q = norm($q.value);
    const eRaw = $estado.value;          // viene del <select>, ya es el código (o vacío)
    const e = toCode(eRaw);

    let visibles = 0;

    Array.from($tbody.querySelectorAll('tr')).forEach(tr => {
      const id       = norm(tr.dataset.id);
      const emp      = norm(tr.dataset.empleado);
      const est      = norm(tr.dataset.estado);         // código
      const estLabel = norm(tr.dataset.estadoLabel || ''); // texto visible (“en proceso”)

      // Busca por id / empleado / estado (código) / estado (label)
      const matchTexto  = !q || id.includes(q) || emp.includes(q) || est.includes(q) || estLabel.includes(q);

      // Filtra por estado del select (acepta sinónimos si algún día cambian)
      const matchEstado = !e || est === e || toCode(est) === e;

      const show = matchTexto && matchEstado;
      tr.classList.toggle('d-none', !show);
      if (show) visibles++;
    });

    if ($contador) {
      const total = $tbody.querySelectorAll('tr').length;
      $contador.textContent = `${visibles} de ${total} resultados`;
    }
  }

  $q.addEventListener('input', filtrar);
  $estado.addEventListener('change', filtrar);
  $limpiar.addEventListener('click', () => {
    $q.value = '';
    $estado.value = '';
    filtrar();
  });

  filtrar();
})();


function getCookie(name) {
  const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return m ? m.pop() : '';
}

document.getElementById('btn-rechazar')?.addEventListener('click', async (ev) => {
  ev.preventDefault();
  const id = document.getElementById('resp-id').value;
  if (!id) return;

  const comentario = (document.getElementById('rechazo-comentario')?.value || '').trim();

  try {
    const res = await fetch(`/forms_requests/guarderia/${id}/rechazar/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: (() => {
        const fd = new FormData();
        fd.append('comentario', comentario);
        return fd;
      })()
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Error');

    // Cierra modal y refresca la lista (o recarga página)
    bootstrap.Modal.getInstance(document.getElementById('modalResponder'))?.hide();
    // Si tienes una función que refresca la tabla, llámala aquí.
    // Si no, recarga:
    location.reload();

  } catch (err) {
    console.error(err);
    alert('No se pudo rechazar la solicitud.');
  }
});