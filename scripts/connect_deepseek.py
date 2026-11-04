"""One-command official DeepSeek connection, with hidden local credential input."""
import getpass
import os
from pathlib import Path
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scheduling_agent.cli import main


def connect(secret_reader=None, runner=None):
    secret_reader = secret_reader or getpass.getpass
    runner = runner or main
    print("将运行一次真实模型排期案例，会消耗 DeepSeek API 额度。")
    print("密钥仅在本机隐藏输入，不写入文件；请勿输入星号或 PowerShell 提示符。")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            secret = secret_reader("请粘贴新 API Key，然后按回车（输入不会显示）: ").strip()
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("已取消或终端不支持隐藏输入。请在本机交互式 PowerShell 中重新运行。")
        return 4
    if not secret or set(secret) == {"*"} or any(not 33 <= ord(c) <= 126 for c in secret):
        print("未读取到有效密钥。请粘贴实际 API Key，不要粘贴星号、命令或提示符。")
        return 4
    settings = {"MODEL_BASE_URL": "https://api.deepseek.com", "MODEL_NAME": "deepseek-flash",
                "MODEL_THINKING": "disabled", "MODEL_API_KEY": secret}
    previous = {name: os.environ.get(name) for name in settings}
    try:
        os.environ.update(settings)
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
    if not sys.stdin.isatty():
        print("请在交互式 PowerShell 中运行本命令；不要使用管道或重定向输入密钥。")
        raise SystemExit(4)
    raise SystemExit(connect())
