// static/js/org_chart.js
$(function () {
  const csrftoken      = window.ORGCHART_CSRF;
  const dataUrl        = window.ORGCHART_DATA_URL;
  const moveUrl        = window.ORGCHART_MOVE_URL;
  const reorderUrl      = window.ORGCHART_REORDER_URL       || null;
  const viewStateUrl    = window.ORGCHART_VIEW_STATE_URL    || null;
  const nodeYOffsetUrl  = window.ORGCHART_NODE_Y_OFFSET_URL || null;
  const isSuperuser     = !!window.ORGCHART_IS_SUPERUSER;

  // Número de empleado del usuario actual (lo manda Django)
  const myEmpNo   = (window.ORGCHART_ME_EMPLOYEE_NUMBER || '').toString().trim();

  const $container = $('#chart-container');
  let currentProfileId = null;
  let currentScale = 1;
  let oc = null;

  // Mapa plano para búsqueda rápida: id -> nodo, id -> parentId
  const nodeMap   = {};
  const parentMap = {};

  // Toggle: mostrar iguales (compañeros del mismo jefe)
  let showPeers = false;

  // Nodo actualmente en foco (el que se muestra como principal en el árbol)
  let currentFocusNode = null;

  // =====================================================
  //  Estado de vista (posición del canvas)
  // =====================================================
  let savedViewState   = null;
  let viewSaveTimer    = null;

  // Offsets verticales por nodo: { "123": 80, "45": 40, ... }
  let nodeYOffsets = {};

  // Copia completa del datasource para re-renderizar tras reordenar
  var fullDatasource = null;

  // Variables para el pan personalizado
  let isPanning      = false;
  let panStartX      = 0;
  let panStartY      = 0;
  let panStartLeft   = 0;
  let panStartTop    = 0;

  function getChartPosition() {
    return {
      chart_left: $container.scrollLeft(),
      chart_top:  $container.scrollTop(),
      scale: currentScale
    };
  }

  function applyChartPosition(state) {
    if (!state) return;
    currentScale = state.scale || 1;
    if (oc && oc.$chart) {
      oc.$chart.css('transform', 'scale(' + currentScale + ')');
    }
    $container.scrollLeft(state.chart_left || 0);
    $container.scrollTop(state.chart_top   || 0);
  }

  // =====================================================
  //  Aplica desplazamiento vertical a nodos específicos
  //  Funciona añadiendo padding-top al <td> contenedor
  //  de cada nodo, lo que "estira" visualmente el cable
  //  sin cambiar la jerarquía.
  // =====================================================
  // =====================================================
  //  Aplica el offset vertical a un <td> dibujando una
  //  línea visual de conexión en lugar de usar padding-top.
  //  Así el nodo baja pero la línea conectora lo sigue.
  // =====================================================
  function setTdYOffset($td, px) {
    px = Math.max(0, Math.round(px));
    $td.attr('data-y-offset', px);
    $td.css('padding-top', '0');
    var $conn = $td.find('> .oc-y-connector');
    if (px > 0) {
      if ($conn.length) {
        $conn.css('height', px + 'px');
      } else {
        $('<div class="oc-y-connector"></div>')
          .css('height', px + 'px')
          .prependTo($td);
      }
    } else {
      $conn.remove();
    }
  }

  function applyNodeYOffsets(offsets) {
    if (!offsets) return;
    $.each(offsets, function (empId, px) {
      if (!px) return;
      var $node = $container.find('.node[data-employee-id="' + empId + '"]').first();
      if (!$node.length) return;
      // Subir al <td> contenedor en la fila de hijos del padre
      var $td = $node.closest('table').closest('td');
      if ($td.length) {
        setTdYOffset($td, px);
      }
    });
  }

  // =====================================================
  //  Drag vertical de nodos (solo superadmin)
  //  Al arrastrar hacia arriba/abajo, ajusta el offset
  //  del <td> contenedor y guarda el offset en el servidor.
  // =====================================================
  var yDragSaveTimer = null;

  function saveNodeYOffset(empId, px) {
    if (!nodeYOffsetUrl || !csrftoken) return;
    clearTimeout(yDragSaveTimer);
    yDragSaveTimer = setTimeout(function () {
      nodeYOffsets[empId] = px;
      $.ajax({
        url: nodeYOffsetUrl,
        method: 'POST',
        contentType: 'application/json',
        headers: { 'X-CSRFToken': csrftoken },
        data: JSON.stringify({ employee_id: empId, offset: px })
      });
    }, 600);
  }

  function setupNodeYDrag() {
    if (!isSuperuser) return;

    // Limpiar handlers previos (evita duplicados al re-renderizar)
    $container.off('mousedown.ydrag');
    $(document).off('mousemove.ydrag mouseup.ydrag');

    var yDragActive      = false;
    var yDragEmpId       = null;
    var yDragStartY      = 0;
    var yDragStartOffset = 0;
    var $yDragTd         = null;

    $container.on('mousedown.ydrag', '.node', function (e) {
      if (!e.altKey || e.which !== 1) return;
      var $td = $(this).closest('table').closest('td');
      if (!$td.length) return;   // nodo raíz, sin <td> contenedor

      e.stopPropagation();
      e.preventDefault();

      yDragActive      = true;
      yDragEmpId       = $(this).attr('data-employee-id');
      yDragStartY      = e.clientY;
      $yDragTd         = $td;
      yDragStartOffset = parseInt($td.attr('data-y-offset') || '0', 10);
      $container.css('cursor', 'ns-resize');
    });

    $(document).on('mousemove.ydrag', function (e) {
      if (!yDragActive || !$yDragTd) return;
      var dy        = e.clientY - yDragStartY;
      var newOffset = Math.max(0, yDragStartOffset + dy);
      setTdYOffset($yDragTd, newOffset);
    });

    $(document).on('mouseup.ydrag', function () {
      if (!yDragActive) return;
      yDragActive = false;
      $container.css('cursor', 'grab');
      var finalOffset = parseInt($yDragTd ? $yDragTd.attr('data-y-offset') || '0' : '0', 10);
      saveNodeYOffset(yDragEmpId, finalOffset);
      $yDragTd = null;
    });
  }

  function saveViewState() {
    if (!isSuperuser || !viewStateUrl || !csrftoken) return;
    clearTimeout(viewSaveTimer);
    viewSaveTimer = setTimeout(function () {
      var state = getChartPosition();
      $.ajax({
        url: viewStateUrl,
        method: 'POST',
        contentType: 'application/json',
        headers: { 'X-CSRFToken': csrftoken },
        data: JSON.stringify(state)
      });
    }, 800);
  }

  // =====================================================
  //  Pan personalizado (reemplaza pan:true de orgchart
  //  que conflictúa con draggable:true de jQuery UI)
  // =====================================================
  function setupCustomPan() {
    $container.off('mousedown.orgpan');
    $(document).off('mousemove.orgpan mouseup.orgpan');

    $container.css('cursor', 'grab');

    $container.on('mousedown.orgpan', function (e) {
      if ($(e.target).closest('.oc-btn, #profile-panel').length) return;
      // Arrastra un nodo solo si es superuser con draggable activo — en ese caso
      // el movimiento pequeño se interpreta como click; uno grande como drag de nodo.
      // Para pan siempre iniciamos, luego el threshold decide.
      isPanning    = false;   // se confirmará al mover más de 5px
      panStartX    = e.clientX;
      panStartY    = e.clientY;
      panStartLeft = $container.scrollLeft();
      panStartTop  = $container.scrollTop();
    });

    $(document).on('mousemove.orgpan', function (e) {
      var dx = e.clientX - panStartX;
      var dy = e.clientY - panStartY;
      if (!isPanning && (Math.abs(dx) > 5 || Math.abs(dy) > 5) && panStartX !== 0) {
        // Solo activar pan si NO es un nodo siendo arrastrado (draggable)
        if (!$(e.target).closest('.node').length) {
          isPanning = true;
          $container.css('cursor', 'grabbing');
        }
      }
      if (!isPanning) return;
      $container.scrollLeft(panStartLeft - dx);
      $container.scrollTop(panStartTop  - dy);
    });

    $(document).on('mouseup.orgpan', function () {
      if (isPanning) {
        isPanning = false;
        $container.css('cursor', 'grab');
        if (isSuperuser) saveViewState();
      }
      panStartX = 0;
    });
  }

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
  //  Nivel 2: persona encontrada (+ iguales si showPeers)
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
      var childrenToShow;
      if (showPeers) {
        // Todos los hijos del jefe: iguales sin subordinados + yo con subordinados directos
        childrenToShow = (parent.children || []).map(function (sibling) {
          if (sibling.id === matchNode.id) return filteredNode;
          return $.extend({}, sibling, { children: [] });
        });
      } else {
        childrenToShow = [filteredNode];
      }
      return $.extend({}, parent, { children: childrenToShow });
    }
    return filteredNode;
  }

  // =====================================================
  //  Tarjeta de perfil (debe estar en el scope externo
  //  para que el click handler de createNode la encuentre)
  // =====================================================
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

  // =====================================================
  //  Helpers para el drag & drop de reordenamiento
  // =====================================================

  // Devuelve el id numérico del nodo a partir del elemento DOM .node
  function getNodeId($node) {
    return $node.attr('data-employee-id');
  }

  // Devuelve los hermanos del nodo en el DOM (misma fila del orgchart)
  // jquery.orgchart genera: table > tr > td.node (por cada hermano)
  function getSiblingIds($node) {
    // En jquery.orgchart los hermanos comparten la misma <tr> de la tabla padre
    var $siblings = $node.closest('td').siblings('td').addBack()
      .map(function () { return $(this).find('> .node').first(); })
      .filter(function () { return $(this).length && getNodeId($(this)); });

    var ids = [];
    $siblings.each(function () {
      var id = getNodeId($(this));
      if (id) ids.push(id);
    });
    return ids;
  }

  // Obtiene el id del padre de un nodo en el DOM
  function getParentNodeId($node) {
    // El padre está en el <tr> de arriba → la celda del conector → la tabla de arriba → el nodo padre
    var $parentNode = $node.closest('table').closest('td').closest('tr').closest('table')
      .closest('td').closest('tr').prev('tr')
      .find('> td > .node').first();
    return getNodeId($parentNode) || null;
  }

  function getOrgChartOptions(data) {
    return {
      data: data,
      nodeId: 'id',
      nodeTitle: 'name',
      nodeContent: 'title',
      pan: false,  // deshabilitado — usamos setupCustomPan()
      zoom: true,
      draggable: false,  // requiere jQuery UI que no está cargado
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
    setupCustomPan();
    setupNodeYDrag();
    // Aplicar offsets verticales solo cuando se muestran compañeros
    if (showPeers && Object.keys(nodeYOffsets).length > 0) {
      applyNodeYOffsets(nodeYOffsets);
    }

    // Centrar el nodo indicado (o la raíz) via scroll
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
  //  Carga del estado de vista (independiente, no bloquea el chart)
  // =====================================================
  if (viewStateUrl) {
    $.ajax({
      url: viewStateUrl,
      method: 'GET',
      dataType: 'json',
      success: function (s) {
        savedViewState = s;
        if (s.node_y_offsets && typeof s.node_y_offsets === 'object') {
          nodeYOffsets = s.node_y_offsets;
        }
        // Si el chart ya está renderizado cuando llega la respuesta,
        // aplicar los offsets inmediatamente (cubre el caso donde el AJAX
        // llega después del timeout de 400ms)
        if (showPeers && Object.keys(nodeYOffsets).length > 0 && $container.find('.node').length > 0) {
          applyNodeYOffsets(nodeYOffsets);
        }
      },
      error: function () { /* ignorar si falla */ }
    });
  }

  // =====================================================
  //  Carga de datos
  // =====================================================
  $.getJSON(dataUrl, function (datasource) {
    fullDatasource = datasource;
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

    // Ocultar el container antes del primer render para evitar el flash
    // de estados intermedios (escala 1 → escala guardada, scroll → scroll guardado)
    $container.css('opacity', '0');

    if (meNode) {
      currentFocusNode = meNode;
      renderChart(getFilteredTree(meNode), true, meNode.id);
    } else {
      renderChart(datasource, false, null);
    }

    // Aplicar posición guardada y offsets verticales después del render,
    // luego revelar el chart de una sola vez (sin flash intermedio)
    setTimeout(function () {
      // El zoom/pan guardado solo aplica al superadmin
      if (savedViewState && isSuperuser) {
        var sl = savedViewState.chart_left || 0;
        var st = savedViewState.chart_top  || 0;
        var sc = savedViewState.scale      || 1;
        if ((sl > 0 || st > 0 || sc !== 1) && sc >= 0.5 && sc <= 2.5) {
          applyChartPosition(savedViewState);
        }
      }
      // Los offsets visuales solo aplican cuando se muestran compañeros
      if (showPeers && Object.keys(nodeYOffsets).length > 0) {
        applyNodeYOffsets(nodeYOffsets);
      }
      // Revelar el chart con un fade suave una vez que todo está listo
      $container.css({ transition: 'opacity 0.25s ease', opacity: '1' });
    }, 400);

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
      if (isSuperuser) saveViewState();
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
    //  BOTÓN TOGGLE IGUALES
    // =========================
    $('#oc-toggle-peers').on('click', function (e) {
      e.preventDefault();
      showPeers = !showPeers;
      $(this).toggleClass('oc-btn-active', showPeers);

      // Usar el nodo actualmente en foco (puede ser yo u otro buscado)
      var focusNode = currentFocusNode || meNode;
      if (!focusNode) return;
      var filteredTree = getFilteredTree(focusNode);
      renderChart(filteredTree, true, focusNode.id);

      // Resaltar el nodo en foco después del render
      setTimeout(function () {
        var $focus = $container.find('.node[data-employee-id="' + focusNode.id + '"]').first();
        $container.find('.node.orgchart-highlight').removeClass('orgchart-highlight');
        if ($focus.length) $focus.addClass('orgchart-highlight');
      }, 200);
    });

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
      currentFocusNode = matchNode;
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
