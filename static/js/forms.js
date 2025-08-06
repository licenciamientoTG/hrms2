document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("formSearch");
  const formItems = document.querySelectorAll(".form-item");

  const tabDisponibles = document.getElementById("tab-disponibles");
  const tabCompletados = document.getElementById("tab-completados");
  const contDisponibles = document.getElementById("contenedor-disponibles");
  const contCompletados = document.getElementById("contenedor-completados");

  // Función para aplicar búsqueda en formularios visibles
  function aplicarFiltro() {
    const searchTerm = searchInput.value.toLowerCase();
    formItems.forEach(item => {
      const name = item.querySelector(".form-name").textContent.toLowerCase();
      const contenedor = item.closest("#contenedor-disponibles, #contenedor-completados");

      if (contenedor && contenedor.style.display !== "none") {
        item.style.display = name.includes(searchTerm) ? "flex" : "none";
      } else {
        item.style.display = ""; // resetea visibilidad si no aplica
      }
    });
  }

  searchInput.addEventListener("input", aplicarFiltro);

  // Tabs funcionales
  tabDisponibles.addEventListener("click", () => {
    tabDisponibles.classList.add("active");
    tabCompletados.classList.remove("active");
    contDisponibles.style.display = "block";
    contCompletados.style.display = "none";
    aplicarFiltro();
  });

  tabCompletados.addEventListener("click", () => {
    tabCompletados.classList.add("active");
    tabDisponibles.classList.remove("active");
    contDisponibles.style.display = "none";
    contCompletados.style.display = "block";
    aplicarFiltro();
  });

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
        const modal = bootstrap.Modal.getInstance(document.getElementById("modalGuarderia"));
        modal.hide();
        form.reset();
      } else {
        alert("⚠️ No se pudo guardar la constancia.");
      }
    })
    .catch(error => {
      console.error("❌ Error al guardar:", error);
      alert("❌ Error al guardar la constancia.");
    });
  });
});
