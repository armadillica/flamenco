function depsgraph(canvas_id, nodes, edges) {
    var container = document.getElementById(canvas_id);

    // provide the data in the vis format
    var data = {
        nodes: new vis.DataSet(nodes),
        edges: new vis.DataSet(edges)
    };
    var options = {
        layout: {
            hierarchical: {
                direction: "RL",
                sortMethod: "directed",
                blockShifting: true,
                edgeMinimization: true,
                parentCentralization: true,
            },
        },
        edges: {
            smooth: false,
        },
        interaction: {
            dragNodes: false,
        },
        physics: {
            enabled: false,
        },
    };

    // initialize your network!
    var network = new vis.Network(container, data, options);

}
