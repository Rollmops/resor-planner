import unittest
from dataclasses import dataclass, field
from typing import Generator

import networkx as nx


@dataclass
class TR:
    name: str
    deps: list[str] = field(default_factory=lambda: [])
    tools: list[str] = field(default_factory=lambda: [])


class ApplyPlanner:
    def __init__(self, state: dict, target: dict, changed: set[str]):
        self._state = state
        self._target = target
        self._changed = changed or set()

        self._delete_deps_graph = self._generate_delete_deps_graph()
        self._tools_deps_graph = self._generate_tools_deps_graph()

        self._applied = set()

    def plan(self, specifiers: list[str] = None) -> Generator[str, None, None]:
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

        for tool in self._tools_deps_graph:
            self._apply_resource(plan, tool)

        plan.append("-" + name)

    def _generate_delete_deps_graph(self) -> nx.DiGraph:
        deps_graph = nx.DiGraph()
        for name, r in self._state.items():
            deps_graph.add_node(name)
            deps_graph.add_edges_from([(name, d) for d in r.deps])

        assert deps_graph.is_directed()
        return deps_graph

    def _generate_tools_deps_graph(self) -> nx.DiGraph:
        tools_graph = nx.DiGraph()
        for name, r in self._state.items():
            tools_graph.add_edges_from([(name, d) for d in r.tools])

        assert tools_graph.is_directed()
        return tools_graph


TEST_RESOURCES_1 = [
    TR("km-config"),
    TR("km", deps=["km-config"]),
    TR("pes-spool", tools=["km"]),
    TR("pes", deps=["km", "pes-spool"]),
]

TEST_RESOURCES_2 = [
    TR("adp-rpm"),
    TR("database-permission-updater", deps=["adp-rpm"]),
    TR("adp-config", tools=["database-permission-updater"], deps=["adp-rpm"]),
]


class GraphBuilderTestCase(unittest.TestCase):

    def test_all_new_except_changed_spool(self):
        gb = self._build_apply_planner(TEST_RESOURCES_1, new=["km", "pes", "km-config"], changed=["pes-spool"])

        plan = gb.plan(["pes-spool"])

        self.assertEqual(['+km-config', '+km', '-pes-spool', '+pes-spool'], list(plan))

    def test_all_new(self):
        gb = self._build_apply_planner(TEST_RESOURCES_1, all_new=True)

        plan = gb.plan()

        self.assertEqual(['+km-config', '+km', '+pes-spool', '+pes'], list(plan))

    def test_all_removed(self):
        gb = self._build_apply_planner(TEST_RESOURCES_1, all_removed=True)

        plan = gb.plan()

        self.assertEqual(['-pes', '-pes-spool', '-km', '-km-config'], list(plan))

    def test_pes_spool_and_tool_changed(self):
        gb = self._build_apply_planner(TEST_RESOURCES_1, changed=["pes-spool", "km"])

        plan = gb.plan()

        self.assertEqual(['-pes', '-pes-spool', '+pes-spool', '-km', '+km', '+pes'], list(plan))

    def test_all_changed(self):
        gb = self._build_apply_planner(TEST_RESOURCES_1, changed=[e.name for e in TEST_RESOURCES_1])

        plan = gb.plan()

        self.assertEqual(
            ['-pes', '-pes-spool', '+pes-spool', '-km', '-km-config', '+km-config', '+km', '+pes'], list(plan)
        )

    def test_km_config_changed(self):
        gb = self._build_apply_planner(TEST_RESOURCES_1, changed=["km-config"])

        plan = gb.plan()

        self.assertEqual(['-pes', '-km', '-km-config', '+km-config', '+km', '+pes'], list(plan))

    def test_2_all_new(self):
        gb = self._build_apply_planner(TEST_RESOURCES_2, all_new=True)

        plan = gb.plan()

        self.assertEqual(['+adp-rpm', '+database-permission-updater', '+adp-config'], list(plan))

    @staticmethod
    def _build_apply_planner(
            resources: list[TR], removed: list[str] = None, new: list[str] = None,
            changed: list[str] = None, all_new: bool = False, all_removed: bool = False) -> ApplyPlanner:
        state, target = {}, {}
        for resource in resources:
            if not all_new:
                state[resource.name] = resource
            if not all_removed:
                target[resource.name] = resource

        for d in removed or []:
            del target[d]

        for n in new or []:
            del state[n]

        return ApplyPlanner(state, target, changed or set())
