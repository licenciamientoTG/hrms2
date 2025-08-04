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

  console.log("✅ JS cargado correctamente");
});
