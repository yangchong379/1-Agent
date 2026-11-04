"""No-install entry point: python scripts/run.py --input ..."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scheduling_agent.cli import main

raise SystemExit(main())
