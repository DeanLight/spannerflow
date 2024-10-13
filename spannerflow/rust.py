import subprocess
import threading
from datetime import datetime
from pathlib import Path

import jinja2
import networkx as nx
import pandas as pd

from spannerflow.config import Config
from spannerflow.engine import Engine
from spannerflow.graph_utils import (
    create_iter_graph,
    find_ingress_nodes,
    find_output,
    find_sources,
    get_common_cols,
    get_minus_cols,
    get_node_schema,
    reduced_graph,
    traverse_cycle,
)

config = Config()

PYTHON_RUST_TYPES = {
    "DATA_TYPE_STRING": "String",
    "DATA_TYPE_INT": "i32",
    "DATA_TYPE_FLOAT": "f32",
    "DATA_TYPE_BOOL": "bool",
}


class equalConstTheta:
    def __init__(self, *pos_val_tuples):
        self.pos_val_tuples = pos_val_tuples

    def __call__(self, df):
        masks = [df.iloc[:, pos] == val for pos, val in self.pos_val_tuples]
        return pd.concat(masks, axis=1).all(axis=1)

    def __str__(self):
        return f"""Theta({', '.join([f'col_{pos}={val}' for pos,val in self.pos_val_tuples])})"""

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if not isinstance(other, equalConstTheta):
            return False
        return self.pos_val_tuples == other.pos_val_tuples


class equalColTheta:
    def __init__(self, *col_pos_tuples):
        self.col_pos_tuples = col_pos_tuples

    def __call__(self, df):
        masks = [
            df.iloc[:, pos1] == df.iloc[:, pos2] for pos1, pos2 in self.col_pos_tuples
        ]
        return pd.concat(masks, axis=1).all(axis=1)

    def __str__(self):
        return f"""Theta({', '.join([f'col_{pos1}=col_{pos2}' for pos1,pos2 in self.col_pos_tuples])})"""

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if not isinstance(other, equalColTheta):
            return False
        return self.col_pos_tuples == other.col_pos_tuples


def get_input_schema(node: int | str) -> list[str]:
    engine = Engine(config)
    collections = engine.get_collections()
    types_list = [PYTHON_RUST_TYPES[x] for x in collections[str(node)]]
    return types_list


def get_sources_data(
    graph: nx.DiGraph,
) -> dict[str | int, dict[str, str | int | list[str]]]:
    return {
        source: {"name": source, "schema": get_input_schema(source)}
        for source in find_sources(graph)
    }


def get_col_schema(cols: list[str]) -> str:
    if not cols:
        return "0"
    if len(cols) > 1:
        return f"({', '.join(cols)})"
    else:
        return cols[0]


def get_join_code(
    graph: nx.DiGraph,
    node: str | int,
    anchor: str | int | None = None,
    in_iterate: bool = False,
) -> str:
    prev_nodes = list(graph.pred[node])
    if len(prev_nodes) != 2:
        raise ValueError("Node is not 2-join: ", node)
    join1, join2 = list(graph.pred[node])
    out_node_str = f"node_{node}"
    join1_str = f"node_{join1}"
    join2_str = f"node_{join2}"

    if in_iterate:
        if node == anchor:
            out_node_str = str(anchor)
        if join1 == anchor:
            join1_str = join1
        if join2 == anchor:
            join2_str = join2

    common_cols = get_common_cols(graph, join1, join2)
    common_schema = get_col_schema(common_cols)

    join1_uncommon_schema = get_col_schema(get_minus_cols(graph, join1, common_cols))
    join2_uncommon_schema = get_col_schema(get_minus_cols(graph, join2, common_cols))
    out_join1_uncommon_schema = (
        join1_uncommon_schema if (not join1_uncommon_schema == "0") else "_"
    )
    out_join2_uncommon_schema = (
        join2_uncommon_schema if (not join2_uncommon_schema == "0") else "_"
    )

    return f"""let {out_node_str} = {join1_str}.map(|{get_node_schema(graph, join1)}| ({common_schema}, {join1_uncommon_schema}))
                        .join(&{join2_str}.map(|{get_node_schema(graph, join2)}| ({common_schema}, {join2_uncommon_schema})))
                        .map(|({common_schema}, ({out_join1_uncommon_schema}, {out_join2_uncommon_schema}))| ({get_node_schema(graph, node)}));"""


def get_union_code(
    graph: nx.DiGraph,
    node: str | int,
    anchor: str | int | None = None,
    in_iterate: bool = False,
) -> str:
    preds = list(graph.pred[node])
    prev_node1_str: int | str = f"node_{preds[0]}"
    node_str = f"node_{node}"
    if in_iterate:
        if preds[0] == anchor:
            prev_node1_str = anchor
        if node == anchor:
            node_str = str(anchor)
    if len(preds) == 1:
        return f"let {node_str} = {prev_node1_str};"
    elif len(preds) == 2:
        prev_node2_str = f"node_{preds[1]}"
        if in_iterate and preds[1] == anchor:
            prev_node2_str = str(anchor)
        return f"let{' mut' if not in_iterate and node_str == 'node_' + str(node) else ''} {node_str} = {prev_node1_str}.concat(&{prev_node2_str});"
    raise ValueError(
        "Union node has invalida number of predecessors: ", (len(preds), node)
    )


def generate_code(
    graph: nx.DiGraph,
    node: str | int,
    anchor: str | int | None = None,
    in_iterate: bool = False,
) -> str:
    gr_node = graph.nodes[node]
    match gr_node["op"]:
        case "get_rel":
            code = get_get_rel_code(graph, node, anchor=anchor, in_iterate=in_iterate)
        case "rename":
            code = get_rename_code(graph, node, anchor=anchor, in_iterate=in_iterate)
        case "project":
            code = get_project_code(graph, node, anchor=anchor, in_iterate=in_iterate)
        case "join":
            code = get_join_code(graph, node, anchor=anchor, in_iterate=in_iterate)
        case "select":
            code = get_select_code(graph, node, anchor=anchor, in_iterate=in_iterate)
        case "union":
            code = get_union_code(graph, node, in_iterate=in_iterate, anchor=anchor)
        case "groupby":
            code = get_groupby_code(graph, node, anchor=anchor, in_iterate=in_iterate)
        case _:
            raise ValueError(f"Unsupported operation: {gr_node['op']}")

    return code


def get_project_code(
    graph: nx.DiGraph,
    node: str | int,
    anchor: str | int | None = None,
    in_iterate: bool = False,
) -> str:
    schema = get_node_schema(graph, node)
    prev_nodes = list(graph.pred[node])
    if prev_nodes:
        prev_node_str = f"node_{prev_nodes[0]}"

    node_str = f"node_{node}"
    if in_iterate:
        if prev_nodes and prev_nodes[0] == anchor:
            prev_node_str = str(anchor)
        if node == anchor:
            node_str = str(anchor)
    if prev_nodes:
        prev_schema = get_node_schema(graph, prev_nodes[0])
        code = f"let {node_str} = {prev_node_str}.map(|{prev_schema}| {schema});"
    else:
        code = ""
    return code


def get_get_rel_code(
    graph: nx.DiGraph,
    node: str | int,
    anchor: str | int | None = None,
    in_iterate: bool = False,
) -> str:
    node_str = f"node_{node}"
    if in_iterate:
        if node == anchor:
            node_str = str(anchor)
    code = f"let {node_str} = input_{node}.to_collection(scope);"
    return code


def get_rename_code(
    graph: nx.DiGraph,
    node: str | int,
    anchor: str | int | None = None,
    in_iterate: bool = False,
) -> str:
    schema = get_node_schema(graph, node)
    prev_nodes = list(graph.pred[node])
    if prev_nodes:
        prev_node_str = f"node_{prev_nodes[0]}"

    node_str = f"node_{node}"
    if in_iterate:
        if prev_nodes and prev_nodes[0] == anchor:
            prev_node_str = str(anchor)
        if node == anchor:
            node_str = str(anchor)

    code = f"let {node_str} = {prev_node_str}.map(|{schema}| {schema});"
    return code


def get_select_code(
    graph: nx.DiGraph,
    node: str | int,
    anchor: str | int | None = None,
    in_iterate: bool = False,
) -> str:
    gr_node = graph.nodes[node]
    prev_nodes = list(graph.pred[node])
    if prev_nodes:
        prev_node_str = f"node_{prev_nodes[0]}"

    node_str = f"node_{node}"
    if in_iterate:
        if prev_nodes and prev_nodes[0] == anchor:
            prev_node_str = str(anchor)
        if node == anchor:
            node_str = str(anchor)
    theta = gr_node["theta"]
    preds = []
    # TODO:
    if isinstance(theta, equalConstTheta):
        preds = [f"col_{pos} == {val}" for pos, val in theta.pos_val_tuples]
    # TODO:
    elif isinstance(theta, equalColTheta):
        preds = [f"col_{pos1} == col_{pos2}" for pos1, pos2 in theta.col_pos_tuples]
    code = f"let {node_str} = {prev_node_str}.filter(|&{get_node_schema(graph, prev_nodes[0])}| {' && '.join(preds)});"
    return code


def get_groupby_code(
    graph: nx.DiGraph,
    node: str | int,
    anchor: str | int | None = None,
    in_iterate: bool = False,
) -> str:
    gr_node = graph.nodes[node]
    prev_nodes = list(graph.pred[node])
    if prev_nodes:
        prev_node_str = f"node_{prev_nodes[0]}"

    node_str = f"node_{node}"
    if in_iterate:
        if prev_nodes and prev_nodes[0] == anchor:
            prev_node_str = str(anchor)
        if node == anchor:
            node_str = str(anchor)
    agg = gr_node["agg"]
    schema = gr_node["schema"]
    groupby_cols = [schema[i] for i, agg_func in enumerate(agg) if agg_func is None]
    agg_by_cols = {
        schema[i]: {"agg_func": agg_func}
        for i, agg_func in enumerate(agg)
        if agg_func is not None
    }

    agg_cols = list(agg_by_cols.keys())
    agg_by_index = {}
    for key, agg_func in agg_by_cols.items():
        agg_func["index"] = agg_cols.index(key)
        agg_by_index[agg_func["index"]] = {
            "agg_func": agg_func["agg_func"],
            "col_name": key,
        }

    multi_agg = False
    if len(agg_by_cols.values()) > 1:
        multi_agg = True

    declares = []
    agg_code = []
    output = []
    for col_name, agg_func in agg_by_cols.items():
        agg_index = agg_func["index"]
        agg_var = f"{agg_func['agg_func']}_{col_name}"
        output.append(agg_var)
        val = "val" if not multi_agg else f"val.{agg_index}"
        match agg_func["agg_func"]:
            case "sum":
                declares.append(f"let mut {agg_var}: i32 = 0;")
                agg_code.append(f"{agg_var} += {val} * (*cnt as i32);")
            case "count":
                declares.append(f"let mut {agg_var}: i32 = 0;")
                agg_code.append(f"{agg_var} += *cnt as i32;")
            case "max":
                declares.append(f"let mut {agg_var}: i32 = i32::MIN;")
                agg_code.append(f"{agg_var} = std::cmp::max({agg_var}, {val});")
            case "min":
                declares.append(f"let mut {agg_var}: i32 = i32::MAX;")
                agg_code.append(f"{agg_var} = std::cmp::min({agg_var}, {val});")
            case "avg":
                declares.append(f"let mut {agg_var}: (i32, i32) = (0, 0);")
                agg_code.append(f"{agg_var}.0 += {val} * (*cnt as i32);")
                agg_code.append(f"{agg_var}.1 += *cnt as i32;")
            case _:
                raise ValueError(
                    f"Unsupported aggregate function: {agg_func['agg_func']}"
                )

    template_loader = jinja2.FileSystemLoader(searchpath=config.TEMPLATES_PATH)
    template_env = jinja2.Environment(loader=template_loader)
    agg_template = template_env.get_template("aggregate.rs.jinja2")

    code = agg_template.render(
        output_node=node_str,
        prev_node=prev_node_str,
        in_schema=get_col_schema(schema),
        groupby_schema=get_col_schema(groupby_cols),
        groupby_len=len(groupby_cols),
        agg_len=len(agg_cols),
        agg_schema=get_col_schema(agg_cols),
        agg_decleration=declares,
        agg_list=agg_code,
        output_tuple=get_col_schema(output),
        agg_by_index=agg_by_index,
    )
    return code


def generate_graph_code(graph: nx.DiGraph) -> dict[str | int, str]:
    flow_code = dict()
    template_loader = jinja2.FileSystemLoader(searchpath=config.TEMPLATES_PATH)
    template_env = jinja2.Environment(loader=template_loader)
    iterate_template = template_env.get_template("iterate.rs.jinja2")
    reduced, cycles = reduced_graph(graph)
    for node in list(nx.topological_sort(reduced)):
        if node in cycles.keys():
            iter_graph = create_iter_graph(graph, cycles[node], node)
            # TODO: need to add mut to the var decleration
            anchor_code = generate_code(reduced, node)
            cycle_code = {}
            cycle_order = traverse_cycle(cycles[node], f"iter_{node}")
            for cycle_node in cycle_order:
                cycle_code[cycle_node] = generate_code(
                    iter_graph, cycle_node, anchor=f"iter_{node}", in_iterate=True
                )
            flow_code[node] = iterate_template.render(
                {
                    "ingress_nodes": find_ingress_nodes(
                        graph, list(cycles[node].nodes)
                    ),
                    "anchor": node,
                    "cycle_flow": cycle_order,
                    "flow_code": cycle_code,
                    "anchor_code": anchor_code,
                }
            )
        else:
            flow_code[node] = generate_code(graph, node)
    return flow_code


def get_output_data(graph: nx.DiGraph) -> tuple[str | int, int]:
    output = find_output(graph)
    return output, len(graph.nodes[output]["schema"])


def create_cargo_toml(file_name: str, timestamp: str) -> None:
    dest_path = config.GENERATED_RUST_PROJECT_PATH / file_name
    template_loader = jinja2.FileSystemLoader(searchpath=config.TEMPLATES_PATH)
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(config.CARGO_TOML_TEMPLATE_NAME)

    output_text = template.render(
        project_name=config.RUST_PROJECT_NAME,
        rust_file_name=f"{timestamp}.rs",
        dependencies=config.RUST_DEPENDENCIES,
        build_dependencies=config.RUST_BUILD_DEPEDENCIES,
    )

    with open(dest_path, "w") as f:
        f.write(output_text)


def create_rust_file(timestamp: str, graph: nx.DiGraph) -> None:
    dest_path = config.GENERATED_RUST_PROJECT_PATH / "src" / f"{timestamp}.rs"
    template_loader = jinja2.FileSystemLoader(searchpath=config.TEMPLATES_PATH)
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(config.RUST_FILE_TEMPLATE_NAME)
    flow_code = generate_graph_code(graph)
    reduced, _ = reduced_graph(graph)
    output_node, output_vars = get_output_data(reduced)
    output_text = template.render(
        sources=get_sources_data(graph),
        flow_code=flow_code,
        top_sort=list(nx.topological_sort(reduced)),
        query_id=111,
        output_node=output_node,
        output_vars=output_vars,
    )

    with open(dest_path, "w") as f:
        f.write(output_text)


def create_rust_build_file(proto_dir_path: Path, proto_file_path: Path) -> None:
    dest_path = config.GENERATED_RUST_PROJECT_PATH / "build.rs"
    template_loader = jinja2.FileSystemLoader(searchpath=config.TEMPLATES_PATH)
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(config.RUST_BUILD_TEMPLATE_NAME)

    output_text = template.render(
        proto_dir_path=proto_dir_path, proto_file_path=proto_file_path
    )

    with open(dest_path, "w") as f:
        f.write(output_text)


def build_so(graph: nx.DiGraph) -> None:
    config.GENERATED_RUST_PROJECT_PATH.joinpath("src").mkdir(
        parents=True, exist_ok=True
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cargo_file_name = "Cargo.toml"
    create_cargo_toml(cargo_file_name, timestamp)
    create_rust_file(timestamp, graph)
    create_rust_build_file(config.PROTO_DIR_PATH, config.PROTO_FILE_PATH)
    build_rust(
        config.GENERATED_RUST_PROJECT_PATH.joinpath(cargo_file_name).absolute(),
        config.RUST_SO_BUILD_LOG_PATH,
    )


def build_rust(cargo_toml_path: Path, log_path: Path) -> None:
    command = [
        "cargo",
        "build",
        "--release",
        "--manifest-path",
        str(cargo_toml_path),
    ]

    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as log_file:
        subprocess.run(
            command,
            cwd=str(cargo_toml_path.parent),
            check=True,
            stderr=log_file,
            stdout=log_file,
        )


def build_rust_server() -> None:
    cargo_toml_path = Path(__file__).parent.joinpath("Cargo.toml")
    build_rust(cargo_toml_path.absolute(), config.RUST_SERVER_BUILD_LOG_PATH)


def run_rust_server_in_background() -> None:
    def inner() -> None:
        # TODO: handle port is already in use
        server_path = (
            Path(__file__)
            .parent.joinpath("target", "release", "spannerflow_rust")
            .absolute()
        )
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(config.RUST_SERVER_LOG_PATH, "a") as log_file:
            subprocess.run([str(server_path)], stdout=log_file, stderr=log_file)

    threading.Thread(target=inner).start()
