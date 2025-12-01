// static/js/org_chart.js
$(function () {
  const csrftoken = window.ORGCHART_CSRF;
  const dataUrl = window.ORGCHART_DATA_URL;
  const moveUrl = window.ORGCHART_MOVE_URL;

  $.getJSON(dataUrl, function (datasource) {

    const $container = $('#chart-container');

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
        // guardamos todos los datos para la tarjeta
        $node.data('emp', data);

        // Título
        $node.find('.title').text(data.name || '');

        // Detalles
        let details = [];
        if (data.title) details.push(data.title);
        if (data.department) details.push(data.department);
        if (data.company) details.push(data.company);

        let html = '';

        if (data.photo) {
          html += '<div><img class="avatar" src="' + data.photo + '"></div>';
        }
        if (details.length) {
          html += '<div>' + details.join(' · ') + '</div>';
        }
        if (data.is_vacant) {
          html += '<div style="font-size:11px;color:#ffc107;">VACANTE</div>';
        }

        $node.find('.content').html(html);

        // 🔹 Click en el nodo -> abrir tarjeta
        $node.off('click').on('click', function (e) {
          e.stopPropagation();
          showProfile($(this).data('emp'));
        });
      }
    });

    // Expandir por si algo se colapsa
    $container.orgchart('expandAll');

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

      $('#profile-panel').addClass('open');
    }

    $('#profile-close').on('click', function () {
      $('#profile-panel').removeClass('open');
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

      const containerOffset = $container.offset();
      const nodeOffset = $match.offset();

      const newScrollTop =
        nodeOffset.top - containerOffset.top +
        $container.scrollTop() -
        ($container.height() / 2) +
        ($match.height() / 2);

      const newScrollLeft =
        nodeOffset.left - containerOffset.left +
        $container.scrollLeft() -
        ($container.width() / 2) +
        ($match.width() / 2);

      $container.animate(
        {
          scrollTop: newScrollTop,
          scrollLeft: newScrollLeft
        },
        400
      );
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
      const dropNode = extra.dropZone ? extra.dropZone.closest('.node') : null;

      const draggedId = draggedNode.attr('data-employee-id') || '';
      const newParentId = dropNode && dropNode.length
        ? (dropNode.attr('data-employee-id') || '')
        : '';

      console.log('draggedId:', draggedId, 'newParentId:', newParentId);

      $.ajax({
        url: moveUrl,
        method: "POST",
        headers: { "X-CSRFToken": csrftoken },
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
    console.error("Error cargando organigrama (admin):", err);
  });
});
