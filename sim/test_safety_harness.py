import unittest

from safety_harness import Scenario, evaluate, run


class SafetyHarnessTests(unittest.TestCase):
    def test_happy_path_allows_paper_mode(self):
        self.assertEqual(evaluate(Scenario("healthy")).decision, "ALLOW")

    def test_unsafe_inputs_abort(self):
        cases = [
            Scenario("unauthorized", authorized=False),
            Scenario("bad-config", configuration_valid=False),
            Scenario("stale", telemetry_age_seconds=61),
            Scenario("provider", provider_available=False),
            Scenario("duplicate", duplicate_event=True),
            Scenario("malformed", malformed_token=True),
        ]
        for case in cases:
            with self.subTest(case=case.name):
                self.assertEqual(evaluate(case).decision, "ABORT")

    def test_uncertain_inputs_hold(self):
        self.assertEqual(evaluate(Scenario("conflict", signal_conflict=0.75)).decision, "HOLD")
        self.assertEqual(evaluate(Scenario("volatile", volatility=0.80)).decision, "HOLD")

    def test_default_suite_has_no_unexpected_allow(self):
        report = run()
        self.assertEqual(report["mode"], "simulation-only")
        self.assertEqual(report["summary"], {"allow": 1, "hold": 2, "abort": 6})


if __name__ == "__main__":
    unittest.main()
