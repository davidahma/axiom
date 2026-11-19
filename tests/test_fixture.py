import json
import unittest
from datetime import datetime

from axiom_demo.fixture import TICKETS, run_case


def states(report, subject, phase):
    return {
        row["surface"]: row["state"]
        for row in report["observations"]
        if row["subject"] == subject and row["phase"] == phase
    }


PRESENT = {"source": "present", "summary": "present", "support": "returned"}
ABSENT = {"source": "absent", "summary": "absent", "support": "not_returned"}


class ControlledFixtureTests(unittest.TestCase):
    def test_stale_job_recreates_a_servable_derivative_only(self):
        report = run_case("broken")
        self.assertEqual(report["origin"], "controlled-fixture")
        self.assertEqual(
            report["worker"], {"captured_before_delete": True, "terminal": "written"}
        )
        self.assertEqual(states(report, "acme", "baseline"), PRESENT)
        self.assertEqual(states(report, "acme", "offboarded"), ABSENT)
        self.assertEqual(
            states(report, "acme", "worker_finished"),
            {"source": "absent", "summary": "present", "support": "returned"},
        )
        for phase in ("baseline", "offboarded", "worker_finished"):
            self.assertEqual(states(report, "birch", phase), PRESENT)

    def test_guarded_job_discards_captured_work_and_keeps_control(self):
        report = run_case("fixed")
        self.assertEqual(report["case"], "fixed")
        self.assertEqual(
            report["worker"], {"captured_before_delete": True, "terminal": "discarded"}
        )
        self.assertEqual(states(report, "acme", "baseline"), PRESENT)
        self.assertEqual(states(report, "acme", "offboarded"), ABSENT)
        self.assertEqual(states(report, "acme", "worker_finished"), ABSENT)
        for phase in ("baseline", "offboarded", "worker_finished"):
            self.assertEqual(states(report, "birch", phase), PRESENT)

    def test_failed_http_baseline_is_unknown_while_storage_still_observes_it(self):
        report = run_case("inconclusive")
        self.assertEqual(
            states(report, "acme", "baseline"),
            {"source": "present", "summary": "present", "support": "unavailable"},
        )
        self.assertEqual(states(report, "birch", "baseline"), PRESENT)
        self.assertEqual(states(report, "acme", "worker_finished"), ABSENT)
        self.assertEqual(report["worker"]["terminal"], "discarded")

    def test_output_is_content_free_and_chronological(self):
        report = run_case("broken")
        observations = report["observations"]
        self.assertEqual(len(observations), 18)
        self.assertEqual(
            [row["phase"] for row in observations],
            ["baseline"] * 6 + ["offboarded"] * 6 + ["worker_finished"] * 6,
        )
        for row in observations:
            self.assertEqual(
                set(row), {"phase", "subject", "surface", "state", "observed_at"}
            )
            self.assertTrue(row["observed_at"].endswith("Z"))
            self.assertIsNotNone(datetime.fromisoformat(row["observed_at"]).tzinfo)
        serialized = json.dumps(report)
        for ticket in TICKETS:
            self.assertNotIn(ticket.reference, serialized)
            self.assertNotIn(ticket.source_id, serialized)
        self.assertNotIn("Bearer", serialized)

    def test_rejects_an_unknown_mode(self):
        with self.assertRaises(ValueError):
            run_case("unrecognized")


if __name__ == "__main__":
    unittest.main()
