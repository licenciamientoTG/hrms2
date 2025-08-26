document.addEventListener("DOMContentLoaded", function () {
  if (!window.tinymce) {
    console.error("[news] TinyMCE no cargó");
    return;
  }

  tinymce.init({
    selector: 'textarea[name="content"]',
    height: 420,
    menubar: false,
    branding: false,
    promotion: false,
    language: 'es',
    plugins: 'lists link image media table emoticons charmap anchor code',
    toolbar: 'undo redo | bold italic underline | forecolor backcolor | ' +
             'fontsizeselect fontselect styles | alignleft aligncenter alignright alignjustify | ' +
             'numlist bullist | outdent indent | link anchor | media table | emoticons charmap | code',
    object_resizing: 'iframe',
    media_live_embeds: true,
    media_dimensions: true,
    extended_valid_elements: 'iframe[src|width|height|frameborder|allow|allowfullscreen]',
    content_style:
      "body{font-family:Inter,Arial,sans-serif;font-size:14px}" +
      ".embed-responsive{position:relative;width:100%;padding-bottom:56.25%;}" +
      ".embed-responsive iframe{position:absolute;top:0;left:0;width:100%;height:100%;}",

    setup(editor) {
      const form = document.getElementById("news-form");
      if (!form) return;

      form.addEventListener("submit", (e) => {
        // Pasa el HTML del editor al <textarea>
        tinymce.triggerSave();

        // Validación mínima: que no esté vacío
        const plain = editor.getContent({ format: 'text' }).trim();
        if (!plain) {
          e.preventDefault();
          alert("El contenido es obligatorio.");
          editor.focus();
        }
      });
    }
  });
});


tinymce.init({
  selector: 'textarea[name="content"]',
  height: 420,

  // UI limpia:
  menubar: false,       // oculta menú "File / Edit / …"
  branding: false,      // quita "Crear con TinyMCE" del status bar
  promotion: false,     // 👈 quita el botón "Explore trial"

  plugins: 'lists link image media table emoticons charmap anchor code',
  toolbar: 'undo redo | bold italic underline | forecolor backcolor | ' +
           'fontsizeselect fontselect styles | alignleft aligncenter alignright alignjustify | ' +
           'numlist bullist | outdent indent | link anchor | media table | emoticons charmap | code',

  object_resizing: 'iframe',
  media_live_embeds: true,
  media_dimensions: true,
  extended_valid_elements: 'iframe[src|width|height|frameborder|allow|allowfullscreen]',
});