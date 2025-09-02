fetch("{% url 'org_chart_data_1' %}", { credentials: 'same-origin' })
  .then(r => r.json())
  .then(({ nodes }) => {
    // Ordenar explícitamente los hijos del ROOT por 'order'
    const rootId = "N_ROOT";
    const root = nodes.find(n => n.id === rootId);
    const assistants = nodes.filter(n => n.pid === rootId && n.assistant === true)
                            .sort((a,b) => (a.order||0) - (b.order||0));
    const children   = nodes.filter(n => n.pid === rootId && !n.assistant)
                            .sort((a,b) => (a.order||0) - (b.order||0));
    const others     = nodes.filter(n => n.id !== rootId && n.pid !== rootId);

    const ordered = [root, ...assistants, ...children, ...others];

    new OrgChart(document.getElementById("tree"), {
      template: "olivia",
      nodeBinding: { field_0: "name", field_1: "title", img_0: "img" },
      nodes: ordered,
      mouseScrool: OrgChart.action.zoom,
      scaleInitial: OrgChart.match.boundary,
      enableSearch: true,
      toolbar: { zoom:true, fit:true, expandAll:true, fullScreen:true, export:{ png:true, pdf:true, svg:true } }
    });
  });
