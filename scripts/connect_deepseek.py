"""One-command official DeepSeek connection, with hidden local credential input."""
import getpass
import argparse
import json
import os
from pathlib import Path
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scheduling_agent.cli import main


def read_secret(prompt):
    if sys.platform != "win32":
        return getpass.getpass(prompt)
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        raise RuntimeError("Windows password dialog requires tkinter") from None
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        value = simpledialog.askstring(
            "DeepSeek API Key", "在这里粘贴新 API Key，然后点 OK。\n输入以星号显示，不会保存到文件。",
            show="*", parent=root)
        return value or ""
    except tk.TclError:
        raise RuntimeError("Cannot open password dialog") from None
    finally:
        if root is not None:
            root.destroy()


def failed_retry_plan(root=ROOT):
    source = root / "examples/runs/live/summary.json"
    if not source.exists():
        raise ValueError("第一轮评估尚未结束，或缺少 examples/runs/live/summary.json。请先等待第一轮运行结束。")
    summary = json.loads(source.read_text(encoding="utf-8"))
    if summary.get("mode") != "live_model":
        raise ValueError("失败重跑仅接受真实模型评估记录。")
    names = [case["case"] for case in summary["cases"] if not case["passed"]]
    number = 1
    while (root / f"examples/runs/live-retry-{number}").exists():
        number += 1
    return names, root / f"examples/runs/live-retry-{number}"


def connect(secret_reader=None, runner=None, full_evaluation=False, evaluation_runner=None, retry_failed=False):
    secret_reader = secret_reader or read_secret
    runner = runner or main
    retry_names, destination = None, ROOT / "examples/runs/live"
    if retry_failed:
        try:
            retry_names, destination = failed_retry_plan()
        except (ValueError, OSError, KeyError):
            print("请先等待第一轮真实评估完整结束并生成 examples/runs/live/summary.json，再重跑失败项。")
            return 4
        if not retry_names:
            print("第一轮没有失败项，无需调用模型。")
            return 0
        full_evaluation = True
        print("仅重跑失败项：" + ", ".join(retry_names))
    print(f"将运行{len(retry_names) if retry_names else 13}组真实模型评估，会进行多次付费 API 调用。" if full_evaluation
          else "将运行一次真实模型排期案例，会消耗 DeepSeek API 额度。")
    print("密钥仅在本机隐藏输入，不写入文件；请勿输入星号或 PowerShell 提示符。")
    if sys.platform == "win32":
        print("请在即将弹出的密码输入窗口中粘贴密钥，再点 OK。", flush=True)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            secret = secret_reader("请粘贴新 API Key，然后按回车（输入不会显示）: ").strip()
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("已取消或终端不支持隐藏输入。请在本机交互式 PowerShell 中重新运行。")
        return 4
    except RuntimeError:
        print("无法打开密码输入窗口。请使用带 tkinter 的本机 Python 3.11，并在桌面会话中重试。")
        return 4
    if not secret or set(secret) == {"*"} or any(not 33 <= ord(c) <= 126 for c in secret):
        print("未读取到有效密钥。请粘贴实际 API Key，不要粘贴星号、命令或提示符。")
        return 4
    settings = {"MODEL_BASE_URL": "https://api.deepseek.com", "MODEL_NAME": "deepseek-flash",
                "MODEL_THINKING": "disabled", "MODEL_API_KEY": secret}
    previous = {name: os.environ.get(name) for name in settings}
    try:
        os.environ.update(settings)
        if full_evaluation:
            if evaluation_runner is None:
                from evaluate import evaluate
                evaluation_runner = evaluate
            print("正在执行完整真实模型评估；每组结束会显示结果，请保持窗口打开。", flush=True)
            if retry_names:
                return evaluation_runner("live", str(destination), case_names=retry_names)
            return evaluation_runner("live", str(destination))
        print("正在连接模型，请等待；运行记录会保存到 examples/runs/live-conflict.json。", flush=True)
        return runner(["--model", "live", "--max-steps", "12",
                       "--input", str(ROOT / "examples/inputs/conflict.json"),
                       "--data", str(ROOT / "data/fixtures.json"),
                       "--db", str(ROOT / ".runtime/live-conflict.sqlite"),
                       "--output", str(ROOT / "examples/runs/live-conflict.json")])
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--evaluate", action="store_true", help="Run all 13 live evaluation scenarios using one hidden key input")
    group.add_argument("--retry-failed", action="store_true", help="Retry failed scenarios only; retain first run and write a new live-retry-N folder")
    args = parser.parse_args()
    if sys.platform != "win32" and not sys.stdin.isatty():
        print("请在交互式 PowerShell 中运行本命令；不要使用管道或重定向输入密钥。")
        raise SystemExit(4)
    raise SystemExit(connect(full_evaluation=args.evaluate, retry_failed=args.retry_failed))
