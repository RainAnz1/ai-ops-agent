import unittest

from analyzer import analyze_error
from fixer import generate_fix


class FixerTest(unittest.TestCase):
    def test_port_plan_uses_detected_port(self):
        logs = "bind() to 0.0.0.0:8080 failed (98: Address already in use)"
        analysis = analyze_error(logs)

        plan = generate_fix(analysis, logs=logs)

        self.assertEqual(plan.issue_type, "端口占用")
        self.assertIn("sudo lsof -i :8080", plan.commands)
        self.assertGreaterEqual(len(plan.manual_steps), 1)


if __name__ == "__main__":
    unittest.main()
