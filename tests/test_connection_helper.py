import contextlib
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from connect_deepseek import connect, read_secret


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

    def test_windows_dialog_masks_input_and_destroys_window(self):
        tk = MagicMock()
        tk.TclError = RuntimeError
        tk.simpledialog.askstring.return_value = "fake-test-secret"
        with patch("connect_deepseek.sys.platform", "win32"), patch.dict(sys.modules, {
                "tkinter": tk, "tkinter.simpledialog": tk.simpledialog}):
            self.assertEqual(read_secret("prompt"), "fake-test-secret")
        self.assertEqual(tk.simpledialog.askstring.call_args.kwargs["show"], "*")
        tk.Tk.return_value.destroy.assert_called_once()

    def test_cancelled_windows_dialog_does_not_call_model(self):
        tk = MagicMock()
        tk.TclError = RuntimeError
        tk.simpledialog.askstring.return_value = None
        runner = MagicMock()
        with patch("connect_deepseek.sys.platform", "win32"), patch.dict(sys.modules, {
                "tkinter": tk, "tkinter.simpledialog": tk.simpledialog}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(connect(runner=runner), 4)
        runner.assert_not_called()
        tk.Tk.return_value.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
