import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import jinja2
import networkx as nx
from singleton_decorator.decorator import _SingletonWrapper, singleton

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
from spannerflow.rust_utils import build_rust


@singleton
class RustDataflow:
    DATAFLOW_TO_RUST_TYPES = {
        "DATA_TYPE_STRING": "String",
        "DATA_TYPE_INT": "i32",
        "DATA_TYPE_FLOAT": "OrderedFloat<f32>",
        "DATA_TYPE_BOOL": "bool",
    }

    PYTHON_TO_DATAFLOW_TYPES = {
        str: "DATA_TYPE_STRING",
        int: "DATA_TYPE_INT",
        float: "DATA_TYPE_FLOAT",
        bool: "DATA_TYPE_BOOL",
        object: "DATA_TYPE_STRING",
    }

    def __init__(
        self, config: Config = Config(), engine: _SingletonWrapper | None = None
    ):
        self._config = config
        self._engine = engine or Engine(config)
        self._query_id = 0
        self._cargo_file_name = "Cargo.toml"
        self._template_loader = jinja2.FileSystemLoader(
            searchpath=self._config.TEMPLATES_PATH
        )
        self._template_env = jinja2.Environment(loader=self._template_loader)
        self._is_server_running = False
        self._server_process: None | subprocess.Popen = None

    def __enter__(self):
        self._build_rust_server()
        self._run_rust_server_in_background()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._is_server_running:
            self._stop_rust_server()

    def get_input_schema_types(self, node: int | str) -> list[str]:
        collections = self._engine.get_collections()
        return [x for x in collections[str(node)]]

    def get_input_schema(self, node: int | str) -> list[str]:
        collections = self._engine.get_collections()
        return [self.DATAFLOW_TO_RUST_TYPES[x] for x in collections[str(node)]]

    def get_sources_data(
        self,
        graph: nx.DiGraph,
    ) -> dict[str | int, dict[str, str | int | list[str]]]:
        return {
            source: {
                "name": source,
                "schema": (
                    self.get_input_schema(source)
                    if "schema_types" not in graph.nodes[source]
                    else [
                        self.DATAFLOW_TO_RUST_TYPES[t]
                        for t in graph.nodes[source]["schema_types"]
                    ]
                ),
                "op": graph.nodes[source]["op"],
                "consts": (
                    self._engine._serialize_row(
                        graph.nodes[source]["schema_types"],
                        [
                            graph.nodes[source]["const_dict"][col]
                            for col in graph.nodes[source]["schema"]
                        ],
                    )
                    if graph.nodes[source]["op"] == "get_const"
                    else []
                ),
            }
            for source in find_sources(graph)
        }

    @staticmethod
    def get_col_schema(cols: list[str]) -> str:
        if not cols:
            return "0"
        if len(cols) > 1:
            return f"({', '.join(cols)})"
        else:
            return cols[0]

    def get_join_code(
        self,
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
        common_schema = self.get_col_schema(common_cols)

        join1_uncommon_schema = self.get_col_schema(
            get_minus_cols(graph, join1, common_cols)
        )
        join2_uncommon_schema = self.get_col_schema(
            get_minus_cols(graph, join2, common_cols)
        )
        out_join1_uncommon_schema = (
            join1_uncommon_schema if (not join1_uncommon_schema == "0") else "_"
        )
        out_join2_uncommon_schema = (
            join2_uncommon_schema if (not join2_uncommon_schema == "0") else "_"
        )

        return f"""let {out_node_str} = {join1_str}.map(|{get_node_schema(graph, join1)}| ({common_schema}, {join1_uncommon_schema}))
                            .join(&{join2_str}.map(|{get_node_schema(graph, join2)}| ({common_schema}, {join2_uncommon_schema})))
                            .map(|({common_schema if common_schema != "0" else "_"}, ({out_join1_uncommon_schema}, {out_join2_uncommon_schema}))| ({get_node_schema(graph, node)}));"""

    def get_union_code(
        self,
        graph: nx.DiGraph,
        node: str | int,
        anchor: str | int | None = None,
        in_iterate: bool = False,
    ) -> str:
        preds = list(
            filter(
                lambda pred: "reduced" not in graph.get_edge_data(pred, node),
                graph.pred[node],
            )
        )

        prev_node1_str = self.get_node_str(
            preds[0], anchor=anchor, in_iterate=in_iterate
        )
        node_str = self.get_node_str(node, anchor=anchor, in_iterate=in_iterate)

        if len(preds) == 1:
            return f"let {node_str} = {prev_node1_str};"
        elif len(preds) == 2:
            prev_node2_str = self.get_node_str(
                preds[1], anchor=anchor, in_iterate=in_iterate
            )
            return f"let{' mut' if not in_iterate and node_str == 'node_' + str(node) else ''} {node_str} = {prev_node1_str}.concat(&{prev_node2_str});"
        raise ValueError(
            "Union node has invalid number of predecessors: ", (len(preds), node)
        )

    def get_node_str(
        self, node: str | int, anchor: str | int | None = None, in_iterate: bool = False
    ) -> str:
        if in_iterate and node == anchor:
            return str(anchor)
        return f"node_{node}"

    def generate_node_code(
        self,
        graph: nx.DiGraph,
        node: str | int,
        anchor: str | int | None = None,
        in_iterate: bool = False,
    ) -> str:
        gr_node = graph.nodes[node]
        preds = [graph.nodes[key] for key in graph.pred[node].keys()]
        match gr_node["op"]:
            case "get_rel":
                gr_node["schema_types"] = self.get_input_schema_types(node)
                code = self.get_get_rel_code(
                    graph, node, anchor=anchor, in_iterate=in_iterate
                )
            case "rename":
                if len(preds) != 1:
                    raise ValueError(
                        "Rename node has invalid number of predecessors: ",
                        (len(preds), node),
                    )
                gr_node["schema_types"] = preds[0]["schema_types"]
                code = self.get_rename_code(
                    graph, node, anchor=anchor, in_iterate=in_iterate
                )
            case "project":
                if len(preds) != 1:
                    raise ValueError(
                        "Project node has invalid number of predecessors: ",
                        (len(preds), node),
                    )
                pred = preds[0]
                gr_node["schema_types"] = [
                    pred["schema_types"][pred["schema"].index(col)]
                    for col in gr_node["schema"]
                ]
                code = self.get_project_code(
                    graph, node, anchor=anchor, in_iterate=in_iterate
                )
            case "join":
                if len(preds) != 2:
                    raise ValueError(
                        "Join node has invalid number of predecessors: ",
                        (len(preds), node),
                    )
                schema_types = []
                for x in gr_node["schema"]:
                    try:
                        index = preds[0]["schema"].index(x)
                        schema_types.append(preds[0]["schema_types"][index])
                    except ValueError:
                        index = preds[1]["schema"].index(x)
                        schema_types.append(preds[1]["schema_types"][index])

                gr_node["schema_types"] = schema_types
                code = self.get_join_code(
                    graph, node, anchor=anchor, in_iterate=in_iterate
                )
            case "select":
                if len(preds) != 1:
                    raise ValueError(
                        "Select node has invalid number of predecessors: ",
                        (len(preds), node),
                    )
                gr_node["schema_types"] = preds[0]["schema_types"]
                code = self.get_select_code(
                    graph, node, anchor=anchor, in_iterate=in_iterate
                )
            case "union":
                gr_node["schema_types"] = preds[0]["schema_types"]
                code = self.get_union_code(
                    graph, node, in_iterate=in_iterate, anchor=anchor
                )
            case "groupby":
                if len(preds) != 1:
                    raise ValueError(
                        "Group By node has invalid number of predecessors: ",
                        (len(preds), node),
                    )
                schema_types = []
                for index, agg in enumerate(gr_node["agg"]):
                    if agg is None:
                        schema_types.append(preds[0]["schema_types"][index])
                    elif agg == "count":
                        schema_types.append("DATA_TYPE_INT")
                    else:
                        schema_types.append("DATA_TYPE_FLOAT")
                gr_node["schema_types"] = schema_types
                code = self.get_groupby_code(
                    graph, node, anchor=anchor, in_iterate=in_iterate
                )
            case "get_const":
                gr_node["schema_types"] = [
                    self.PYTHON_TO_DATAFLOW_TYPES[type(const)]
                    for const in gr_node["const_dict"].values()
                ]
                code = self.get_get_const_code(
                    graph, node, anchor=anchor, in_iterate=in_iterate
                )
            case "product":
                if len(preds) != 2:
                    raise ValueError(
                        "Product node has invalid number of predecessors: ",
                        (len(preds), node),
                    )
                schema_types = []
                for x in gr_node["schema"]:
                    try:
                        index = preds[0]["schema"].index(x)
                        schema_types.append(preds[0]["schema_types"][index])
                    except ValueError:
                        index = preds[1]["schema"].index(x)
                        schema_types.append(preds[1]["schema_types"][index])
                gr_node["schema_types"] = schema_types
                code = self.get_join_code(  # not a bug, same implementation as join
                    graph, node, anchor=anchor, in_iterate=in_iterate
                )
            case "ie_map":
                if callable(gr_node["in_schema"]):
                    gr_node["in_schema"] = gr_node["in_schema"](gr_node["in_arity"])
                if callable(gr_node["out_schema"]):
                    gr_node["out_schema"] = gr_node["out_schema"](gr_node["out_arity"])
                gr_node["schema_types"] = [
                    (
                        self.PYTHON_TO_DATAFLOW_TYPES[t]
                        # TODO Support multiple types
                        if not isinstance(t, tuple)
                        else list(
                            filter(lambda x: x in self.PYTHON_TO_DATAFLOW_TYPES, t)
                        )[0]
                    )
                    for t in gr_node["in_schema"] + gr_node["out_schema"]
                ]
                code = self.get_ie_map_code(
                    graph, node, anchor=anchor, in_iterate=in_iterate
                )
            case _:
                raise ValueError(f"Unsupported operation: {gr_node['op']}")

        return code

    def get_ie_map_code(
        self,
        graph: nx.DiGraph,
        node: str | int,
        anchor: str | int | None = None,
        in_iterate: bool = False,
    ) -> str:
        prev_nodes = list(graph.pred[node])
        node_str = self.get_node_str(node, anchor=anchor, in_iterate=in_iterate)
        prev_node_str = self.get_node_str(
            prev_nodes[0], anchor=anchor, in_iterate=in_iterate
        )
        match graph.nodes[node]["name"]:
            case "not":
                if len(prev_nodes) != 1:
                    raise ValueError(
                        "Not node has invalid number of predecessors: ",
                        (len(prev_nodes), node),
                    )
                prev_node_str = self.get_node_str(
                    prev_nodes[0], anchor=anchor, in_iterate=in_iterate
                )
                code = f"let {node_str} = {prev_node_str}.map(|{get_node_schema(graph, prev_nodes[0])}| ({get_node_schema(graph, prev_nodes[0])}, !{get_node_schema(graph, prev_nodes[0])}));"
            case _:
                ie_map_template = self._template_env.get_template("ie_map.rs.jinja2")
                code = ie_map_template.render(
                    output_node=node_str,
                    prev_node=prev_node_str,
                    grpc_address=f"http://{self._config.LISTEN_ADDRESS}",
                    function_name=graph.nodes[node]["name"],
                    in_schema=self.get_col_schema(
                        graph.nodes[node]["schema"][
                            : len(graph.nodes[node]["in_schema"])
                        ]
                    ),
                    out_schema_len=len(graph.nodes[node]["out_schema"]),
                    in_schema_len=len(graph.nodes[node]["in_schema"]),
                    out_schema_types=graph.nodes[node]["schema_types"],
                )
        return code

    def get_get_const_code(
        self,
        graph: nx.DiGraph,
        node: str | int,
        anchor: str | int | None = None,
        in_iterate: bool = False,
    ) -> str:
        node_str = self.get_node_str(node, anchor=anchor, in_iterate=in_iterate)
        code = f"let {node_str} = input_{node}.to_collection(scope);"
        return code

    def get_project_code(
        self,
        graph: nx.DiGraph,
        node: str | int,
        anchor: str | int | None = None,
        in_iterate: bool = False,
    ) -> str:
        schema = get_node_schema(graph, node)
        prev_nodes = list(graph.pred[node])

        prev_node_str = self.get_node_str(
            prev_nodes[0], anchor=anchor, in_iterate=in_iterate
        )
        node_str = self.get_node_str(node, anchor=anchor, in_iterate=in_iterate)

        if prev_nodes:
            prev_schema = get_node_schema(graph, prev_nodes[0])
            code = f"let {node_str} = {prev_node_str}.map(|{prev_schema}| {schema});"
        else:
            code = ""
        return code

    def get_get_rel_code(
        self,
        graph: nx.DiGraph,
        node: str | int,
        anchor: str | int | None = None,
        in_iterate: bool = False,
    ) -> str:
        node_str = self.get_node_str(node, anchor=anchor, in_iterate=in_iterate)
        code = f"let {node_str} = input_{node}.to_collection(scope);"
        return code

    def get_rename_code(
        self,
        graph: nx.DiGraph,
        node: str | int,
        anchor: str | int | None = None,
        in_iterate: bool = False,
    ) -> str:
        schema = get_node_schema(graph, node)
        prev_nodes = list(graph.pred[node])

        prev_node_str = self.get_node_str(
            prev_nodes[0], anchor=anchor, in_iterate=in_iterate
        )
        node_str = self.get_node_str(node, anchor=anchor, in_iterate=in_iterate)

        code = f"let {node_str} = {prev_node_str}.map(|{schema}| {schema});"
        return code

    def get_select_code(
        self,
        graph: nx.DiGraph,
        node: str | int,
        anchor: str | int | None = None,
        in_iterate: bool = False,
    ) -> str:
        gr_node = graph.nodes[node]
        prev_nodes = list(graph.pred[node])

        prev_node_str = self.get_node_str(
            prev_nodes[0], anchor=anchor, in_iterate=in_iterate
        )
        node_str = self.get_node_str(node, anchor=anchor, in_iterate=in_iterate)

        theta = gr_node["theta"]
        preds = []
        if hasattr(theta, "pos_val_tuples"):  #  equalConstTheta
            preds = [f"*col_{pos} == {val}" for pos, val in theta.pos_val_tuples]
        elif hasattr(theta, "col_pos_tuples"):  #  equalColTheta
            preds = [f"col_{pos1} == col_{pos2}" for pos1, pos2 in theta.col_pos_tuples]
        else:
            raise ValueError(f"Unsupported theta join: {theta}. {dir(theta)}")
        code = f"let {node_str} = {prev_node_str}.filter(|{get_node_schema(graph, prev_nodes[0])}| {' && '.join(preds)});"
        return code

    def update_repeatable_cols_in_schema(self, schema: list[str]) -> list[str]:
        repeatable_cols: dict[str, list[int]] = {}
        for i, col in enumerate(schema):
            if col in repeatable_cols:
                repeatable_cols[col].append(i)
            else:
                repeatable_cols[col] = [i]

        if not repeatable_cols:
            return schema
        result = schema.copy()
        for col, indecies in repeatable_cols.items():
            if len(indecies) > 1:
                for i, index in enumerate(indecies):
                    result[index] = f"{col}_{i}"
        return result

    def get_groupby_code(
        self,
        graph: nx.DiGraph,
        node: str | int,
        anchor: str | int | None = None,
        in_iterate: bool = False,
    ) -> str:
        gr_node = graph.nodes[node]
        prev_nodes = list(graph.pred[node])

        prev_node_str = self.get_node_str(
            prev_nodes[0], anchor=anchor, in_iterate=in_iterate
        )
        node_str = self.get_node_str(node, anchor=anchor, in_iterate=in_iterate)

        agg = gr_node["agg"]
        schema = self.update_repeatable_cols_in_schema(gr_node["schema"])
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

        agg_template = self._template_env.get_template("aggregate.rs.jinja2")
        code = agg_template.render(
            output_node=node_str,
            prev_node=prev_node_str,
            in_schema=self.get_col_schema(schema),
            groupby_schema=self.get_col_schema(groupby_cols),
            groupby_len=len(groupby_cols),
            agg_len=len(agg_cols),
            agg_schema=self.get_col_schema(agg_cols),
            agg_decleration=declares,
            agg_list=agg_code,
            output_tuple=self.get_col_schema(output),
            agg_by_index=agg_by_index,
        )
        return code

    def generate_graph_code(self, graph: nx.DiGraph) -> list[str]:
        flow_code = list()

        iterate_template = self._template_env.get_template("iterate.rs.jinja2")
        reduced, cycles = reduced_graph(graph)
        for node in list(nx.topological_sort(reduced)):
            if node in cycles.keys():
                iter_graph = create_iter_graph(graph, cycles[node], node)
                anchor_code = self.generate_node_code(reduced, node)
                cycle_code = {}
                cycle_order = traverse_cycle(cycles[node], f"iter_{node}")
                for cycle_node in cycle_order:
                    cycle_code[cycle_node] = self.generate_node_code(
                        iter_graph, cycle_node, anchor=f"iter_{node}", in_iterate=True
                    )
                flow_code.append(
                    iterate_template.render(
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
                )
            else:
                flow_code.append(self.generate_node_code(graph, node))
        return flow_code

    def create_cargo_toml(self, timestamp: str) -> None:
        dest_path = self._config.GENERATED_RUST_PROJECT_PATH / self._cargo_file_name
        template = self._template_env.get_template(
            self._config.CARGO_TOML_TEMPLATE_NAME
        )

        output_text = template.render(
            project_name=f"{self._config.RUST_PROJECT_NAME}{self._query_id}",
            rust_file_name=f"{timestamp}.rs",
            dependencies=self._config.RUST_DEPENDENCIES,
            build_dependencies=self._config.RUST_BUILD_DEPEDENCIES,
        )

        with open(dest_path, "w") as f:
            f.write(output_text)

    def create_rust_file(self, timestamp: str, graph: nx.DiGraph) -> None:
        dest_path = self._config.GENERATED_RUST_PROJECT_PATH / "src" / f"{timestamp}.rs"
        template = self._template_env.get_template(self._config.RUST_FILE_TEMPLATE_NAME)
        flow_code = self.generate_graph_code(graph)
        output_node = find_output(graph)
        output_text = template.render(
            query_id=self._query_id,
            sources=self.get_sources_data(graph),
            flow_code=flow_code,
            output_node_str=self.get_node_str(output_node),
            output_vars_count=len(graph.nodes[output_node]["schema"]),
        )

        with open(dest_path, "w") as f:
            f.write(output_text)

    def create_rust_build_file(self) -> None:
        dest_path = self._config.GENERATED_RUST_PROJECT_PATH / "build.rs"
        template = self._template_env.get_template(
            self._config.RUST_BUILD_TEMPLATE_NAME
        )

        output_text = template.render(
            proto_dir_path=self._config.PROTO_DIR_PATH,
            proto_file_path=self._config.PROTO_FILE_PATH,
        )
        with open(dest_path, "w") as f:
            f.write(output_text)

    def build_so(self, graph: nx.DiGraph) -> tuple[Path, str]:
        self._config.GENERATED_RUST_PROJECT_PATH.joinpath("src").mkdir(
            parents=True, exist_ok=True
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._query_id += 1
        self.create_cargo_toml(timestamp)
        self.create_rust_file(timestamp, graph)
        self.create_rust_build_file()
        build_rust(
            self._config.GENERATED_RUST_PROJECT_PATH.joinpath(
                self._cargo_file_name
            ).absolute(),
            self._config.RUST_SO_BUILD_LOG_PATH,
        )
        # Determine file extension based on the platform
        crate_name = f"{self._config.RUST_PROJECT_NAME}{self._query_id}"
        if os.name == "posix":  # Linux/macOS
            if os.uname().sysname == "Darwin":
                extension = ".dylib"  # macOS
            else:
                extension = ".so"  # Linux
            lib_filename = f"lib{crate_name}{extension}"
        elif os.name == "nt":  # Windows
            extension = ".dll"
            lib_filename = f"{crate_name}{extension}"
        else:
            raise RuntimeError("Unsupported OS")
        return (
            self._config.GENERATED_RUST_PROJECT_PATH.joinpath(
                "target", "release", lib_filename
            ),
            f"query_{self._query_id}",
        )

    def _build_rust_server(self) -> None:
        cargo_toml_path = Path(__file__).parent.joinpath("Cargo.toml")
        build_rust(cargo_toml_path.absolute(), self._config.RUST_SERVER_BUILD_LOG_PATH)

    def _run_rust_server_in_background(self) -> None:
        def inner() -> None:
            # TODO: handle port is already in use
            server_path = (
                Path(__file__)
                .parent.joinpath("target", "release", "spannerflow_rust")
                .absolute()
            )
            self._config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
            with open(self._config.RUST_SERVER_LOG_PATH, "a") as log_file:
                self._server_process = subprocess.Popen(
                    [str(server_path)], stdout=log_file, stderr=log_file
                )
                self._server_process.communicate()

        if self._is_server_running:
            raise RuntimeError("Server is already running")
        threading.Thread(target=inner).start()

        self._is_server_running = True

    def _stop_rust_server(self):
        if not self._is_server_running:
            raise RuntimeError("Server is not running")
        self._server_process.terminate()
        self._is_server_running = False
