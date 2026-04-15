// static/js/org_chart.js
$(function () {
  const csrftoken = window.ORGCHART_CSRF;
  const dataUrl   = window.ORGCHART_DATA_URL;
  const moveUrl   = window.ORGCHART_MOVE_URL;

  // Número de empleado del usuario actual (lo manda Django)
  const myEmpNo   = (window.ORGCHART_ME_EMPLOYEE_NUMBER || '').toString().trim();

  const $container = $('#chart-container');
  let currentProfileId = null;
  let currentScale = 1;
  let oc = null;

  // Mapa plano para búsqueda rápida: id -> nodo, id -> parentId
  const nodeMap   = {};
  const parentMap = {};

  // =====================================================
  //  Construye los mapas planos recorriendo el árbol
  // =====================================================
  function buildMaps(node, parentId) {
    if (!node) return;
    // Nodo raíz virtual (cuando hay múltiples raíces)
    if (node.id === 'ORG_ROOT') {
      (node.children || []).forEach(function (c) { buildMaps(c, null); });
      return;
    }
    nodeMap[node.id] = node;
    parentMap[node.id] = (parentId !== undefined) ? parentId : null;
    (node.children || []).forEach(function (c) { buildMaps(c, node.id); });
  }

  // =====================================================
  //  Construye el árbol de 3 niveles para la búsqueda
  //  Nivel 1: jefe (si existe)
  //  Nivel 2: persona encontrada
  //  Nivel 3: colaboradores directos (sin sus hijos)
  // =====================================================
  function getFilteredTree(matchNode) {
    var parentId = parentMap[matchNode.id];
    var parent   = (parentId !== null && parentId !== undefined) ? nodeMap[parentId] : null;

    // Nodo central: solo sus hijos directos, sin nietos
    var filteredNode = $.extend({}, matchNode, {
      children: (matchNode.children || []).map(function (child) {
        return $.extend({}, child, { children: [] });
      })
    });

    if (parent) {
      // Devolvemos padre con un único hijo: la persona buscada
      return $.extend({}, parent, { children: [filteredNode] });
    }
    return filteredNode;
  }

  // =====================================================
  //  Opciones del orgchart (reutilizadas en renderChart)
  // =====================================================
  function getOrgChartOptions(data) {
    return {
      data: data,
      nodeId: 'id',
      nodeTitle: 'name',
      nodeContent: 'title',
      pan: true,
      zoom: true,
      draggable: !!moveUrl,   // drag sólo en admin (cuando moveUrl está definido)
      createNode: function ($node, nodeData) {
        $node.attr('data-employee-id', nodeData.id);
        if (nodeData.employee_number) {
          $node.attr('data-empno', nodeData.employee_number);
        }
        $node.data('emp', nodeData);

        var photoUrl = nodeData.photo || '/static/template/img/logos/logo_sencillo.png';
        var html = '<div class="avatar-wrapper">';
        html += '  <img class="avatar" src="' + photoUrl + '">';

        var directReports = Array.isArray(nodeData.children) ? nodeData.children.length : 0;
        if (directReports > 0) {
          html += '<div class="direct-reports-badge" title="' + directReports + ' subordinados directos">';
          html += '<span>' + directReports + '</span></div>';
        }
        html += '</div>';
        html += '<div class="node-name">' + (nodeData.name || 'Sin Nombre') + '</div>';
        if (nodeData.title) {
          html += '<div class="node-role">' + nodeData.title + '</div>';
        }

        $node.find('.content').html(html);

        $node.css('cursor', 'pointer').on('click', function (e) {
          if ($(e.target).closest('.oc-btn').length) return;
          $container.find('.node.orgchart-highlight').removeClass('orgchart-highlight');
          $node.addClass('orgchart-highlight');

          var empData = $node.data('emp');
          if ($('#profile-panel').is(':visible') && currentProfileId === empData.id) {
            $('#profile-panel').fadeOut(200);
            currentProfileId = null;
          } else {
            showProfile(empData);
          }
        });
      }
    };
  }

  // =====================================================
  //  Renderiza (o re-renderiza) el organigrama
  // =====================================================
  function renderChart(data, isFiltered, centerNodeId) {
    $container.empty();
    oc = $container.orgchart(getOrgChartOptions(data));
    $container.orgchart('expandAll');

    // Centrar el nodo indicado (o la raíz) después de que el DOM se pinte
    setTimeout(function () {
      var $target;
      if (centerNodeId) {
        $target = $container.find('.node[data-employee-id="' + centerNodeId + '"]').first();
      }
      if (!$target || !$target.length) {
        $target = $container.find('.orgchart .node').first();
      }
      if ($target && $target.length) {
        var newScrollTop  = $target.position().top  + $container.scrollTop()
                          - ($container.height() / 2) + ($target.outerHeight() / 2);
        var newScrollLeft = $target.position().left + $container.scrollLeft()
                          - ($container.width()  / 2) + ($target.outerWidth()  / 2);
        $container.scrollTop(Math.max(0, newScrollTop));
        $container.scrollLeft(Math.max(0, newScrollLeft));
      }
    }, 150);
  }

  // =====================================================
  //  Carga de datos
  // =====================================================
  $.getJSON(dataUrl, function (datasource) {

    buildMaps(datasource, null);

    // Buscar al usuario actual por número de empleado para vista inicial
    var meNode = null;
    if (myEmpNo) {
      $.each(nodeMap, function (id, node) {
        if ((node.employee_number || '').toString().trim() === myEmpNo) {
          meNode = node;
          return false;
        }
      });
    }

    if (meNode) {
      // Vista inicial: jefe → yo → mis subordinados directos, centrado en mí
      renderChart(getFilteredTree(meNode), true, meNode.id);
    } else {
      renderChart(datasource, false, null);
    }

    // ========================
    //  Helper: centrar un nodo
    // ========================
    function scrollToNode($node) {
      if (!$node || !$node.length) return;
      var containerOffset = $container.offset();
      var nodeOffset      = $node.offset();

      var newScrollTop =
        nodeOffset.top - containerOffset.top +
        $container.scrollTop() -
        ($container.height() / 2) +
        ($node.height() / 2);

      var newScrollLeft =
        nodeOffset.left - containerOffset.left +
        $container.scrollLeft() -
        ($container.width() / 2) +
        ($node.width() / 2);

      $container.animate({ scrollTop: newScrollTop, scrollLeft: newScrollLeft }, 400);
    }

    // =========================
    //  Zoom con botones
    // =========================
    function applyScale(scale) {
      currentScale = Math.max(0.3, Math.min(2.0, scale));
      if (typeof window.setChartScale === 'function') {
        window.setChartScale(oc.$chart, currentScale);
      } else {
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
      var $chart = $container.find('.orgchart');
      if (!$chart.length) return;
      var scale = $container.width() / $chart.outerWidth();
      applyScale(Math.max(0.3, Math.min(1.2, scale)));
      scrollToNode($container.find('.orgchart .node:first'));
    });

    // =========================
    //  BOTÓN "IR A MÍ"
    // =========================
    $('#oc-center-me').on('click', function (e) {
      e.preventDefault();
      if (!myEmpNo) return;

      $container.orgchart('expandAll');
      var $me = $container.find('.node[data-empno="' + myEmpNo + '"]').first();
      if (!$me.length) return;

      $container.find('.node.orgchart-highlight').removeClass('orgchart-highlight');
      $me.addClass('orgchart-highlight');
      scrollToNode($me);
    });

    // =========================
    //  TARJETA DE PERFIL
    // =========================
    function showProfile(data) {
      if (!data) return;
      var photo = data.photo || '/static/template/img/logos/logo_sencillo.png';

      $('#profile-name').text(data.name || '');
      $('#profile-photo').attr('src', photo);
      $('#profile-title').text(data.title || '—');
      $('#profile-dept').text(data.department || '—');
      $('#profile-team').text(data.team || '—');
      $('#profile-responsible').text(data.responsible || '—');

      var email = data.email || '';
      if (email) {
        $('#profile-email').text(email).attr('href', 'mailto:' + email);
      } else {
        $('#profile-email').text('').attr('href', '#');
      }
      $('#profile-phone').text(data.phone_number || '');
      $('#profile-empno').text(data.employee_number || '');

      currentProfileId = data.id;
      $('#profile-panel').fadeIn(200);
    }

    $('#profile-close').on('click', function () {
      $('#profile-panel').fadeOut(200);
      currentProfileId = null;
    });

    // =========================
    //  BUSCADOR (vista 3 niveles)
    // =========================
    function focusNodeByName(term) {
      term = (term || '').trim().toLowerCase();
      var $result = $('#orgchart-search-result');

      if (!term) {
        $result.text('Escribe un nombre para buscar.');
        return;
      }

      // Buscar en el mapa de nodos (más rápido y preciso que buscar en el DOM)
      var matchNode = null;
      $.each(nodeMap, function (id, node) {
        if ((node.name || '').toLowerCase().includes(term)) {
          matchNode = node;
          return false; // break
        }
      });

      if (!matchNode) {
        $result.text('No se encontró a nadie con ese nombre.');
        return;
      }

      // Construir árbol de 3 niveles y re-renderizar centrado en la persona
      var filteredTree = getFilteredTree(matchNode);
      renderChart(filteredTree, true, matchNode.id);

      // Resaltar la persona buscada después del render
      setTimeout(function () {
        var $match = $container.find('.node[data-employee-id="' + matchNode.id + '"]').first();
        $container.find('.node.orgchart-highlight').removeClass('orgchart-highlight');
        $match.addClass('orgchart-highlight');
      }, 200);

      var directCount = (matchNode.children || []).length;
      $result.text(
        matchNode.name +
        (directCount > 0 ? ' — ' + directCount + ' colaborador(es) directo(s)' : '')
      );
    }

    $('#orgchart-search-btn').on('click', function () {
      focusNodeByName($('#orgchart-search-input').val());
    });

    $('#orgchart-search-input').on('keypress', function (e) {
      if (e.which === 13) {
        e.preventDefault();
        focusNodeByName($(this).val());
      }
    });

    // =========================
    //  LÓGICA DE ARRASTRAR tarjeta
    // =========================
    var card   = document.getElementById('profile-panel');
    var header = document.querySelector('.profile-panel-header');
    var isDragging = false;
    var offsetX, offsetY;

    if (header && card) {
      header.addEventListener('mousedown', function (e) {
        isDragging = true;
        offsetX = e.clientX - card.getBoundingClientRect().left;
        offsetY = e.clientY - card.getBoundingClientRect().top;
        header.style.cursor = 'grabbing';
      });

      document.addEventListener('mousemove', function (e) {
        if (!isDragging) return;
        e.preventDefault();
        card.style.left = (e.clientX - offsetX) + 'px';
        card.style.top  = (e.clientY - offsetY) + 'px';
        card.style.transform = 'none';
      });

      document.addEventListener('mouseup', function () {
        isDragging = false;
        if (header) header.style.cursor = 'move';
      });
    }

  }).fail(function (err) {
    console.error('Error cargando organigrama:', err);
  });
});
