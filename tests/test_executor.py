import unittest

from executor import execute_command, is_safe_command


class ExecutorTest(unittest.TestCase):
    def test_blocks_shell_operators(self):
        allowed, reason = is_safe_command("echo ok && rm -rf /")

        self.assertFalse(allowed)
        self.assertIn("shell", reason)

    def test_blocks_mutating_systemctl_actions(self):
        allowed, reason = is_safe_command("systemctl restart nginx")

        self.assertFalse(allowed)
        self.assertIn("systemctl", reason)

    def test_blocks_mutating_sudo_docker_actions(self):
        allowed, reason = is_safe_command("sudo docker restart web")

        self.assertFalse(allowed)
        self.assertIn("docker", reason)

    def test_dry_run_safe_command(self):
        results = execute_command(["df -h"], dry_run=True)

        self.assertEqual(results[0].status, "dry-run")


if __name__ == "__main__":
    unittest.main()
