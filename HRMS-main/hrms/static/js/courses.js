document.addEventListener("DOMContentLoaded", function () {
    // 🔴 Al cargar la página, eliminar los módulos y lecciones del localStorage
    localStorage.removeItem("modules");

    // Continuar con la carga normal
    loadModulesFromStorage(); // Esto ahora cargará una lista vacía
});

document.addEventListener("DOMContentLoaded", function () {
    let currentStep = 1;
    const steps = document.querySelectorAll(".wizard-step");
    const moduleContainer = document.getElementById("module-container");
    const addModuleBtn = document.getElementById("add-module");

    function showStep(step) {
        steps.forEach((el, index) => el.classList.toggle("d-none", index !== step - 1));
    } 

    function validateStepFields(step) {
        let stepElement = document.getElementById(`step-${step}`);
        let valid = true;
    
        stepElement.querySelectorAll("input, textarea, select").forEach(field => {
            if (field.hasAttribute("required") && !field.value.trim()) {
                field.classList.add("is-invalid"); // 🔴 Agrega borde rojo si el campo está vacío
                valid = false;
            } else {
                field.classList.remove("is-invalid"); // ✅ Quita el borde rojo si el campo se llena
            }
        });
    
        return valid;
    }

    document.querySelectorAll(".next-step").forEach(button => {
        button.addEventListener("click", function () {
            if (!validateStepFields(currentStep)) {
                Swal.fire({
                    icon: "error",
                    title: "Campos incompletos",
                    text: "Por favor, completa todos los campos antes de continuar.",
                });
                return; // 🔴 Evita avanzar si la validación falla
            }
    
            if (currentStep === 3 && !validateModulesAndLessons()) {
                Swal.fire({
                    icon: "error",
                    title: "Oops...",
                    text: "Debes de guardar al menos un módulo antes de continuar.",
                });
                return; // Evita avanzar al siguiente paso
            }
    
            saveStepData(currentStep); // Guarda los datos antes de avanzar
    
            if (currentStep < steps.length) {
                currentStep++;
                showStep(currentStep);
                loadStepData(currentStep); // Carga los datos guardados
    
                if (currentStep === 4) {
                    generateSummary();
                }
            }
        });
    });
    

    document.querySelectorAll(".prev-step").forEach(button => {
        button.addEventListener("click", function () {
            if (currentStep > 1) {
                currentStep--;
                showStep(currentStep);
                loadStepData(currentStep); // Carga los datos guardados al retroceder
            }
        });
    });


    showStep(currentStep);

    function validateModulesAndLessons() {
        let moduleCards = document.querySelectorAll("#module-container .card");
        return moduleCards.length > 0; // Solo avanza si hay módulos guardados como card
    }

    let imageInput = document.getElementById("id_portrait"); // Asegurar que este ID sea correcto
    let previewImage = document.getElementById("preview-image");

    if (imageInput) {
        imageInput.addEventListener("change", function (event) {
            let file = event.target.files[0];
            if (file) {
                let reader = new FileReader();
                reader.onload = function () {
                    previewImage.src = reader.result;
                    previewImage.classList.remove("d-none"); // Mostrar la imagen
                };
                reader.readAsDataURL(file);
            }
        });
    }
    
    function saveStepData(step) {
        let stepData = {};

        if (step === 1 || step === 2 || step === 4) {
            document.querySelectorAll(`#step-${step} input, #step-${step} textarea, #step-${step} select`).forEach(field => {
                let key = field.name || field.id.replace("id_", "");  // 👈 CORRECCIÓN
                if (field.type === "radio") {
                    if (!stepData.hasOwnProperty(key)) {
                        stepData[key] = "off";
                    }
                    if (field.checked) {
                        stepData[key] = field.value;
                    }
                } else if (field.type === "checkbox") {
                    stepData[key] = field.checked ? "on" : "off";
                } else {
                    stepData[key] = field.value;
                }
            });

            console.log(`📌 Guardando en localStorage -> step${step}:`, stepData);
            localStorage.setItem(`step${step}`, JSON.stringify(stepData));
        }
    }

    
        
    function loadStepData(step) {
        let stepData = JSON.parse(localStorage.getItem(`step${step}`)) || {};
    
        console.log(`📌 Cargando datos para step${step}:`, stepData);
    
        if (step === 1 || step === 2 || step === 4) {
            document.querySelectorAll(`#step-${step} input, #step-${step} textarea, #step-${step} select`).forEach(field => {
                if (field.type === "radio") {
                    field.checked = stepData[field.name] === field.value;
                } else if (field.type === "checkbox") {
                    field.checked = stepData[field.name] === "on"; // ✅ Restaurar checkboxes correctamente
                } else {
                    field.value = stepData[field.name] || "";
                }
            });
        }
    }
    
    
    

    // 📌 Función para agregar un nuevo módulo
    function addModule(moduleData = null) {
        let moduleId = "module-" + Date.now();
        let newModule = document.createElement("div");
        newModule.classList.add("module-form", "border", "p-3", "mb-3");
        newModule.setAttribute("data-module-id", moduleId);

        newModule.innerHTML = `
            <h4>Módulo</h4>
            <div class="mb-3">
                <label class="form-label">Curso:</label>
                <input type="text" class="form-control module-course" name="module_course[]" value="${moduleData?.course || ''}" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Título del Módulo:</label>
                <input type="text" class="form-control module-title" name="module_title[]" value="${moduleData?.title || ''}" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Descripción:</label>
                <textarea class="form-control module-description" name="module_description[]" rows="3" required>${moduleData?.description || ''}</textarea>
            </div>
            <button type="button" class="btn btn-outline-success add-lesson">Agregar Lección</button>
            <div class="lesson-container mt-3"></div>
            <button type="button" class="btn btn-primary btn-sm save-module mt-3">Guardar Módulo</button>
            <button type="button" class="btn btn-danger btn-sm remove-module mt-3">Eliminar Módulo</button>
        `;

        // 📌 Evento para guardar el módulo cuando el usuario hace clic en "Guardar Módulo"
        newModule.querySelector(".save-module").addEventListener("click", function () {
        saveModule(newModule);
        });


        moduleContainer.appendChild(newModule);
        let lessonContainer = newModule.querySelector(".lesson-container");
        let addLessonBtn = newModule.querySelector(".add-lesson");

        addLessonBtn.addEventListener("click", function () {
            addLesson(lessonContainer);
        });

        newModule.querySelector(".remove-module").addEventListener("click", function () {
            removeModule(newModule);
        });

        if (moduleData && moduleData.lessons) {
            moduleData.lessons.forEach(lesson => addLesson(lessonContainer, lesson));
        }
    }

function saveModule(moduleElement) {
    let moduleId = moduleElement.getAttribute("data-module-id");
    let moduleCourse = moduleElement.querySelector(".module-course");
    let moduleTitle = moduleElement.querySelector(".module-title");
    let moduleDescription = moduleElement.querySelector(".module-description");
    let lessons = moduleElement.querySelectorAll(".lesson-form");

    // 🔴 Validar que los campos del módulo no estén vacíos
    if (!moduleCourse.value.trim() || !moduleTitle.value.trim() || !moduleDescription.value.trim()) {
        Swal.fire({
            icon: "error",
            title: "Campos incompletos en el módulo",
            text: "Por favor, completa todos los campos del módulo antes de guardarlo.",
        });

        // Resaltar los campos vacíos
        [moduleCourse, moduleTitle, moduleDescription].forEach(field => {
            if (!field.value.trim()) {
                field.classList.add("is-invalid");
            } else {
                field.classList.remove("is-invalid");
            }
        });

        return; // ❌ Bloquea el guardado
    }

    // 🔴 Validar que haya al menos una lección agregada
    if (lessons.length === 0) {
        Swal.fire({
            icon: "error",
            title: "Faltan lecciones",
            text: "Debes agregar al menos una lección antes de guardar el módulo.",
        });
        return; // ❌ Bloquea el guardado
    }

    let moduleData = {
        id: moduleId,
        created_at: Date.now(),
        course: moduleCourse.value.trim(),
        title: moduleTitle.value.trim(),
        description: moduleDescription.value.trim(),
        lessons: []
    };

    let hasEmptyLesson = false;

    // 🔴 Validar cada lección
lessons.forEach((lessonElement, index) => {
        let lessonTitle = lessonElement.querySelector(".lesson-title");
        let lessonType = lessonElement.querySelector(".lesson-type");
        let lessonDescription = lessonElement.querySelector(".lesson-description");

        if (!lessonTitle.value.trim() || !lessonType.value.trim() || !lessonDescription.value.trim()) {
            hasEmptyLesson = true;

            // Resaltar los campos vacíos
            [lessonTitle, lessonType, lessonDescription].forEach(field => {
                if (!field.value.trim()) {
                    field.classList.add("is-invalid");
                } else {
                    field.classList.remove("is-invalid");
                }
            });
        } else {
            // Si los campos están completos, eliminar la clase de error
            [lessonTitle, lessonType, lessonDescription].forEach(field => {
                field.classList.remove("is-invalid");
            });

        let lessonVideoURL = lessonElement.querySelector(".lesson-video-url");

            moduleData.lessons.push({
                title: lessonTitle.value.trim(),
                type: lessonType.value,
                description: lessonDescription.value.trim(),
                video_url: lessonVideoURL.value.trim(),
                resource_index: index
            });
        }
    });

    // Si alguna lección tiene campos vacíos, bloquear el guardado
    if (hasEmptyLesson) {
        Swal.fire({
            icon: "error",
            title: "Campos incompletos en las lecciones",
            text: "Completa todos los campos de las lecciones antes de guardar el módulo.",
        });
        return; // ❌ Bloquea el guardado
    }

    // ✅ Si pasa todas las validaciones, guardar el módulo
    let storedModules = JSON.parse(localStorage.getItem("modules")) || [];
    storedModules = storedModules.filter(m => m.id !== moduleId); // Eliminar duplicado si ya existía
    storedModules.push(moduleData);
    localStorage.setItem("modules", JSON.stringify(storedModules));

    Swal.fire({
        icon: "success",
        title: "Módulo guardado",
        text: "El módulo ha sido guardado correctamente.",
    });

    renderModuleCard(moduleElement, moduleData);
}


    // 📌 Función para renderizar un módulo como una card
    function renderModuleCard(moduleElement, moduleData) {
        moduleElement.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">${moduleData.title}</h5>
                    <h6 class="card-subtitle mb-2 text-muted">${moduleData.course}</h6>
                    <p class="card-text">${moduleData.description}</p>
                    <button type="button" class="btn btn-warning edit-module">Editar</button>
                    <button type="button" class="btn btn-danger remove-module">Eliminar</button>
                </div>
            </div>
        `;

        moduleElement.querySelector(".edit-module").addEventListener("click", function () {
            restoreModuleForm(moduleElement, moduleData);
        });

        moduleElement.querySelector(".remove-module").addEventListener("click", function () {
            removeModule(moduleElement);
        });
    }

    // 📌 Función para restaurar un módulo a su estado editable
    function restoreModuleForm(moduleElement, moduleData) {
        // Crear un nuevo contenedor para reemplazar el existente
        let newModule = document.createElement("div");
        newModule.classList.add("module-form", "border", "p-3", "mb-3");
        newModule.setAttribute("data-module-id", moduleData.id);
    
        newModule.innerHTML = `
            <h4>Módulo</h4>
            <div class="mb-3">
                <label class="form-label">Curso:</label>
                <input type="text" class="form-control module-course" name="module_course[]" value="${moduleData.course}" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Título del Módulo:</label>
                <input type="text" class="form-control module-title" name="module_title[]" value="${moduleData.title}" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Descripción:</label>
                <textarea class="form-control module-description" name="module_description[]" rows="3" required>${moduleData.description}</textarea>
            </div>
            <button type="button" class="btn btn-outline-success add-lesson">Agregar Lección</button>
            <div class="lesson-container mt-3"></div>
            <button type="button" class="btn btn-primary btn-sm save-module mt-3">Guardar Módulo</button>
        `;
    
        // Reemplazar el módulo en el DOM
        moduleElement.replaceWith(newModule);
    
        // Seleccionar el nuevo contenedor de lecciones
        let lessonContainer = newModule.querySelector(".lesson-container");
    
        // Restaurar las lecciones del módulo
        moduleData.lessons.forEach(lesson => addLesson(lessonContainer, lesson));
    
        // Agregar evento para agregar lecciones
        newModule.querySelector(".add-lesson").addEventListener("click", function () {
            addLesson(lessonContainer);
        });
    
        // Agregar evento para guardar el módulo nuevamente
        newModule.querySelector(".save-module").addEventListener("click", function () {
            saveModule(newModule);
        });
    }
    
    function removeModule(moduleElement) {
        let moduleId = moduleElement.getAttribute("data-module-id");
        let storedModules = JSON.parse(localStorage.getItem("modules")) || [];
        storedModules = storedModules.filter(m => m.id !== moduleId);
        localStorage.setItem("modules", JSON.stringify(storedModules));
        moduleElement.remove();
    }

    // 📌 Función para agregar una lección dentro de un módulo específico con recurso y guardar
function addLesson(lessonContainer, lessonData = null) {
    let newLesson = document.createElement("div");
    newLesson.classList.add("lesson-form", "border", "p-3", "mb-3");

    let lessonId = "lesson-" + Date.now();
    newLesson.setAttribute("data-lesson-id", lessonId);

    newLesson.innerHTML = `
        <div class="mb-3">
            <label class="form-label">Título de la Lección:</label>
            <input type="text" class="form-control lesson-title" name="lesson_title[]" value="${lessonData?.title || ''}" required>
        </div>
        <div class="mb-3">
            <label class="form-label">Tipo de Lección:</label>
            <select class="form-control lesson-type" name="lesson_type[]" required>
                <option value="Video" ${lessonData?.type === "Video" ? "selected" : ""}>Video</option>
                <option value="Lectura" ${lessonData?.type === "Lectura" ? "selected" : ""}>Lectura</option>
                <option value="Artículo" ${lessonData?.type === "Artículo" ? "selected" : ""}>Artículo</option>
            </select>
        </div>
        <div class="mb-3">
            <label class="form-label">Descripción:</label>
            <textarea class="form-control lesson-description" name="lesson_description[]" rows="3" required>${lessonData?.description || ''}</textarea>
        </div>
        <div class="mb-3">
            <label class="form-label">Recurso (Opcional):</label>
            <input type="file" class="form-control lesson-resource" name="lesson_resource[]">
        </div>
        <div class="mb-3">
            <label class="form-label">URL de Video (YouTube, opcional):</label>
            <input type="url" class="form-control lesson-video-url" name="lesson_video_url[]" placeholder="https://www.youtube.com/watch?v=..." value="${lessonData?.video_url || ''}">
        </div>
        <button type="button" class="btn btn-danger btn-sm remove-lesson">Eliminar Lección</button>
    `;

    // Evento para eliminar
    newLesson.querySelector(".remove-lesson").addEventListener("click", function () {
        Swal.fire({ /* ... */ }).then(result => {
            if (result.isConfirmed) {
                removeLesson(newLesson);
            }
        });
    });

    lessonContainer.appendChild(newLesson);
}



    // 📌 Función para eliminar una lección del DOM y del localStorage
    function removeLesson(lessonElement) {
        let lessonTitle = lessonElement.querySelector(".lesson-title").value;

        // Obtener los módulos guardados en localStorage
        let storedModules = JSON.parse(localStorage.getItem("modules")) || [];

        // Recorrer los módulos y eliminar la lección que coincida
        storedModules.forEach(module => {
            module.lessons = module.lessons.filter(lesson => lesson.title !== lessonTitle);
        });

        // Guardar la nueva lista de módulos sin la lección eliminada
        localStorage.setItem("modules", JSON.stringify(storedModules));

        // Eliminar del DOM
        lessonElement.remove();
    }

    // 📌 Función para eliminar módulo y sus lecciones
    function removeModule(moduleElement) {
        moduleElement.remove();
        saveModulesToStorage();
    }

    // 📌 Función para guardar módulos y lecciones en `localStorage`
    function saveModulesToStorage() {
        let modules = [];
        document.querySelectorAll(".module-form").forEach(moduleElement => {
            let moduleData = {
                course: moduleElement.querySelector(".module-course").value,
                title: moduleElement.querySelector(".module-title").value,
                description: moduleElement.querySelector(".module-description").value,
                lessons: []
            };

            moduleElement.querySelectorAll(".lesson-form").forEach(lessonElement => {
                let lessonData = {
                    title: lessonElement.querySelector(".lesson-title").value,
                    type: lessonElement.querySelector(".lesson-type").value,
                    description: lessonElement.querySelector(".lesson-description").value,
                    lessonresource: moduleElement.querySelector(".lesson-resource").value,
                    video_url: lessonElement.querySelector(".lesson-video-url")?.value || ""
                };
                moduleData.lessons.push(lessonData);
            });

            modules.push(moduleData);
        });

        localStorage.setItem("modules", JSON.stringify(modules));
    }

    function loadModulesFromStorage() {
        let storedModules = JSON.parse(localStorage.getItem("modules")) || [];

        // Solo ordenar si el campo created_at existe
        storedModules.sort((a, b) => (b.created_at || 0) - (a.created_at || 0));

        storedModules.forEach(moduleData => addModule(moduleData));
    }


    function generateSummary() {
        let summaryContainer = document.getElementById("summary-container");
        summaryContainer.innerHTML = ""; // Limpiar contenido previo

        // Obtener los datos guardados en localStorage
        let step1Data = JSON.parse(localStorage.getItem("step1")) || {};
        let step2Data = JSON.parse(localStorage.getItem("step2")) || {};
        let modules = JSON.parse(localStorage.getItem("modules")) || [];

        let summaryHTML = `
            <h4>📌 Información del Curso</h4>
            <p><strong>Nombre:</strong> ${step1Data["course_name"] || "No especificado"}</p>
            <p><strong>Descripción:</strong> ${step1Data["course_description"] || "No especificado"}</p>

            <h4>⚙️ Configuración</h4>
            <p><strong>Nivel:</strong> ${step2Data["course_level"] || "No especificado"}</p>
            <p><strong>Categoría:</strong> ${step2Data["course_category"] || "No especificado"}</p>

            <h4>📚 Módulos y Lecciones</h4>

        `;

        if (modules.length === 0) {
            summaryHTML += `<p>No se han agregado módulos.</p>`;
        } else {
            modules.forEach((module, index) => {
                summaryHTML += `
                    <div class="border p-2 mb-2 resumen-card" data-title="${module.title.toLowerCase()}">
                        <h5>🔹 Módulo ${index + 1}: ${module.title}</h5>
                        <p><strong>Descripción:</strong> ${module.description}</p>
                        <p><strong>Lecciones:</strong></p>
                        <ul>
                `;

                if (module.lessons.length === 0) {
                    summaryHTML += `<li>No hay lecciones en este módulo.</li>`;
                } else {
                    module.lessons.forEach(lesson => {
                        summaryHTML += `<li>${lesson.title} - ${lesson.type}`;
                        if (lesson.video_url) {
                            summaryHTML += `<br><small>📺 <a href="${lesson.video_url}" target="_blank">${lesson.video_url}</a></small>`;
                        }
                        summaryHTML += `</li>`;
                    });
                }

                summaryHTML += `</ul></div>`;
            });
        }

        summaryContainer.innerHTML = summaryHTML;

        // 🔍 Activar el filtro justo después de generar el HTML
        const filtroInput = document.getElementById("filtroResumenCursos");
        if (filtroInput) {
            filtroInput.addEventListener("input", function () {
                const filtro = filtroInput.value.toLowerCase();
                const cards = document.querySelectorAll(".resumen-card");

                cards.forEach(card => {
                    const title = card.getAttribute("data-title") || "";
                    card.style.display = title.includes(filtro) ? "" : "none";
                });
            });
        }
    }

    addModuleBtn.addEventListener("click", function () {
        addModule();
    });

    loadModulesFromStorage();


    // Cuando se cargue el documento, verificamos si existe la variable en local storage llamada step1
    if (localStorage.getItem('step1')) {
        var step1 = JSON.parse(localStorage.getItem('step1'));
        if (step1.title) document.getElementById('id_title').value = step1.title;
        if (step1.duration) document.getElementById('id_duration').value = step1.duration;
        if (step1.category) document.getElementById('id_category').value = step1.category;
        if (step1.description) document.getElementById('id_description').value = step1.description;
    }

    if (localStorage.getItem('step2')) {
        var step2 = JSON.parse(localStorage.getItem('step2'));
        // Vamos a llenar el formulario con los datos guardados
        document.getElementById('id_language').value = step2.language;
        document.getElementById('id_level').value = step2.level;
    }
    
    document.addEventListener("DOMContentLoaded", function () {
        document.getElementById("toggleSidebar").addEventListener("click", function () {
            let sidebar = document.getElementById("sidebar");
            if (sidebar) {
                sidebar.classList.toggle("d-none"); // Alterna la visibilidad
            }
        });
    });

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("input[type='radio']").forEach(radio => {
            radio.addEventListener("change", function () {
                saveStepData(2); // Guarda los cambios en el paso 2 cuando se selecciona un radio button
                });
            });
        });    
    });

function cancel_course(route) {
    Swal.fire({
        title: "¿Estás segur@?",
        text: "Esta acción eliminará el curso permanentemente.",
        icon: "warning",
        showCancelButton: true,
        confirmButtonColor: "#d33",
        cancelButtonColor: "#3085d6",
        confirmButtonText: "Sí, eliminar",
        cancelButtonText: "Cancelar"
    }).then((result) => {
        if (result.isConfirmed) {
            // 🔴 Borra todos los datos de cursos en localStorage
            localStorage.removeItem("step1");
            localStorage.removeItem("step2");
            localStorage.removeItem("step3");
            localStorage.removeItem("step4");
            localStorage.removeItem("modules");

            // 🕒 Pequeño retraso para asegurarse de que los datos se eliminan antes de redirigir
            setTimeout(function () {
                window.location.href = route;
            }, 1000);
            
            Swal.fire({
                title: "¡Eliminado!",
                text: "El curso ha sido eliminado exitosamente.",
                icon: "success",
                showConfirmButton: false // ❌ Oculta el botón de "OK"

            });
        }
    });
}

document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("save-button").addEventListener("click", function (event) {
        event.preventDefault(); // Evita el envío automático del formulario

        // Obtener los datos del localStorage
        let step1 = JSON.parse(localStorage.getItem("step1")) || {};
        let step2 = JSON.parse(localStorage.getItem("step2")) || {};
        let modules = JSON.parse(localStorage.getItem("modules")) || [];

        // Convertir a JSON
        let formData = new FormData();
        formData.append("step1", JSON.stringify(step1));
        formData.append("step2", JSON.stringify(step2));
        formData.append("modules", JSON.stringify(modules));

        // ✅ Adjuntar archivo principal del curso
        let portraitInput = document.getElementById("id_portrait");
        if (portraitInput && portraitInput.files.length > 0) {
            formData.append("portrait", portraitInput.files[0]);
        }

        // ✅ Adjuntar archivos de cada lección
        let lessonFiles = document.querySelectorAll(".lesson-resource");
        lessonFiles.forEach((input, index) => {
            if (input.files.length > 0) {
                formData.append(`lesson_resource_${index}`, input.files[0]);  // ← nombre esperable por backend
            }
        });


        // Enviar al backend
        fetch('/courses/api/save-course/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken()  // No pongas 'Content-Type' con FormData
            },
            body: formData
        })

        .then(response => response.json())
        .then(data => {
            console.log("✅ Respuesta del servidor:", data);
            
            if (data.status === "success") {
                Swal.fire({
                    icon: "success",
                    title: "¡Guardado!",
                    text: "El curso se ha guardado correctamente.",
                    timer: 2000,  // Se cierra automáticamente en 2 segundos
                    showConfirmButton: false
                });

                // 🔥 Limpiar localStorage después de guardar con éxito
                localStorage.clear();
                console.log("🗑️ localStorage eliminado.");

                // Redirigir a la página principal de cursos después de 2 segundos
                setTimeout(function () {
                    window.location.href = "/courses/course_wizard";
                }, 2000);
            } else {
                Swal.fire("Error", "No se pudo guardar el curso.", "error");
            }
        })
        .catch(error => {
            console.error("❌ Error en la solicitud AJAX:", error);
            Swal.fire("Error", "Hubo un problema con la conexión.", "error");
        });
    });
});

// 📌 Función para obtener el token CSRF
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}


    // Obtener el valor de la audiencia desde el backend (pasado a través del contexto)
    const audience = "{{ course_config.audience }}";  // Obtén el valor de 'audience' de la configuración del curso
    
    document.addEventListener("DOMContentLoaded", function () {
        const segmentButtonCell = document.getElementById("segment-button-cell");

        // Si la audiencia es 'segmentado', muestra el botón
        if (audience === "segment") {
            segmentButtonCell.style.display = "table-cell";  // Muestra el botón
        } else {
            segmentButtonCell.style.display = "none";  // Oculta el botón
        }
    });

    document.addEventListener("DOMContentLoaded", function () {
        // Obtener los elementos de los radios
        const allUsersRadio = document.getElementById("allUsers");
        const segmentUsersRadio = document.getElementById("segmentUsers");
        const segmentationCard = document.getElementById("segmentationCard");  // Tarjeta de segmentación
    
        // Función para mostrar u ocultar la tarjeta de segmentación
        function toggleSegmentationCard() {
            console.log("Segmentar está seleccionado: ", segmentUsersRadio.checked); // Verifica el estado
    
            if (segmentUsersRadio.checked) {
                segmentationCard.classList.remove("d-none");  // Muestra la tarjeta de segmentación
            } else {
                segmentationCard.classList.add("d-none");  // Oculta la tarjeta de segmentación
            }
        }
    
        // Asegurarse de que los radios están seleccionados al cargar la página
        toggleSegmentationCard();
    
        // Escuchar los cambios en los radios
        allUsersRadio.addEventListener("change", toggleSegmentationCard);
        segmentUsersRadio.addEventListener("change", toggleSegmentationCard);
    });
    
