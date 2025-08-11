document.addEventListener("DOMContentLoaded", () => {
  fetch("/courses/unread_count/")
    .then(res => res.json())
    .then(data => {
      const count = data.unread_count;
      const badge = document.getElementById("new-courses-count");
      if (count > 0) {
        badge.textContent = count;
        badge.classList.remove("d-none");
      }
    });
});
