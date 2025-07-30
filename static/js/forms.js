document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("formSearch");
  const formItems = document.querySelectorAll(".form-item");

  searchInput.addEventListener("input", function () {
    const searchTerm = searchInput.value.toLowerCase();

    formItems.forEach(item => {
      const name = item.querySelector(".form-name").textContent.toLowerCase();
      item.style.display = name.includes(searchTerm) ? "flex" : "none";
    });
  });
});

