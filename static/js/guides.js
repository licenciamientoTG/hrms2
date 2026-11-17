/**
 * Sistema de Guías Interactivas - HRMS
 * Usa Driver.js para tours interactivos paso a paso.
 * Los tours permiten interacción real (clics, navegación) sin ejecutar acciones finales.
 */

var _driverObj = null;

var HRMS_GUIDES = [
  // ── Guías generales ──
  {
    id: 'cambiar_password_propio',
    title: 'Cambiar mi contraseña',
    description: 'Aprende cómo cambiar tu propia contraseña del sistema.',
    icon: 'fa-lock',
    category: 'general',
    requiredPerms: [],
    requiredStaff: false,
    pages: [
      {
        path: null, // cualquier página
        steps: [
          {
            element: '#settingsDropdown',
            popover: {
              title: 'Paso 1: Configuración',
              description: 'Haz clic en el ícono de <b>engranaje</b> para abrir el menú.',
              side: 'bottom', align: 'end',
            },
            interactive: true,
            opensDropdown: true,
          },
          {
            element: '#menu-cambiar-password',
            popover: {
              title: 'Paso 2: Cambiar contraseña',
              description: 'Haz clic en <b>"Cambiar contraseña"</b> para ir al formulario.',
              side: 'bottom', align: 'end',
            },
            interactive: true,
            navigates: true,
          },
        ]
      },
      {
        path: '/auth/accounts/password_change/',
        steps: [
          {
            element: '#field-old-password',
            popover: {
              title: 'Paso 3: Contraseña actual',
              description: 'Escribe tu <b>contraseña actual</b> para verificar tu identidad.',
              side: 'right', align: 'start',
            }
          },
          {
            element: '#field-new-password',
            popover: {
              title: 'Paso 4: Nueva contraseña',
              description: 'Escribe la <b>nueva contraseña</b> que deseas usar.',
              side: 'right', align: 'start',
            }
          },
          {
            element: '#field-confirm-password',
            popover: {
              title: 'Paso 5: Confirmar contraseña',
              description: 'Vuelve a escribir la nueva contraseña para <b>confirmarla</b>.',
              side: 'right', align: 'start',
            }
          },
          {
            element: '#btn-submit-password',
            popover: {
              title: 'Paso 6: Guardar',
              description: 'Cuando hayas llenado los campos, haz clic en <b>"Actualizar contraseña"</b> para guardar el cambio.<br><br><i class="fa-solid fa-circle-info text-info"></i> <em>La guía termina aquí. Puedes hacerlo ahora o después.</em>',
              side: 'top', align: 'start',
            }
          },
        ]
      }
    ]
  },
  // ── Navegar por los módulos ──
  {
    id: 'navegar_modulos',
    title: 'Navegar por los módulos',
    description: 'Conoce las partes principales de la interfaz y cómo moverte por el sistema.',
    icon: 'fa-compass',
    category: 'general',
    requiredPerms: [],
    requiredStaff: false,
    pages: [
      {
        path: null,
        steps: [
          {
            element: '.js-sidebar-toggle',
            skipIf: function () {
              var sidebar = document.getElementById('sidebar');
              if (!sidebar) return false;
              var rect = sidebar.getBoundingClientRect();
              return rect.right > 50; // ya está visible, saltar este paso
            },
            popover: {
              title: 'Abrir el menú',
              description: 'El menú lateral está oculto. Haz clic en este botón para <b>desplegarlo</b> y ver los módulos del sistema.',
              side: 'bottom', align: 'start',
            },
            interactive: true,
            clickAndWait: 450,
          },
          {
            element: '#sidebar',
            popover: {
              title: 'Menú lateral',
              description: 'Este es el <b>menú lateral</b>. Desde aquí accedes a todos los módulos disponibles según tu perfil. Los módulos que ves dependen de los permisos de tu puesto.',
              side: 'right', align: 'start',
            },
          },
          {
            element: '.sidebar-nav',
            popover: {
              title: 'Lista de módulos',
              description: 'Cada elemento de la lista es un <b>módulo del sistema</b>. Haz clic en cualquiera para abrirlo. Si aparece un <span class="badge bg-danger">número</span> rojo, significa que tienes elementos pendientes de atender en ese módulo.',
              side: 'right', align: 'start',
            },
          },
          {
            element: '#alertsDropdown',
            popover: {
              title: 'Notificaciones',
              description: 'La <b>campana</b> muestra tus notificaciones recientes: nuevos cursos, comunicados, solicitudes, entre otros. El punto rojo indica que tienes notificaciones sin leer.',
              side: 'bottom', align: 'end',
            },
          },
          {
            element: '#settingsDropdown',
            popover: {
              title: 'Configuración',
              description: 'El <b>engranaje</b> abre el menú de configuración, donde puedes cambiar tu contraseña o ajustar el tamaño de la interfaz.',
              side: 'bottom', align: 'end',
            },
          },
          {
            element: '#nav-user-dropdown',
            popover: {
              title: 'Tu perfil y sesión',
              description: 'Haz clic en tu nombre para acceder a <b>Mi Perfil</b> o para <b>cerrar sesión</b> de forma segura.<br><br><i class="fa-solid fa-circle-info text-info"></i> <em>¡Listo! Ya conoces las partes principales del sistema.</em>',
              side: 'bottom', align: 'end',
            },
          },
        ]
      },
    ]
  },

  // ── Ver el organigrama ──
  {
    id: 'ver_organigrama',
    title: 'Ver el organigrama',
    description: 'Aprende a navegar la estructura organizacional de la empresa.',
    icon: 'fa-sitemap',
    category: 'general',
    requiredPerms: [],
    requiredStaff: false,
    pages: [
      {
        path: null,
        steps: [
          {
            element: '#sidebar-link-organigrama',
            popover: {
              title: 'Paso 1: Acceder al organigrama',
              description: 'En el menú lateral encontrarás el módulo <b>Organigrama</b>. Haz clic aquí para abrirlo.',
              side: 'right', align: 'start',
            },
            interactive: true,
            navigates: true,
          },
        ]
      },
      {
        path: '/org_chart/',
        steps: [
          {
            element: '#orgchart-search-input',
            popover: {
              title: 'Paso 2: Buscar un colaborador',
              description: 'Puedes escribir el nombre de cualquier colaborador para localizarlo dentro del organigrama.',
              side: 'bottom', align: 'start',
            },
          },
          {
            element: '#orgchart-search-btn',
            popover: {
              title: 'Paso 3: Ejecutar la búsqueda',
              description: 'Haz clic en <b>Buscar</b> y el organigrama se moverá automáticamente al colaborador encontrado.',
              side: 'bottom', align: 'start',
            },
          },
          {
            element: '#oc-center-me',
            popover: {
              title: 'Paso 4: Ir a mi posición',
              description: 'Este botón centra el organigrama en <b>tu propia tarjeta</b>, útil para ubicarte rápidamente.',
              side: 'left', align: 'start',
            },
          },
          {
            element: '#oc-toggle-peers',
            popover: {
              title: 'Paso 5: Mostrar / ocultar compañeros',
              description: 'Con este botón puedes <b>mostrar u ocultar</b> a los compañeros que tienen el mismo jefe directo que tú.',
              side: 'left', align: 'start',
            },
          },
          {
            element: '#oc-zoom-in',
            popover: {
              title: 'Paso 6: Zoom',
              description: 'Usa los botones <b>+ / −</b> para acercar o alejar el organigrama, y el botón de <b>expandir</b> para ajustarlo a la pantalla.<br><br><i class="fa-solid fa-circle-info text-info"></i> <em>También puedes hacer clic en cualquier tarjeta para ver el perfil del colaborador.</em>',
              side: 'left', align: 'start',
            },
          },
        ]
      },
    ]
  },
];


/* ═══════════════════════════════════════
   Filtrar guías según permisos del usuario
   ═══════════════════════════════════════ */

function getAvailableGuides() {
  var user = window.HRMS_USER || {};
  var perms = user.perms || {};

  return HRMS_GUIDES.filter(function (guide) {
    if (guide.requiredStaff && !user.isStaff) return false;

    if (guide.requiredPerms && guide.requiredPerms.length > 0) {
      for (var i = 0; i < guide.requiredPerms.length; i++) {
        if (!perms[guide.requiredPerms[i]]) return false;
      }
    }
    return true;
  });
}


/* ═══════════════════════════════════════
   Modal de selección de guías
   ═══════════════════════════════════════ */

function openGuidesModal() {
  var existing = document.getElementById('guides-modal');
  if (existing) existing.remove();

  var availableGuides = getAvailableGuides();

  if (availableGuides.length === 0) {
    Swal.fire({
      icon: 'info',
      title: 'Sin guías disponibles',
      text: 'No hay guías disponibles para tu perfil de usuario.',
      confirmButtonText: 'Entendido',
    });
    return;
  }

  var adminGuides = availableGuides.filter(function (g) { return g.category === 'admin'; });
  var generalGuides = availableGuides.filter(function (g) { return g.category === 'general'; });

  function buildItems(guides) {
    return guides.map(function (guide) {
      return '<a href="#" class="list-group-item list-group-item-action guide-item" data-guide-id="' + guide.id + '">'
        + '<div class="d-flex align-items-center">'
        + '<div class="me-3"><i class="fa-solid ' + guide.icon + ' fa-lg text-primary"></i></div>'
        + '<div>'
        + '<h6 class="mb-1">' + guide.title + '</h6>'
        + '<small class="text-muted">' + guide.description + '</small>'
        + '</div>'
        + '</div>'
        + '</a>';
    }).join('');
  }

  var body = '';
  if (adminGuides.length > 0) {
    body += '<div class="px-3 pt-3 pb-1"><small class="text-uppercase fw-bold text-secondary"><i class="fa-solid fa-shield-halved me-1"></i>Administración</small></div>';
    body += '<div class="list-group list-group-flush">' + buildItems(adminGuides) + '</div>';
  }
  if (generalGuides.length > 0) {
    body += '<div class="px-3 pt-3 pb-1"><small class="text-uppercase fw-bold text-secondary"><i class="fa-solid fa-user me-1"></i>General</small></div>';
    body += '<div class="list-group list-group-flush">' + buildItems(generalGuides) + '</div>';
  }

  var html = ''
    + '<div class="modal fade" id="guides-modal" tabindex="-1" aria-hidden="true">'
    + '<div class="modal-dialog modal-dialog-centered">'
    + '<div class="modal-content">'
    + '<div class="modal-header">'
    + '<h5 class="modal-title"><i class="fa-solid fa-book-open me-2"></i>Guías del sistema</h5>'
    + '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button>'
    + '</div>'
    + '<div class="modal-body p-0">'
    + '<div class="p-3 bg-light border-bottom">'
    + '<small class="text-muted">Selecciona una guía. Te irá indicando paso a paso dónde hacer clic. Podrás interactuar con el sistema de forma real durante la guía.</small>'
    + '</div>'
    + body
    + '</div>'
    + '</div>'
    + '</div>'
    + '</div>';

  document.body.insertAdjacentHTML('beforeend', html);

  var modal = new bootstrap.Modal(document.getElementById('guides-modal'));
  modal.show();

  document.querySelectorAll('.guide-item').forEach(function (item) {
    item.addEventListener('click', function (e) {
      e.preventDefault();
      var guideId = this.getAttribute('data-guide-id');
      modal.hide();
      setTimeout(function () { startGuide(guideId, 0, 0); }, 400);
    });
  });
}


/* ═══════════════════════════════════════
   Motor de guías interactivas
   ═══════════════════════════════════════ */

function startGuide(guideId, pageIndex, stepIndex) {
  var guide = HRMS_GUIDES.find(function (g) { return g.id === guideId; });
  if (!guide) return;

  var page = guide.pages[pageIndex];
  if (!page) return;

  var currentPath = window.location.pathname;

  // Si la página requiere un path específico y no estamos ahí, navegar
  if (page.path && !currentPath.startsWith(page.path)) {
    sessionStorage.setItem('hrms_guide_state', JSON.stringify({
      id: guideId,
      pageIndex: pageIndex,
      stepIndex: stepIndex
    }));
    window.location.href = page.path;
    return;
  }

  // Filtrar pasos con skipIf (ej. hamburguesa cuando el sidebar ya está abierto)
  var steps = page.steps.filter(function (s) {
    return !s.skipIf || !s.skipIf();
  });

  var totalStepsAllPages = 0;
  var stepsBeforeThisPage = 0;
  for (var p = 0; p < guide.pages.length; p++) {
    // Contar solo los pasos que no se saltan
    var pageSteps = guide.pages[p].steps.filter(function (s) {
      return !s.skipIf || !s.skipIf();
    });
    totalStepsAllPages += pageSteps.length;
    if (p < pageIndex) stepsBeforeThisPage += pageSteps.length;
  }

  // Construir los steps para Driver.js
  var driverSteps = steps.map(function (step, idx) {
    var globalIdx = stepsBeforeThisPage + idx;
    var driverStep = {
      popover: {
        title: step.popover.title,
        description: step.popover.description
          + '<div class="mt-2 text-muted" style="font-size:0.8em;">Paso ' + (globalIdx + 1) + ' de ' + totalStepsAllPages + '</div>',
        side: step.popover.side,
        align: step.popover.align,
      }
    };

    if (step.element) {
      driverStep.element = step.element;
    }

    return driverStep;
  });

  _driverObj = window.driver.js.driver({
    showProgress: false,
    animate: true,
    overlayColor: 'black',
    overlayOpacity: 0.6,
    stagePadding: 10,
    stageRadius: 8,
    allowClose: true,
    allowKeyboardControl: true,
    disableActiveInteraction: false,
    doneBtnText: (pageIndex < guide.pages.length - 1) ? 'Continuar →' : 'Finalizar',
    closeBtnText: 'Cerrar',
    nextBtnText: 'Siguiente →',
    prevBtnText: '← Anterior',
    steps: driverSteps,
    onNextClick: function (el, step, opts) {
      var activeIdx = _driverObj.getActiveIndex();
      var stepDef = steps[activeIdx];

      // Si el paso abre un dropdown, abrirlo y avanzar
      if (stepDef && stepDef.opensDropdown && el) {
        el.click();
        setTimeout(function () { _driverObj.moveNext(); }, 350);
        return;
      }

      // Si el paso hace clic y espera (ej. hamburguesa que abre sidebar)
      if (stepDef && stepDef.clickAndWait && el) {
        el.click();
        setTimeout(function () { _driverObj.moveNext(); }, stepDef.clickAndWait);
        return;
      }

      // Si el paso navega a otra página, guardar estado y navegar
      if (stepDef && stepDef.navigates && el) {
        var href = el.getAttribute('href');
        if (href) {
          sessionStorage.setItem('hrms_guide_state', JSON.stringify({
            id: guideId,
            pageIndex: pageIndex + 1,
            stepIndex: 0
          }));
          _driverObj.destroy();
          window.location.href = href;
          return;
        }
      }

      // Avance normal
      if (_driverObj.isLastStep()) {
        if (pageIndex < guide.pages.length - 1) {
          _driverObj.destroy();
          startGuide(guideId, pageIndex + 1, 0);
        } else {
          _driverObj.destroy();
        }
      } else {
        _driverObj.moveNext();
      }
    },
    onCloseClick: function () {
      _driverObj.destroy();
      sessionStorage.removeItem('hrms_guide_state');
    },
    onDestroyStarted: function () {
      _driverObj.destroy();
    }
  });

  _driverObj.drive(stepIndex);
}


/* ═══════════════════════════════════════
   Reanudar guía al cargar la página
   ═══════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', function () {
  var stateStr = sessionStorage.getItem('hrms_guide_state');
  if (!stateStr) return;

  sessionStorage.removeItem('hrms_guide_state');

  try {
    var state = JSON.parse(stateStr);
    setTimeout(function () {
      startGuide(state.id, state.pageIndex, state.stepIndex);
    }, 600);
  } catch (e) {
    // Estado inválido, ignorar
  }
});
