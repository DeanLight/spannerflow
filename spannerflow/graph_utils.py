import networkx as nx


def find_sources(graph: nx.DiGraph) -> list[str | int]:
    return [node for node in graph.nodes() if graph.in_degree(node) == 0]


def find_output(graph: nx.DiGraph) -> str | int:
    outputs = [node for node in graph.nodes() if graph.out_degree(node) == 0]
    if len(outputs) != 1:
        raise Exception("There can only be one output node to the graph")
    return outputs[0]


def change_node_key(G, old_key, new_key):
    # Add a new node with the new key, and copy the attributes of the old node
    G.add_node(new_key, **G.nodes[old_key])

    # Reconnect the edges from the old node to the new node
    for neighbor in G.neighbors(old_key):
        G.add_edge(new_key, neighbor)

    # If it's a directed graph, also handle incoming edges
    if G.is_directed():
        for predecessor in G.predecessors(old_key):
            G.add_edge(predecessor, new_key)

    # Remove the old node
    G.remove_node(old_key)


def get_cycles(graph):
    cycles = nx.recursive_simple_cycles(graph)
    cycle_dicts = dict()

    for cycle in cycles:
        anchor = find_anchor_of_cycle(graph, cycle)
        cycle_dicts[anchor] = graph.subgraph(cycle).copy()

    return cycle_dicts


def find_anchor_of_cycle(graph, cycle):
    # TODO: Change to node with edge to egress node (outside of the circle)
    for node in cycle:
        if graph.nodes[node]["op"] == "union":
            return node


def reduced_graph(graph):
    """Returned a reduced graph with the cycle nodes removed but the anchor node"""
    cycles = get_cycles(graph)
    reduced = graph.copy()

    for anchor, cycle in cycles.items():
        cycle_nodes = [node for node in cycle if node != anchor]
        change_node_key(cycle, anchor, f"iter_{anchor}")

        reduced.remove_nodes_from(cycle_nodes)
        reduced.nodes[anchor]["anchor"] = True
        graph.nodes[anchor]["anchor"] = True

        # find edges that connect to the cycle and connect them to the anchor
        for node in cycle_nodes:
            for p_node in graph.predecessors(node):
                if p_node not in cycle_nodes and p_node != anchor:
                    reduced.add_edge(p_node, anchor)

    return reduced, cycles


def get_node_schema(graph, node):
    schema = graph.nodes[node]["schema"]
    if len(schema) > 1:
        return f"({', '.join(schema)})"

    if len(schema) == 0:
        return "()"
    return schema[0]


def get_common_cols(graph, node1, node2):
    return list(set(graph.nodes[node1]["schema"]) & set(graph.nodes[node2]["schema"]))


def get_diff_cols(graph, node1, node2):
    return list(set(graph.nodes[node1]["schema"]) ^ set(graph.nodes[node2]["schema"]))


def get_minus_cols(graph, node1, common_cols):
    return list(set(graph.nodes[node1]["schema"]) - set(common_cols))


def find_egress_node(graph, cycle, anchor):
    """find a node that the anchor has an edge to it but it is not part of the cycle"""
    for node in graph.successors(anchor):
        if node not in cycle.nodes:
            return node


def traverse_cycle(graph, cycle, anchor):
    """create a list of nodes for traversing the cylce
    (a direct edge must exist between adjucent nodes in the list)
    The anchor node must be the last node in the list.
    """
    temp_node = anchor
    cycle_order = []
    while len(cycle_order) < len(cycle):
        cycle_order += list(cycle.successors(temp_node))
        temp_node = cycle_order[-1]
    return cycle_order


def find_ingress_nodes(graph, cycle, anchor=None):
    """returns all nodes that have an edge to the cycle that is not part of the cycle"""
    ingress_nodes = []
    for node in cycle:
        if type(node) is str and "iter" in node:
            node = node.split("_")[1]
        for pred in graph.pred[node]:
            if pred not in cycle and "anchor" not in graph.nodes[pred]:
                ingress_nodes.append(pred)
    return ingress_nodes


def create_iter_graph(graph, cycle, anchor):
    ingress = find_ingress_nodes(graph, cycle, anchor)
    iter_graph = graph.subgraph(list(cycle.nodes) + (ingress) + [anchor]).copy()
    change_node_key(iter_graph, anchor, f"iter_{anchor}")
    iter_graph.nodes[f"iter_{anchor}"]["anchor"] = True
    return iter_graph
