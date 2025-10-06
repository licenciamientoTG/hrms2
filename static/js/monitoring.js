  if (window.bootstrap) {
    document.querySelectorAll('.usage-week .day').forEach(el=>{
      new bootstrap.Tooltip(el);
    });
  }