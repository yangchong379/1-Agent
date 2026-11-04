import argparse
import json
from pathlib import Path
import sqlite3
import sys
from .engine import Agent
from .models import ChatModel, MockModel
from .store import Store


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Material review and scheduling; drafts ONLY")
    parser.add_argument("--input", required=True, help="User-authorized request JSON")
    parser.add_argument("--data", default="data/fixtures.json", help="Synthetic dataset JSON")
    parser.add_argument("--db", default=".runtime/drafts.sqlite")
    parser.add_argument("--output", default=".runtime/result.json")
    parser.add_argument("--model", choices=["mock", "live"], default="mock")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--fault", choices=["save_draft", "read_material", "query_slots"],
                        help="Explicit synthetic tool failure injection")
    args = parser.parse_args(argv)
    store = None
    try:
        data, req = load_json(args.data), load_json(args.input)
        model = MockModel() if args.model == "mock" else ChatModel()
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)
        store = Store(args.db, data)
        result = Agent(model, store, data, args.max_steps, args.fault).run(req)
        result["invocation"] = {"input": args.input, "data": args.data,
                                "fault": args.fault, "database": args.db}
        write_json(args.output, result)
        print(json.dumps({"output": args.output, "mode": result["mode"],
                          "items": [{"material_id": i["material_id"], "status": i["status"],
                                     "draft_save_status": i["draft_save_status"]} for i in result["items"]]}, ensure_ascii=False))
        if not result["execution_complete"]:
            return 3
        return 0 if result["all_drafts_saved"] else 2
    except (ValueError, OSError, sqlite3.Error) as exc:
        # No provider response bodies or environment values are printed.
        print(json.dumps({"error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 4
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    sys.exit(main())
