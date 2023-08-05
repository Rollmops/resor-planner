from typing import Generator

import networkx as nx


class ApplyPlanner:
    def __init__(self, state: dict, target: dict, changed: set[str]):
        self._state = state
        self._target = target
        self._changed = changed or set()

        self._delete_deps_graph = self._generate_delete_deps_graph()
        self._tools_deps_graph = self._generate_tools_deps_graph()

        self._applied = set()

    def plan(self, specifiers: list[str] = None) -> Generator[str, None, None]:
        self._validate_acyclic()

        self._applied.clear()
        specifiers = sorted(specifiers or self._target.keys() | self._state.keys())

        plan = []

        for specifier in specifiers:
            self._apply_resource(plan, specifier)

        for to_be_present in self._target:
            if "-" + to_be_present in plan and not "+" + to_be_present in plan:
                plan.append("+" + to_be_present)

        visited = set()
        for e in plan:
            if e not in visited:
                yield e
            visited.add(e)

    def _validate_acyclic(self):
        try:
            if cycles := nx.find_cycle(
                    nx.compose(self._delete_deps_graph, self._tools_deps_graph)
            ):
                raise ValueError(f"Detected cycles: {cycles}")
        except nx.NetworkXNoCycle:
            pass

    def _apply_resource(self, plan: list[str], name: str):
        if name in self._applied:
            return

        self._applied.add(name)

        if name not in self._target:
            self._plan_delete(plan, name)

        elif self._is_changed(name):
            self._plan_delete(plan, name)
            self._plan_create(plan, name)

        elif name not in self._state:
            self._plan_create(plan, name)

    def _is_changed(self, name: str) -> bool:
        return name in self._changed

    def _plan_create(self, plan: list[str], name: str):
        assert name in self._target or name in self._state

        try:
            resource = self._target[name]
        except KeyError:
            resource = self._state[name]

        for tool in resource.tools:
            self._apply_resource(plan, tool)

        for dep in resource.deps:
            self._apply_resource(plan, dep)

        plan.append("+" + name)

    def _plan_delete(self, plan: list[str], name: str):
        assert name in self._state

        if name in self._tools_deps_graph:
            for dependee_tool in self._tools_deps_graph.predecessors(name):
                self._apply_resource(plan, dependee_tool)

        for dependee in self._delete_deps_graph.predecessors(name):
            self._plan_delete(plan, dependee)

        for tool in self._state[name].tools:
            self._applied.discard(name)
            self._apply_resource(plan, tool)

        plan.append("-" + name)

    def _generate_delete_deps_graph(self) -> nx.DiGraph:
        deps_graph = nx.DiGraph()
        for name, r in self._state.items():
            deps_graph.add_node(name)
            deps_graph.add_edges_from([(name, d) for d in r.deps])

        return deps_graph

    def _generate_tools_deps_graph(self) -> nx.DiGraph:
        tools_graph = nx.DiGraph()
        for name, r in self._state.items():
            tools_graph.add_edges_from([(name, d) for d in r.tools])

        return tools_graph
