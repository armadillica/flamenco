// The number of graph elements (nodes + edges) we consider a "big" graph.
var GRAPH_ELEMENTS_CONSIDERED_BIG = 100;

function depsgraph(canvas_id, elements, roots, focus_task_id) {

    // At least draw *something* when there is no data.
    if (!elements || elements.length == 0) {
        console.log('Nothing to draw');
        elements = [{data: {
            outside: true,
            label: 'No tasks here...',
        }}];
        roots = null;
    }

    // Set up nodes
    let nodes_list = [];
    let task_id_to_node_index = {};
    var node_idx = 0;
    for (element of elements) {
        if (element.group != "nodes") continue;
        var node = element.data;

        var classes = ['task', node.status];
        if (node.outside) classes.push('outside');
        if (node.focus) classes.push('focus');

        g.setNode(node.id,  {
            label: node.label,
            class: classes.join(" "),
            style: "background-color: " + node.color,
            id: node.id,
        });

        // console.log('node', index, node_idx, element.data);
    }

    g.nodes().forEach(function(v) {
      var node = g.node(v);
      // Round the corners of the nodes
      node.rx = node.ry = 5;
    });

    // Set up edges
    for (element of elements) {
        if (element.group != "edges") continue;
        // console.log("edge", element.data);
        g.setEdge(element.data.source, element.data.target);
    }

    // Create the renderer
    var render = new dagreD3.render();

    // Run the renderer. This is what draws the final graph.
    render(d3.select("svg g"), g);

    $('svg g.node')
    .off('click')
    .off('contextmenu')
    .click(function(evt) {
        evt.preventDefault();
        // focus_on_node(evt.delegateTarget.id);
        window.location.href = 'depsgraph?t=' + evt.delegateTarget.id;
    })
    .contextmenu(function(evt) {
        evt.preventDefault();
        window.open('../with-task/' + evt.delegateTarget.id, '_blank');
    });
}

function focus_on_node(node_id) {
    console.log(node_id);
    var url = 'depsgraph-data';
    if (typeof node_id !== 'undefined') {
        url += '/' + node_id;
    }

    $.getJSON(url, function(node_edge_data) {
        console.log('Node/edge data: ', node_edge_data);
        depsgraph('depsgraph', node_edge_data.elements, node_edge_data.roots, node_id);
    })
    .fail(function(xhr) {
        console.log('Could not get depsgraph data', xhr);
    })
    .always(function() { $('#loading').hide(); })
    ;
}

let g = new dagreD3.graphlib.Graph()
    .setGraph({})
    .setDefaultEdgeLabel(function() { return {}; });

function init_depsgraph() {
    // Set up zoom support
    var svg = d3.select("svg"),
        inner = d3.select("svg g"),
        zoom = d3.zoom().on("zoom", function() {
          inner.attr("transform", d3.event.transform);
        });
    svg.call(zoom);
}
