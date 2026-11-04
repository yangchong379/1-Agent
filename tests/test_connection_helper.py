import contextlib
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from connect_deepseek import connect


class ConnectionHelperTests(unittest.TestCase):
    def test_hidden_input_configures_live_and_restores_environment(self):
        captured = io.StringIO()
        def fake_runner(args):
            self.assertEqual(os.environ["MODEL_BASE_URL"], "https://api.deepseek.com")
            self.assertEqual(os.environ["MODEL_NAME"], "deepseek-flash")
            self.assertEqual(os.environ["MODEL_API_KEY"], "fake-test-secret")
            self.assertIn("live", args)
            self.assertIn("12", args)
            return 0
        with patch.dict(os.environ, {"MODEL_API_KEY": "previous-test-value"}), contextlib.redirect_stdout(captured):
            self.assertEqual(connect(lambda prompt: "fake-test-secret", fake_runner), 0)
            self.assertEqual(os.environ["MODEL_API_KEY"], "previous-test-value")
        self.assertNotIn("fake-test-secret", captured.getvalue())

    def test_invalid_inputs_never_call_model_or_echo_input(self):
        for value in ("", "*********", "PS E:\\example>", "line\nbreak"):
            captured = io.StringIO()
            with self.subTest(value=value), contextlib.redirect_stdout(captured):
                def unexpected(args):
                    self.fail("Invalid credential must not reach model")
                self.assertEqual(connect(lambda prompt: value, unexpected), 4)

    def test_runner_error_still_removes_temporary_key(self):
        def broken(args):
            raise RuntimeError("test failure")
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                connect(lambda prompt: "fake-test-secret", broken)
            self.assertNotIn("MODEL_API_KEY", os.environ)


if __name__ == "__main__":
    unittest.main()
