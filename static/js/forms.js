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
    e.preventDefault();  // ⛔ Evita redirección

    const formData = new FormData(form);

    fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),  // ✅ CSRF desde cookies
      },
      body: formData,
    })
    .then(response => {
      if (!response.ok) {
        throw new Error("Respuesta no OK del servidor");
      }
      return response.json();  // ✅ Asegura que sea JSON
    })
    .then(data => {
      if (data.success) {
        alert(data.message || "Solicitud enviada correctamente.");
        const modal = bootstrap.Modal.getInstance(document.getElementById("modalGuarderia"));
        modal.hide();
        form.reset();
        location.reload();
      } else {
          alert(data.error || "⚠️ No se pudo guardar la constancia.");
      }
    })
    .catch(error => {
      console.error("❌ Error al guardar:", error);
      alert("❌ Ya cuenta con una solicitúd en proceso");
    });
  });
});
