function toggleStatus(userId) {
  fetch(toggleUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-CSRFToken": csrfToken
    },
    body: "user_id=" + userId
  })
  .then(response => response.json())
  .then(data => {
    if (data.status === "ok") {
      const row = document.getElementById("row-" + userId);
      const statusSpan = row.querySelector(".status");
      const button = row.querySelector("button");

      if (data.is_active) {
        statusSpan.textContent = "✅ Activo";
        button.textContent = "Desactivar";
      } else {
        statusSpan.textContent = "🚫 Inactivo";
        button.textContent = "Activar";
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", function () {
  const filtroInput = document.getElementById("searchUsuarios");
  const rows = document.querySelectorAll(".user-table tbody tr");
  const pagination = document.getElementById("pagination");
  const itemsPerPage = 10;

  let filtroTexto = "";
  let currentPage = 1;

  function applyFilters() {
    let visibles = [];

    rows.forEach(row => {
      const name = row.querySelector('.name')?.innerText.toLowerCase() || '';
      const username = row.querySelector('td:nth-child(2)')?.innerText.toLowerCase() || '';

      const matchTexto = name.includes(filtroTexto) || username.includes(filtroTexto);

      if (matchTexto) {
        visibles.push(row);
      }

      row.style.display = "none";
    });

    renderPage(visibles, currentPage);
    renderPagination(visibles);
  }

  function renderPage(rowsFiltradas, page) {
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;

    rowsFiltradas.forEach((row, i) => {
      row.style.display = (i >= start && i < end) ? "" : "none";
    });
  }

  function renderPagination(rowsFiltradas) {
    const totalPages = Math.ceil(rowsFiltradas.length / itemsPerPage);
    pagination.innerHTML = "";

    if (totalPages <= 1) return;

    for (let i = 1; i <= totalPages; i++) {
      const btn = document.createElement("button");
      btn.className = `btn btn-sm mx-1 ${i === currentPage ? "btn-primary" : "btn-outline-primary"}`;
      btn.textContent = i;
      btn.addEventListener("click", () => {
        currentPage = i;
        renderPage(rowsFiltradas, i);
        renderPagination(rowsFiltradas);
      });
      pagination.appendChild(btn);
    }
  }

  filtroInput.addEventListener("input", function () {
    filtroTexto = this.value.toLowerCase().trim();
    currentPage = 1;
    applyFilters();
  });

  applyFilters();
});

