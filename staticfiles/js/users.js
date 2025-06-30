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
