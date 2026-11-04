import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scheduling_agent.domain import validate_request
from scheduling_agent.engine import Agent, initial_state
from scheduling_agent.models import Action, ChatModel, MockModel, ModelError, ModelProtocolError
from scheduling_agent.store import Store

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return json.loads((ROOT / "data/fixtures.json").read_text(encoding="utf-8"))


def request(mid="M01", hour=17, **kwargs):
    return {"request_id": "test-request", "material_ids": [mid], "channel": "douyin",
            "preferred_slot": f"2026-11-05T{hour:02}:00+08:00", "hard_time": True, **kwargs}


def tools(result):
    return [e["action"]["tool"] for e in result["trace"] if "action" in e]


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = fixture()
        self.path = Path(self.temp.name) / "drafts.sqlite"
        self.store = Store(self.path, self.data)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def run_agent(self, req=None, **kwargs):
        return Agent(MockModel(), self.store, self.data, **kwargs).run(req or request())

    def test_normal_exact_slot_draft_only(self):
        result = self.run_agent()
        self.assertEqual(result["items"][0]["status"], "draft_ready")
        self.assertEqual(result["items"][0]["suggested_slot"], request()["preferred_slot"])
        self.assertFalse(result["items"][0]["published"])
        self.assertEqual(tools(result), ["read_material", "check_rules", "query_slots", "save_draft", "finish"])
        self.assertEqual(self.store.count(), 1)

    def test_conflict_preserves_hard_time_and_requires_consent(self):
        req = request(hour=18)
        result = self.run_agent(req)
        item = result["items"][0]
        self.assertEqual(item["status"], "awaiting_confirmation")
        self.assertEqual(item["suggested_slot"], "2026-11-05T19:00+08:00")
        self.assertEqual(item["requested_slot"], req["preferred_slot"])
        self.assertEqual(item["save_receipt"]["confirmation"], "pending_user")
        self.assertTrue(item["pending_confirmation"])

    def test_missing_data_supplement_unresolved(self):
        result = self.run_agent(request("M03"))
        self.assertEqual(result["items"][0]["status"], "needs_info")
        self.assertIn("copyright", result["items"][0]["missing_fields"])
        self.assertIn("supplement_metadata", tools(result))
        self.assertNotIn("save_draft", tools(result))
        self.assertEqual(self.store.count(), 0)

    def test_supplement_changes_next_action(self):
        result = self.run_agent(request("M02"))
        self.assertEqual(result["items"][0]["status"], "draft_ready")
        sequence = tools(result)
        index = sequence.index("supplement_metadata")
        self.assertEqual(sequence[index + 1:index + 3], ["check_rules", "query_slots"])

    def test_rule_risk_blocks(self):
        result = self.run_agent(request("M04"))
        item = result["items"][0]
        self.assertEqual(item["status"], "blocked")
        self.assertEqual(item["risk_reasons"][0]["code"], "PROHIBITED_CLAIM")
        self.assertEqual(self.store.count(), 0)

    def test_copyright_and_privacy_both_reported(self):
        result = self.run_agent(request("M05"))
        self.assertEqual({r["code"] for r in result["items"][0]["risk_reasons"]},
                         {"COPYRIGHT_DENIED", "PRIVACY_RISK"})

    def test_duplicate_persists_across_connection_and_request_ids(self):
        first = self.run_agent(request(hour=18))
        self.store.close()
        self.store = Store(self.path, self.data)
        second = self.run_agent(request(hour=18))
        third = self.run_agent(request(hour=18, request_id="new-id-same-business"))
        self.assertEqual(first["items"][0]["draft_id"], second["items"][0]["draft_id"])
        self.assertEqual(second["items"][0]["save_receipt"]["code"], "DUPLICATE")
        self.assertEqual(third["items"][0]["draft_id"], first["items"][0]["draft_id"])
        self.assertEqual(self.store.count(), 1)

    def test_explicit_exact_approval_updates_same_draft(self):
        first = self.run_agent(request(hour=18))
        second = self.run_agent(request(hour=18, request_id="approval-event",
                        approved_slots={"M01": "2026-11-05T19:00+08:00"}))
        self.assertEqual(second["items"][0]["status"], "draft_ready")
        self.assertEqual(first["items"][0]["draft_id"], second["items"][0]["draft_id"])
        self.assertEqual(second["items"][0]["save_receipt"]["code"], "UPDATED")
        self.assertEqual(self.store.count(), 1)
        # An old unapproved request cannot downgrade confirmed state.
        third = self.run_agent(request(hour=18))
        self.assertEqual(third["items"][0]["save_receipt"]["confirmation"], "confirmed")

    def test_approval_is_scoped_to_exact_slot(self):
        req = validate_request(request(hour=18, approved_slots={"M01": "2026-11-05T20:00+08:00"}))
        receipt = self.store.save(req, "M01", "2026-11-05T19:00+08:00")
        self.assertEqual(receipt["confirmation"], "pending_user")

    def test_flexible_time_allows_alternative(self):
        result = self.run_agent(request(hour=18, hard_time=False))
        self.assertEqual(result["items"][0]["status"], "draft_ready")

    def test_save_failure_rolls_back_and_is_explicit(self):
        result = self.run_agent(fault="save_draft")
        item = result["items"][0]
        self.assertEqual(item["status"], "save_failed")
        self.assertEqual(item["draft_save_status"], "failed")
        self.assertIsNone(item["draft_id"])
        self.assertFalse(result["all_drafts_saved"])
        self.assertEqual(tools(result).count("save_draft"), 2)
        self.assertEqual(self.store.count(), 0)

    def test_sqlite_transaction_start_failure_is_explicit(self):
        def deny_begin(action, first, second, db, trigger):
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_TRANSACTION and first == "BEGIN" else sqlite3.SQLITE_OK
        self.store.db.set_authorizer(deny_begin)
        result = self.store.save(validate_request(request()), "M01", request()["preferred_slot"])
        self.store.db.set_authorizer(None)
        self.assertEqual(result["code"], "SAVE_FAILED")
        self.assertEqual(self.store.count(), 0)

    def test_step_limit_is_global_and_returns_all_items(self):
        result = self.run_agent(request(material_ids=["M01", "M02"]), max_steps=2)
        self.assertEqual(result["model_calls"], 2)
        self.assertFalse(result["execution_complete"])
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(all(i["status"] == "incomplete_step_limit" for i in result["items"]))

    def test_tool_failure_cannot_be_success(self):
        result = self.run_agent(fault="query_slots", max_steps=8)
        self.assertEqual(result["items"][0]["status"], "incomplete_step_limit")
        self.assertEqual(self.store.count(), 0)
        self.assertTrue(any(e["observation"].get("code") == "TOOL_UNAVAILABLE" for e in result["trace"]))

    def test_unknown_material_does_not_schedule(self):
        result = self.run_agent(request("M404"))
        self.assertEqual(result["items"][0]["status"], "needs_info")
        self.assertEqual(self.store.count(), 0)

    def test_no_slots_ends_without_save(self):
        for hour in (17, 19, 20):
            self.store.db.execute("INSERT INTO schedules VALUES(?,?,?,?)", (
                f"extra-{hour}", "douyin", f"2026-11-05T{hour}:00+08:00", f"2026-11-05T{hour+1}:00+08:00"))
        result = self.run_agent()
        self.assertEqual(result["items"][0]["status"], "no_available_slot")
        self.assertEqual(self.store.count(), 0)

    def test_changed_occupancy_changes_selected_slot(self):
        self.store.db.execute("INSERT INTO schedules VALUES(?,?,?,?)", (
            "extra-19", "douyin", "2026-11-05T19:00+08:00", "2026-11-05T20:00+08:00"))
        result = self.run_agent(request(hour=18))
        self.assertEqual(result["items"][0]["suggested_slot"], "2026-11-05T20:00+08:00")
        self.assertEqual(self.run_agent(request(hour=18))["items"][0]["save_receipt"]["code"], "DUPLICATE")

    def test_multiple_items_do_not_conflict(self):
        result = self.run_agent(request(material_ids=["M01", "M06"]))
        self.assertEqual([i["suggested_slot"] for i in result["items"]],
                         ["2026-11-05T17:00+08:00", "2026-11-05T19:00+08:00"])
        self.assertEqual(self.store.count(), 2)

    def test_reused_request_id_different_payload_rejected(self):
        self.run_agent()
        with self.assertRaisesRegex(ValueError, "REQUEST_ID_REUSED"):
            self.run_agent(request(hour=18))
        self.assertEqual(self.store.count(), 1)

    def test_new_request_cannot_silently_change_existing_requirement(self):
        self.run_agent()
        result = self.run_agent(request(hour=19, request_id="change"))
        self.assertEqual(result["items"][0]["status"], "needs_confirmation")
        self.assertEqual(self.store.draft("M01", "douyin")["slot"], request()["preferred_slot"])

    def test_interval_conflict_and_boundary(self):
        self.store.db.execute("INSERT INTO schedules VALUES(?,?,?,?)", (
            "half-hour", "other", "2026-11-05T17:30+08:00", "2026-11-05T18:30+08:00"))
        self.assertEqual(self.store.conflicts("other", "2026-11-05T17:00+08:00", "M01"), ["half-hour"])
        self.assertEqual(self.store.conflicts("other", "2026-11-05T18:30+08:00", "M01"), [])

    def test_race_query_then_save_rechecks_current_occupancy(self):
        agent = Agent(MockModel(), self.store, self.data)
        req, state = validate_request(request()), initial_state("M01")
        for name in ("read_material", "check_rules", "query_slots"):
            self.assertTrue(agent.execute(req, state, Action(name))["ok"])
        self.store.db.execute("INSERT INTO schedules VALUES(?,?,?,?)", (
            "racing", "douyin", "2026-11-05T17:00+08:00", "2026-11-05T18:00+08:00"))
        result = agent.execute(req, state, Action("save_draft", {"slot": req["preferred_slot"]}))
        self.assertEqual(result["code"], "SLOT_CONFLICT")
        self.assertEqual(self.store.count(), 0)

    def test_model_cannot_forge_confirmation_or_publish(self):
        agent = Agent(MockModel(), self.store, self.data)
        req, state = validate_request(request()), initial_state("M01")
        self.assertEqual(agent.execute(req, state, Action("publish"))["code"], "UNKNOWN_TOOL")
        forged = Action("save_draft", {"slot": req["preferred_slot"], "confirmed": True})
        self.assertEqual(agent.execute(req, state, forged)["code"], "INVALID_TOOL_ARGUMENTS")
        self.assertEqual(agent.execute(req, state, Action("save_draft", {"slot": req["preferred_slot"]}))["code"], "REVIEW_REQUIRED")
        self.assertEqual(agent.execute(req, state, Action("finish"))["code"], "FINISH_REQUIRES_EVIDENCE")
        self.assertEqual(self.store.count(), 0)

    def test_observed_write_conflict_causes_requery_then_alternative(self):
        original_save = self.store.save
        injected = False
        def racing_save(req, material_id, slot, fail=False):
            nonlocal injected
            if not injected:
                injected = True
                self.store.db.execute("INSERT INTO schedules VALUES(?,?,?,?)", (
                    "race-17", "douyin", "2026-11-05T17:00+08:00", "2026-11-05T18:00+08:00"))
            return original_save(req, material_id, slot, fail)
        self.store.save = racing_save
        result = self.run_agent()
        self.assertEqual(result["items"][0]["status"], "awaiting_confirmation")
        self.assertEqual(result["items"][0]["suggested_slot"], "2026-11-05T19:00+08:00")
        sequence = tools(result)
        index = sequence.index("save_draft")
        self.assertEqual(sequence[index:index+4], ["save_draft", "query_slots", "save_draft", "finish"])

    def test_failed_approval_update_preserves_pending_draft(self):
        self.run_agent(request(hour=18))
        result = self.run_agent(request(hour=18, request_id="confirm-failure",
                          approved_slots={"M01": "2026-11-05T19:00+08:00"}), fault="save_draft")
        self.assertEqual(result["items"][0]["status"], "save_failed")
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(self.store.draft("M01", "douyin")["confirmation"], "pending_user")

    def test_model_cannot_save_risky_material(self):
        agent = Agent(MockModel(), self.store, self.data)
        req, state = validate_request(request("M04")), initial_state("M04")
        for tool in ("read_material", "check_rules", "query_slots"):
            agent.execute(req, state, Action(tool))
        self.assertEqual(agent.execute(req, state, Action("save_draft", {"slot": req["preferred_slot"]}))["code"], "REVIEW_NOT_APPROVED")

    def test_save_without_slot_observation_rejected(self):
        agent = Agent(MockModel(), self.store, self.data)
        req, state = validate_request(request()), initial_state("M01")
        for tool in ("read_material", "check_rules"):
            agent.execute(req, state, Action(tool))
        self.assertEqual(agent.execute(req, state, Action("save_draft", {"slot": req["preferred_slot"]}))["code"], "AVAILABLE_SLOT_OBSERVATION_REQUIRED")

    def test_model_error_is_incomplete_with_explicit_code(self):
        class Broken(MockModel):
            def choose(self, *args):
                raise ModelError("MODEL_HTTP_401")
        result = Agent(Broken(), self.store, self.data).run(request())
        self.assertEqual(result["items"][0]["status"], "incomplete_model_error")
        self.assertEqual(result["items"][0]["error"], "MODEL_HTTP_401")

    def test_protocol_rejection_is_visible_and_recovery_counts_towards_budget(self):
        class OnceRejected(MockModel):
            def choose(self, req, state, history):
                if not history:
                    raise ModelProtocolError(0)
                return super().choose(req, state, history)
        result = Agent(OnceRejected(), self.store, self.data).run(request())
        self.assertEqual(result["items"][0]["status"], "draft_ready")
        self.assertIsNone(result["items"][0]["error"])
        self.assertEqual(result["model_calls"], 6)
        self.assertEqual(result["tool_calls"], 5)
        self.assertEqual(result["protocol_rejections"], 1)
        self.assertEqual(result["trace"][0]["diagnostics"]["tool_calls_count"], 0)

    def test_repeated_protocol_rejections_stop_at_global_limit(self):
        class AlwaysRejected(MockModel):
            def choose(self, *args):
                raise ModelProtocolError(2)
        result = Agent(AlwaysRejected(), self.store, self.data, max_steps=3).run(request())
        self.assertEqual(result["model_calls"], 3)
        self.assertEqual(result["tool_calls"], 0)
        self.assertEqual(result["items"][0]["status"], "incomplete_step_limit")
        self.assertEqual(self.store.count(), 0)

    def test_saved_review_snapshot_survives_observed_post_save_reread(self):
        # Regression reproduces the first item's actual live-retry batch path.
        # This is an offline reporting test, not a new live model evaluation.
        sequence = iter([Action("read_material"), Action("check_rules"), Action("query_slots"),
                         Action("save_draft", {"slot": request()["preferred_slot"]}),
                         Action("read_material"), Action("finish")])
        class Replay(MockModel):
            name = "offline-test-of-observed-post-save-reread"
            def choose(self, *args):
                return next(sequence)
        result = Agent(Replay(), self.store, self.data).run(request())
        item = result["items"][0]
        self.assertEqual(item["status"], "draft_ready")
        self.assertEqual(item["review_status"], "approved")
        self.assertEqual(item["review_basis"], "at_successful_save")
        self.assertEqual(item["draft_save_status"], "saved")

    def test_dataset_change_refuses_silent_reset(self):
        changed = copy.deepcopy(self.data)
        changed["rules"]["blocked_phrases"].append("changed")
        with self.assertRaisesRegex(ValueError, "dataset changed"):
            Store(self.path, changed)

    def test_invalid_user_inputs(self):
        cases = [request(hard_time="false"), request(material_ids=["M01", "M01"]),
                 request(preferred_slot="2026-11-05T17:00"),
                 request(approved_slots={"M02": "2026-11-05T19:00+08:00"}),
                 request(publish=True), request(material_ids=[])]
        for req in cases:
            with self.subTest(req=req), self.assertRaises(ValueError):
                validate_request(req)

    def test_concurrent_duplicate_only_one_draft(self):
        self._concurrent(["M01", "M01"], expected_success=2, expected_count=1)

    def test_concurrent_different_materials_same_slot_only_one_succeeds(self):
        self._concurrent(["M01", "M06"], expected_success=1, expected_count=1)

    def _concurrent(self, ids, expected_success, expected_count):
        barrier = threading.Barrier(2)
        def worker(mid):
            store = Store(self.path, self.data)
            try:
                req = validate_request(request(mid))
                store.query(req, mid)
                barrier.wait(timeout=5)
                return store.save(req, mid, req["preferred_slot"])
            finally:
                store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, ids))
        self.assertEqual(sum(r["ok"] for r in results), expected_success)
        self.assertEqual(self.store.count(), expected_count)


class FakeResponse:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return self.body


class ModelAdapterTests(unittest.TestCase):
    def fake_model(self, message):
        class Opener:
            def __init__(self):
                self.requests = []
            def open(self, req, timeout):
                self.requests.append(json.loads(req.data))
                return FakeResponse(json.dumps({"choices": [{"message": message}]}).encode())
        self.opener = Opener()
        return ChatModel("https://example.invalid/v1", "test-model", "fake-test-key", opener=self.opener)

    def test_real_adapter_sends_observations_and_replays_provider_call_id(self):
        message = {"role": "assistant", "content": None, "reasoning_content": "PRIVATE-REASONING",
                   "tool_calls": [{"id": "provider-original-id", "type": "function", "function": {
                       "name": "read_material", "arguments": '{"rationale":"read metadata"}'}}]}
        model = self.fake_model(message)
        state, req = initial_state("M01"), validate_request(request())
        first = model.choose(req, state, [])
        history = [{"action": {"tool": first.tool, "arguments": first.arguments, "rationale": first.rationale},
                    "observation": {"ok": True, "material": {"title": "OBSERVED-TITLE"}}}]
        model.choose(req, state, history)
        payload = self.opener.requests[-1]
        self.assertEqual(payload["messages"][-1]["role"], "tool")
        self.assertEqual(payload["messages"][-1]["tool_call_id"], "provider-original-id")
        self.assertIn("OBSERVED-TITLE", payload["messages"][-1]["content"])
        self.assertEqual(payload["messages"][-2]["reasoning_content"], "PRIVATE-REASONING")
        self.assertNotIn("PRIVATE-REASONING", json.dumps(history))
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertNotIn("parallel_tool_calls", payload)

    def test_multiple_tool_calls_rejected(self):
        model = self.fake_model({"role": "assistant", "content": None, "tool_calls": [
            {"id": "one", "type": "function", "function": {"name": "check_rules", "arguments": "{}"}},
            {"id": "two", "type": "function", "function": {"name": "query_slots", "arguments": "{}"}}]})
        with self.assertRaisesRegex(ModelError, "MODEL_EXPECTED_ONE_TOOL_CALL"):
            model.choose(validate_request(request()), initial_state("M01"), [])

    def test_non_thinking_mode_requires_a_tool(self):
        message = {"role": "assistant", "content": None, "tool_calls": [{"id": "call-one", "function": {
            "name": "read_material", "arguments": '{"rationale":"read"}'}}]}
        model = self.fake_model(message)
        with patch.dict("os.environ", {"MODEL_THINKING": "disabled"}):
            model.choose(validate_request(request()), initial_state("M01"), [])
        self.assertEqual(self.opener.requests[-1]["tool_choice"], "required")
        self.assertEqual(self.opener.requests[-1]["thinking"]["type"], "disabled")

    def test_parallel_batch_rejection_replays_results_for_every_original_call(self):
        message = {"role": "assistant", "content": None, "tool_calls": [
            {"id": "one", "type": "function", "function": {"name": "check_rules", "arguments": "{}"}},
            {"id": "two", "type": "function", "function": {"name": "query_slots", "arguments": "{}"}}]}
        model = self.fake_model(message)
        req, state = validate_request(request()), initial_state("M01")
        with self.assertRaises(ModelProtocolError):
            model.choose(req, state, [])
        message["tool_calls"] = [{"id": "three", "type": "function", "function": {
            "name": "read_material", "arguments": '{"rationale":"read first"}'}}]
        model.choose(req, state, [{"recoverable": True, "model_error": "MODEL_EXPECTED_ONE_TOOL_CALL"}])
        messages = self.opener.requests[-1]["messages"]
        replies = [m for m in messages if m["role"] == "tool"]
        self.assertEqual([m["tool_call_id"] for m in replies], ["one", "two"])
        self.assertTrue(all(json.loads(m["content"])["executed"] is False for m in replies))
        self.assertEqual(messages[-1]["role"], "user")

    def test_zero_tool_response_replays_actual_text_and_corrective_instruction(self):
        message = {"role": "assistant", "content": "I will inspect the metadata."}
        model = self.fake_model(message)
        req, state = validate_request(request()), initial_state("M01")
        with self.assertRaises(ModelProtocolError) as failure:
            model.choose(req, state, [])
        self.assertEqual(failure.exception.diagnostics["tool_calls_count"], 0)
        message["tool_calls"] = [{"id": "next", "type": "function", "function": {
            "name": "read_material", "arguments": '{"rationale":"read"}'}}]
        model.choose(req, state, [{"recoverable": True, "model_error": "MODEL_EXPECTED_ONE_TOOL_CALL"}])
        messages = self.opener.requests[-1]["messages"]
        self.assertEqual(messages[-2]["content"], "I will inspect the metadata.")
        self.assertFalse(any(m["role"] == "tool" for m in messages))

    def test_long_rationale_is_rejected_without_execution_then_can_be_corrected(self):
        message = {"role": "assistant", "content": None, "tool_calls": [{"id": "long", "type": "function", "function": {
            "name": "read_material", "arguments": json.dumps({"rationale": "x" * 501})}}]}
        model = self.fake_model(message)
        req, state = validate_request(request()), initial_state("M01")
        with self.assertRaisesRegex(ModelProtocolError, "MODEL_INVALID_RATIONALE"):
            model.choose(req, state, [])
        message["tool_calls"][0]["function"]["arguments"] = '{"rationale":"read metadata"}'
        action = model.choose(req, state, [{"recoverable": True, "model_error": "MODEL_INVALID_RATIONALE"}])
        self.assertEqual(action.tool, "read_material")
        replies = [m for m in self.opener.requests[-1]["messages"] if m["role"] == "tool"]
        self.assertFalse(json.loads(replies[0]["content"])["executed"])

    def test_invalid_json_arguments_rejected(self):
        model = self.fake_model({"role": "assistant", "tool_calls": [{"id": "invalid-json", "function": {"name": "read_material", "arguments": "INVALID"}}]})
        with self.assertRaisesRegex(ModelError, "MODEL_INVALID_RESPONSE"):
            model.choose(validate_request(request()), initial_state("M01"), [])

    def test_http_error_body_not_exposed(self):
        model = self.fake_model({})
        self.opener.open = lambda *args, **kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError("https://example.invalid", 401, "SECRET-IN-BODY", {}, None))
        with self.assertRaisesRegex(ModelError, "^MODEL_HTTP_401$"):
            model.choose(validate_request(request()), initial_state("M01"), [])

    def test_missing_provider_call_id_or_null_message_is_safe_error(self):
        for message in (None, {"role": "assistant", "tool_calls": [{"function": {
                "name": "read_material", "arguments": '{"rationale":"read"}'}}]}):
            with self.subTest(message=message):
                model = self.fake_model(message)
                with self.assertRaisesRegex(ModelError, "MODEL_INVALID_RESPONSE"):
                    model.choose(validate_request(request()), initial_state("M01"), [])

    def test_missing_key_and_unsafe_urls_rejected(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                ChatModel()
        for url in ("http://example.com", "https://user:secret@example.com", "https://example.com?key=secret"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                ChatModel(url, "model", "fake")


class CliTests(unittest.TestCase):
    def test_exit_codes_and_json_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            for name, req, extra, expected in (
                ("normal", request(), [], 0),
                ("blocked", request("M04"), [], 2),
                ("limit", request(), ["--max-steps", "1"], 3),
                ("failure", request(), ["--fault", "save_draft"], 2),
                ("invalid", request(hard_time="bad"), [], 4),
            ):
                with self.subTest(name=name):
                    folder = Path(temp) / name
                    folder.mkdir()
                    (folder / "input.json").write_text(json.dumps(req), encoding="utf-8")
                    process = subprocess.run([sys.executable, str(ROOT / "scripts/run.py"),
                        "--input", str(folder / "input.json"), "--data", str(ROOT / "data/fixtures.json"),
                        "--db", str(folder / "db.sqlite"), "--output", str(folder / "result.json"), *extra],
                        capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
                    self.assertEqual(process.returncode, expected, process.stderr)
                    if expected != 4:
                        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
                        self.assertEqual(result["mode"], "offline_mock")
                    else:
                        self.assertIn("hard_time", process.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
