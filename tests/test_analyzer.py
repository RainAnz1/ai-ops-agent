import unittest

from analyzer import analyze_error


class AnalyzerTest(unittest.TestCase):
    def test_detects_port_in_use(self):
        logs = "nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)"

        result = analyze_error(logs)

        self.assertEqual(result.issue_type, "端口占用")
        self.assertEqual(result.severity, "high")
        self.assertGreaterEqual(result.confidence, 0.65)
        self.assertTrue(result.evidence)

    def test_empty_logs_are_reported(self):
        result = analyze_error("")

        self.assertEqual(result.issue_type, "无日志内容")
        self.assertEqual(result.severity, "low")


if __name__ == "__main__":
    unittest.main()
