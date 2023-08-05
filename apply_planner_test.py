import unittest
from dataclasses import dataclass, field

from apply_planner import ApplyPlanner


@dataclass
class TR:
    name: str
    deps: list[str] = field(default_factory=lambda: [])
    tools: list[str] = field(default_factory=lambda: [])


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
