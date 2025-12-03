// static/js/org_chart.js
$(function () {
  const csrftoken = window.ORGCHART_CSRF;
  const dataUrl   = window.ORGCHART_DATA_URL;
  const moveUrl   = window.ORGCHART_MOVE_URL;

  // Número de empleado del usuario actual (lo manda Django)
  const myEmpNo   = (window.ORGCHART_ME_EMPLOYEE_NUMBER || '').toString().trim();

  $.getJSON(dataUrl, function (datasource) {

    const $container = $('#chart-container');
    let currentProfileId = null;
    let currentScale = 1;

    // =========================
    //  Inicializar organigrama
    // =========================
    const oc = $container.orgchart({
      data: datasource,
      nodeId: 'id',
      nodeTitle: 'name',
      nodeContent: 'title',
      pan: true,
      zoom: true,
      draggable: true,
      createNode: function ($node, data) {
        // ID de empleado en el DOM
        $node.attr('data-employee-id', data.id);

        // número de empleado para "ir a mí"
        if (data.employee_number) {
          $node.attr('data-empno', data.employee_number);
        }

        // guardamos todos los datos para la tarjeta
        $node.data('emp', data);

        // Título (nombre)
        $node.find('.title').text(data.name || '');

        // Contenido (solo foto + badge)
        let html = '';

        // Foto
        if (data.photo) {
          html += '<div><img class="avatar" src="' + data.photo + '"></div>';
        }

        // 🔹 SUBORDINADOS DIRECTOS (children del nodo)
        const directReports = Array.isArray(data.children) ? data.children.length : 0;
        if (directReports > 0) {
          html += `
            <div class="direct-reports-badge">
              <i class="fas fa-users"></i>
              <span>${directReports}</span>
            </div>
          `;
        }

        $node.find('.content').html(html);

        // 🔹 Click en título/contenido -> toggle del panel
        $node.find('.title, .content')
          .css('cursor', 'pointer')
          .on('click', function (e) {
            e.stopPropagation(); // que no colapse/expand el orgchart

            const empData = $node.data('emp');

            // si ya está abierto el panel con este mismo id, lo cerramos
            if ($('#profile-panel').hasClass('open') && currentProfileId === empData.id) {
              $('#profile-panel').removeClass('open');
              currentProfileId = null;
            } else {
              showProfile(empData);
            }
          });
      }
    });

    // Expandir todo al inicio
    $container.orgchart('expandAll');

    // =========================
    //  Helper: centrar un nodo
    // =========================
    function scrollToNode($node) {
      if (!$node || !$node.length) return;

      const containerOffset = $container.offset();
      const nodeOffset      = $node.offset();

      const newScrollTop =
        nodeOffset.top - containerOffset.top +
        $container.scrollTop() -
        ($container.height() / 2) +
        ($node.height() / 2);

      const newScrollLeft =
        nodeOffset.left - containerOffset.left +
        $container.scrollLeft() -
        ($container.width() / 2) +
        ($node.width() / 2);

      $container.animate(
        { scrollTop: newScrollTop, scrollLeft: newScrollLeft },
        400
      );
    }

    // =========================
    //  Zoom con botones
    // =========================
    function applyScale(scale) {
      currentScale = Math.max(0.3, Math.min(2.0, scale));  // límites

      // El plugin expone setChartScale($chart, newScale) como función global
      if (typeof window.setChartScale === 'function') {
        window.setChartScale(oc.$chart, currentScale);
      } else {
        // fallback por si acaso: CSS transform
        oc.$chart.css('transform', 'scale(' + currentScale + ')');
      }
    }

    $('#oc-zoom-in').on('click', function (e) {
      e.preventDefault();
      applyScale(currentScale + 0.1);
    });

    $('#oc-zoom-out').on('click', function (e) {
      e.preventDefault();
      applyScale(currentScale - 0.1);
    });

    $('#oc-fit').on('click', function (e) {
      e.preventDefault();

      const $chart = $container.find('.orgchart');
      if (!$chart.length) return;

      const containerWidth = $container.width();
      const chartWidth     = $chart.outerWidth();

      if (!containerWidth || !chartWidth) return;

      // escala aproximada para que quepa de ancho
      const scale = containerWidth / chartWidth;
      applyScale(Math.max(0.3, Math.min(1.2, scale)));

      // centrar la raíz
      const $root = $container.find('.orgchart .node:first');
      scrollToNode($root);
    });

    // =========================
    //  BOTÓN "IR A MÍ"
    // =========================
    $('#oc-center-me').on('click', function (e) {
      e.preventDefault();

      if (!myEmpNo) {
        console.warn('ORGCHART_ME_EMPLOYEE_NUMBER no está definido');
        return;
      }

      // aseguramos todo expandido
      $container.orgchart('expandAll');

      const $me = $container
        .find('.node[data-empno="' + myEmpNo + '"]')
        .first();

      if (!$me.length) {
        console.warn('No se encontró nodo para el número de empleado', myEmpNo);
        return;
      }

      // resaltar
      $container.find('.node.orgchart-highlight').removeClass('orgchart-highlight');
      $me.addClass('orgchart-highlight');

      scrollToNode($me);
    });

    // =========================
    //  FUNCIÓN TARJETA
    // =========================
    function showProfile(data) {
      if (!data) return;

      const photo = data.photo || '/static/template/img/logos/logo_sencillo.png';
      $('#profile-name').text(data.name || '');
      $('#profile-photo').attr('src', photo);
      $('#profile-title').text(data.title || '');
      $('#profile-dept').text(data.department || '');
      $('#profile-company').text(data.company || '');
      $('#profile-team').text(data.team || '');
      $('#profile-responsible').text(data.responsible || '');

      const email = data.email || '';
      if (email) {
        $('#profile-email')
          .text(email)
          .attr('href', 'mailto:' + email);
      } else {
        $('#profile-email').text('').attr('href', '#');
      }

      $('#profile-phone').text(data.phone_number || '');
      $('#profile-empno').text(data.employee_number || '');

      currentProfileId = data.id;
      $('#profile-panel').addClass('open');
    }

    $('#profile-close').on('click', function () {
      $('#profile-panel').removeClass('open');
      currentProfileId = null;
    });

    // =========================
    //  BUSCADOR
    // =========================
    function focusNodeByName(term) {
      term = (term || '').trim().toLowerCase();
      const $result = $('#orgchart-search-result');

      if (!term) {
        $result.text('Escribe un nombre para buscar.');
        return;
      }

      $container.orgchart('expandAll');

      const $nodes = $container.find('.node');
      let $match = null;

      $nodes.each(function () {
        const text = $(this).find('.title').text().trim().toLowerCase();
        if (text.includes(term)) {
          $match = $(this);
          return false;
        }
      });

      if (!$match) {
        $result.text('No se encontró a nadie con ese nombre.');
        return;
      }

      $result.text('');
      $container.find('.node.orgchart-highlight').removeClass('orgchart-highlight');
      $match.addClass('orgchart-highlight');

      scrollToNode($match);
    }

    $('#orgchart-search-btn').on('click', function () {
      const term = $('#orgchart-search-input').val();
      focusNodeByName(term);
    });

    $('#orgchart-search-input').on('keypress', function (e) {
      if (e.which === 13) {
        e.preventDefault();
        const term = $(this).val();
        focusNodeByName(term);
      }
    });

    // =========================
    //  DRAG & DROP -> API
    // =========================
    oc.$chart.on('nodedrop.orgchart', function (event, extra) {
      const draggedNode = extra.draggedNode.closest('.node');
      const dropNode    = extra.dropZone ? extra.dropZone.closest('.node') : null;

      const draggedId   = draggedNode.attr('data-employee-id') || '';
      const newParentId = dropNode && dropNode.length
        ? (dropNode.attr('data-employee-id') || '')
        : '';

      console.log('draggedId:', draggedId, 'newParentId:', newParentId);

      $.ajax({
        url: moveUrl,
        method: 'POST',
        headers: { 'X-CSRFToken': csrftoken },
        data: {
          moved_position_id: draggedId,
          new_parent_id: newParentId
        },
        success: function (resp) {
          console.log('API OK:', resp);
        },
        error: function (xhr) {
          console.error('API ERROR', xhr.status, xhr.responseText);
        }
      });
    });

  }).fail(function (err) {
    console.error('Error cargando organigrama (admin):', err);
  });
});
