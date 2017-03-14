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

    var is_big_graph = elements.length >= GRAPH_ELEMENTS_CONSIDERED_BIG;

    var cy;

    function centre_on_focus_node() {
        if (!is_big_graph) return;
        if (typeof focus_task_id == 'undefined') return;
        if (typeof cy == 'undefined') return; // happens when layout is ready before cytoscape() returns.

        var node = cy.$("#" + focus_task_id);
        cy.center(node);
    }

    cy = cytoscape({
        container: document.getElementById(canvas_id),
        elements: elements,
        style: [
            {
                selector: 'node',
                style: {
                    'background-color': function(node) {
                        if (node.data('outside')) return '#eee';
                        return node.data('color');
                    },
                    'label': 'data(label)',
                    'font-size': 12,
                    'text-opacity': function(node) { return node.data('outside') ? 0.25 : 1; },
                    'border-width': function(node) { return node.data('outside') || node.data('focus') ? 1 : 0; },
                    'border-color': function(node) { return node.data('focus') ? '#fff' : '#ddd'; },
                    'border-style': function(node) { return node.data('outside') ? 'dashed' : 'solid'; },
                    'shadow-color': '#000',
                    'shadow-blur': function(node) { return node.data('focus') ? '30px' : 0; },
                    'shadow-offset-x': 0,
                    'shadow-offset-y': 0,
                    'shadow-opacity': function(node) { return node.data('focus') ? 0.4 : 0; },
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 3,
                    'line-color': '#ccc',
                    'mid-target-arrow-color': '#ccc',
                    'mid-target-arrow-shape': 'triangle',
                }
            }
        ],

        layout: {
            // name: 'cose-bilkent',
            name: is_big_graph ? 'breadthfirst' : 'cose-bilkent',
            // name: 'breadthfirst',
            // name: 'preset',
            // name: 'cose',
            // circle: true,
            // randomize: true,
            animate: false,
            directed: true,
            maximalAdjustments: is_big_graph ? 1 : 50,
            roots: roots,
            fit: !is_big_graph,

            ready: centre_on_focus_node,
        },
        zoom: 1,
    });

    centre_on_focus_node();

    // Set up GUI events.
    cy.on('tap', 'node', function(e) {
        location.href = 'depsgraph?t=' + e.cyTarget.id();
        // focus_on_node(e.cyTarget.id()); also works, but doesn't push to browser history.
    });
    cy.on('cxttap', 'node', function(e) {
        window.open('../with-task/' + e.cyTarget.id(), '_blank');
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
        if (node_edge_data.elements.length >= GRAPH_ELEMENTS_CONSIDERED_BIG) {
            $('#graphsize').text(node_edge_data.elements.length);
            $('#size_warning').show();
        } else {
            $('#size_warning').hide();
        }
        depsgraph('depsgraph', node_edge_data.elements, node_edge_data.roots, node_id);
    })
    .fail(function(xhr) {
        console.log('Could not get depsgraph data', xhr);
    })
    .always(function() { $('#loading').hide(); })
    ;
}
