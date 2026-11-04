"""Run real code, save actual outputs/traces, and verify business invariants.

Offline mock results are NOT evidence of model decision quality.
Live mode executes the same scenarios using configured provider tool calls.
"""
import argparse
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scheduling_agent.cli import load_json, write_json
from scheduling_agent.domain import digest
from scheduling_agent.engine import Agent
from scheduling_agent.models import ChatModel, MockModel
from scheduling_agent.store import Store


def req(case, mid="M01", hour=17, **extra):
    return {"request_id": case, "material_ids": [mid], "channel": "douyin",
            "preferred_slot": f"2026-11-05T{hour:02}:00+08:00", "hard_time": True, **extra}


def cases():
    return [
        ("normal", req("normal"), "draft_ready", None, 40, None),
        ("conflict", req("conflict", hour=18), "awaiting_confirmation", None, 40, None),
        ("missing", req("missing", "M03"), "needs_info", None, 40, None),
        ("risk", req("risk", "M04"), "blocked", None, 40, None),
        ("save_failure", req("save_failure"), "save_failed", "save_draft", 40, None),
        ("duplicate", req("duplicate", hour=18), "awaiting_confirmation", None, 40, None),
        ("supplement", req("supplement", "M02"), "draft_ready", None, 40, None),
        ("confirmed", req("confirmed", hour=18, approved_slots={"M01": "2026-11-05T19:00+08:00"}), "draft_ready", None, 40, None),
        ("changed_occupancy", req("changed_occupancy", hour=18), "awaiting_confirmation", None, 40, "occupy_19"),
        ("no_slots", req("no_slots"), "no_available_slot", None, 40, "occupy_all"),
        ("step_limit", req("step_limit"), "incomplete_step_limit", None, 2, None),
        ("batch", req("batch", material_ids=["M01", "M06"]), "draft_ready", None, 40, None),
        ("privacy_copyright", req("privacy_copyright", "M05"), "blocked", None, 40, None),
    ]


def source_digest():
    return digest({str(p.relative_to(ROOT)).replace("\\", "/"): p.read_text(encoding="utf-8")
                   for folder in ("src", "tests", "scripts") for p in sorted((ROOT / folder).rglob("*.py"))})


def evaluate(mode, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    summary = {"mode": "offline_mock" if mode == "mock" else "live_model",
               "generated_at_utc": datetime.now(timezone.utc).isoformat(),
               "python": platform.python_version(), "platform": platform.platform(),
               "source_sha256": source_digest(), "cases": [],
               "real_model_decision_quality_verified": False,
               "boundary": "Automatic business assertions only; manually inspect live traces for decision quality."}
    base = load_json(ROOT / "data/fixtures.json")
    started = time.monotonic()
    for name, request, expected, fault, max_steps, variant in cases():
        data = copy.deepcopy(base)
        if variant:
            hours = (19,) if variant == "occupy_19" else (17, 19, 20)
            for hour in hours:
                data["existing_schedule"].append({"id": f"variant-{hour}", "channel": "douyin",
                    "start": f"2026-11-05T{hour}:00+08:00", "end": f"2026-11-05T{hour+1}:00+08:00"})
        write_json(ROOT / "examples/inputs" / f"{name}.json", request)
        case_dir = destination / name
        write_json(case_dir / "input.json", request)
        write_json(case_dir / "dataset.json", data)
        before_count = None
        first = None
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp) / "drafts.sqlite", data)
            try:
                if name in {"duplicate", "confirmed", "changed_occupancy"}:
                    original = copy.deepcopy(request)
                    original["approved_slots"] = {}
                    original["request_id"] = name if name != "confirmed" else "before-confirmation"
                    model = MockModel() if mode == "mock" else ChatModel()
                    first = Agent(model, store, data).run(original)
                    write_json(case_dir / "first_run.json", first)
                    before_count = store.count()
                model = MockModel() if mode == "mock" else ChatModel()
                result = Agent(model, store, data, max_steps=max_steps, fault=fault).run(request)
                write_json(case_dir / "result.json", result)
                count = store.count()
                rows = [dict(r) for r in store.db.execute("SELECT * FROM drafts ORDER BY id")]
                write_json(case_dir / "database_snapshot.json", {"draft_count": count, "drafts": rows})
            finally:
                store.close()
        checks = {
            "expected_first_item_status": result["items"][0]["status"] == expected,
            "draft_only": all(i["published"] is False for i in result["items"]),
            "original_time_preserved": all(i["requested_slot"] == request["preferred_slot"] for i in result["items"]),
            "bounded_calls": result["model_calls"] <= max_steps and result["tool_calls"] <= max_steps,
            "save_claims_match_database": all(i["draft_save_status"] != "saved" or
                                any(r["id"] == i["draft_id"] for r in rows) for i in result["items"]),
        }
        if name in {"normal", "supplement"}:
            checks["exact_requested_slot"] = result["items"][0]["suggested_slot"] == request["preferred_slot"]
        if name in {"missing", "risk", "save_failure", "no_slots", "step_limit", "privacy_copyright"}:
            checks["no_draft_created"] = count == 0
        if name in {"conflict", "duplicate", "changed_occupancy"}:
            selected = "2026-11-05T20:00+08:00" if name == "changed_occupancy" else "2026-11-05T19:00+08:00"
            checks["expected_alternative"] = result["items"][0]["suggested_slot"] == selected
            checks["pending_exact_user_confirmation"] = bool(result["items"][0]["pending_confirmation"])
        if first:
            checks["same_draft_id"] = result["items"][0]["draft_id"] == first["items"][0]["draft_id"]
            checks["single_persisted_draft"] = before_count == count == 1
        if name == "confirmed":
            checks["trusted_approval_applied"] = bool(result["items"][0]["save_receipt"]) and result["items"][0]["save_receipt"]["confirmation"] == "confirmed"
        if name == "batch":
            checks["two_distinct_nonconflicting_drafts"] = count == 2 and len({r["slot"] for r in rows}) == 2
            checks["second_item_requires_confirmation"] = result["items"][1]["status"] == "awaiting_confirmation"
        record = {"case": name, "expected_status": expected,
                  "actual_status": result["items"][0]["status"], "checks": checks,
                  "passed": all(checks.values()), "result": f"{name}/result.json",
                  "model_calls": result["model_calls"], "fault": fault}
        summary["cases"].append(record)
        print(f"{name}: {'PASS' if record['passed'] else 'FAIL'} ({record['actual_status']})", flush=True)
    summary["duration_seconds"] = round(time.monotonic() - started, 3)
    summary["passed"] = sum(c["passed"] for c in summary["cases"])
    summary["total"] = len(summary["cases"])
    if mode == "mock":
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        stream = io.StringIO()
        test_result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        (destination / "tests.txt").write_text(stream.getvalue(), encoding="utf-8")
        summary["unit_tests"] = {"run": test_result.testsRun, "failures": len(test_result.failures),
                                 "errors": len(test_result.errors), "passed": test_result.wasSuccessful()}
    write_json(destination / "summary.json", summary)
    lines = ["# Actual evaluation report", "", f"Mode: **{summary['mode']}**", "",
             "Mock results verify workflow and boundaries only; real model decisions remain unverified." if mode == "mock"
             else "Live tool calls were used. Inspect actual traces before claiming model decision quality.", "",
             "| Case | Expected | Actual | Checks |", "|---|---|---|---|"]
    lines += [f"| [{r['case']}]({r['result']}) | {r['expected_status']} | {r['actual_status']} | {'PASS' if r['passed'] else 'FAIL'} |"
              for r in summary["cases"]]
    lines += ["", f"Passed: {summary['passed']}/{summary['total']}", "", f"Source SHA-256: `{summary['source_sha256']}`", ""]
    (destination / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if summary["passed"] == summary["total"] and summary.get("unit_tests", {}).get("passed", True) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["mock", "live"], default="mock")
    parser.add_argument("--output", help="Keep live runs separate from the submitted offline evidence")
    args = parser.parse_args()
    output = args.output or str(ROOT / "examples/runs" / args.model)
    try:
        raise SystemExit(evaluate(args.model, output))
    except ValueError as exc:
        parser.exit(4, f"Configuration error: {exc}\n")
