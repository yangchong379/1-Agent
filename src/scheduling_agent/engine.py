"""Model-driven loop plus deterministic tool and reporting boundaries."""
from dataclasses import asdict
from datetime import datetime, timezone
import copy
import sqlite3
from .domain import digest, review, validate_request
from .models import ModelError, ModelProtocolError, TOOLS


def initial_state(material_id):
    return {"material_id": material_id, "material": None, "review": None,
            "supplemented": False, "query": None, "saved": None, "saved_review": None,
            "existing_draft": None, "last_error": None, "save_attempted": False}


class Agent:
    def __init__(self, model, store, data, max_steps=40, fault=None):
        if not 1 <= max_steps <= 100:
            raise ValueError("max_steps must be 1..100 (whole request, including finish)")
        self.model, self.store, self.data = model, store, data
        self.max_steps, self.fault = max_steps, fault

    def execute(self, req, state, action):
        name, args = action.tool, action.arguments
        if name not in TOOLS or not isinstance(args, dict):
            return {"ok": False, "code": "UNKNOWN_TOOL"}
        expected = {"slot"} if name == "save_draft" else set()
        if set(args) != expected or (expected and not isinstance(args["slot"], str)):
            return {"ok": False, "code": "INVALID_TOOL_ARGUMENTS"}
        if self.fault == name and name not in {"save_draft", "query_slots"}:
            return {"ok": False, "code": "TOOL_UNAVAILABLE", "tool": name}
        mid = state["material_id"]
        if name == "read_material":
            material = self.data["materials"].get(mid)
            if material is None:
                state["material"] = {"id": mid}
                state["review"] = {"status": "needs_info", "missing_fields": ["material_not_found"], "risks": []}
                return {"ok": False, "code": "MATERIAL_NOT_FOUND", "material_id": mid}
            state["material"] = copy.deepcopy(material)
            state["existing_draft"] = self.store.draft(mid, req["channel"])
            state["review"] = None
            return {"ok": True, "material": state["material"], "existing_draft": state["existing_draft"],
                    "review_required": True, "note": "Reading metadata invalidates previous review; call check_rules before saving."}
        if name == "supplement_metadata":
            if state["material"] is None:
                return {"ok": False, "code": "READ_FIRST"}
            if state["supplemented"]:
                return {"ok": False, "code": "SUPPLEMENT_ALREADY_ATTEMPTED"}
            supplement = self.data.get("supplements", {}).get(mid, {})
            # Supplement fills absent fields only; it cannot overwrite known risks.
            found = {k: v for k, v in supplement.items()
                     if state["material"].get(k) in (None, "")}
            state["material"].update(found)
            state["supplemented"] = True
            state["review"] = None
            return {"ok": True, "found": found, "source": "synthetic_supplements", "review_required": True,
                    "note": "Run check_rules again after this lookup, even when found is empty."}
        if name == "check_rules":
            if state["material"] is None:
                return {"ok": False, "code": "READ_FIRST"}
            state["review"] = review(state["material"], self.data["rules"])
            return {"ok": True, **state["review"], "rule_version": self.data["rules"]["version"]}
        if name == "query_slots":
            try:
                if self.fault == name:
                    result = {"ok": False, "code": "TOOL_UNAVAILABLE", "tool": name}
                else:
                    result = self.store.query(req, mid)
            except sqlite3.Error:
                result = {"ok": False, "code": "TOOL_UNAVAILABLE", "tool": name}
            state["query"] = result if result["ok"] else None
            state["last_error"] = None if result["ok"] else result["code"]
            if not result["ok"]:
                return {**result, "terminal": True, "reason": "Slot query failed. Retry the request when the query service is available."}
            return result
        if name == "save_draft":
            # Recompute review; never trust the model's interpretation or cached status alone.
            if state["review"] is None or state["material"] is None:
                return {"ok": False, "code": "REVIEW_REQUIRED",
                        "reason": "No current review. Reading or supplementing metadata invalidates previous review; call check_rules before saving. This is not an approval error."}
            current = review(state["material"], self.data["rules"])
            if current["status"] != "approved":
                return {"ok": False, "code": "REVIEW_NOT_APPROVED", "review": current}
            if not state["query"] or args["slot"] not in state["query"]["available"]:
                return {"ok": False, "code": "AVAILABLE_SLOT_OBSERVATION_REQUIRED"}
            state["save_attempted"] = True
            result = self.store.save(req, mid, args["slot"], fail=self.fault == "save_draft")
            if result["ok"]:
                state["saved"] = result
                state["saved_review"] = copy.deepcopy(current)
                state["last_error"] = None
            else:
                state["last_error"] = result["code"]
            return result
        if name == "finish":
            status = self.result_status(state)
            if status == "incomplete":
                return {"ok": False, "code": "FINISH_REQUIRES_EVIDENCE",
                        "review_status": state["review"]["status"] if state["review"] else "unchecked",
                        "draft_saved": False,
                        "reason": "No terminal evidence yet. Obtain a current review, query slots and save a draft when possible. A free alternative draft may be saved as pending_user before approval; it does not change the hard requirement or publish."}
            return {"ok": True, "code": "FINISHED", "status": status}

    @staticmethod
    def result_status(state):
        if state["saved"]:
            return "awaiting_confirmation" if state["saved"]["confirmation"] == "pending_user" else "draft_ready"
        audit = state["review"]
        if audit and audit["status"] in {"blocked", "needs_info"}:
            return audit["status"]
        if state["last_error"] == "SAVE_FAILED":
            return "save_failed"
        if state["last_error"] in {"EXISTING_DRAFT_REQUIREMENT_CONFLICT", "DRAFT_CHANGE_NEEDS_EXPLICIT_APPROVAL"}:
            return "needs_confirmation"
        if state["query"] and not state["query"]["available"]:
            return "no_available_slot"
        return "incomplete"

    def run(self, raw):
        req = validate_request(raw)
        self.store.bind_request(req)
        events, items = [], []
        calls = 0
        started = datetime.now(timezone.utc).isoformat()
        for mid in req["material_ids"]:
            state, history = initial_state(mid), []
            stop, model_error = "step_limit", None
            while calls < self.max_steps:
                calls += 1
                try:
                    action = self.model.choose(req, copy.deepcopy(state), copy.deepcopy(history))
                except ModelProtocolError as exc:
                    model_error = str(exc)
                    event = {"step": calls, "material_id": mid, "model_error": model_error,
                             "recoverable": True, "diagnostics": exc.diagnostics}
                    history.append(event)
                    events.append(event)
                    continue
                except ModelError as exc:
                    model_error, stop = str(exc), "model_error"
                    events.append({"step": calls, "material_id": mid, "model_error": model_error})
                    break
                model_error = None
                observation = self.execute(req, state, action)
                event = {"step": calls, "material_id": mid, "action": asdict(action),
                         "observation": copy.deepcopy(observation)}
                history.append(event)
                events.append(event)
                if action.tool == "query_slots" and observation.get("terminal"):
                    stop = "query_failed"
                    break
                if action.tool == "finish" and observation.get("ok"):
                    stop = "finished"
                    break
            saved = state["saved"]
            audit = (state["saved_review"] if saved else state["review"]) or {
                "status": "unchecked", "missing_fields": [], "risks": []}
            pending = [f"补充 {field}" for field in audit["missing_fields"]]
            if saved and saved["confirmation"] == "pending_user":
                pending.append(f"请确认是否将 {req['preferred_slot']} 调整为 {saved['slot']}；原硬性要求保持不变")
            if self.result_status(state) == "needs_confirmation":
                pending.append("已有草稿与本次要求冲突，需要用户明确处理")
            if stop == "query_failed" and not saved:
                status = "query_failed"
            elif stop in {"finished", "query_failed"}:
                status = self.result_status(state)
            else:
                status = "incomplete_" + stop
            items.append({"material_id": mid,
                "status": status,
                "review_status": audit["status"], "review_basis": "at_successful_save" if saved else "latest_rule_check",
                "risk_reasons": audit["risks"],
                "missing_fields": audit["missing_fields"], "requested_slot": req["preferred_slot"],
                "hard_time": req["hard_time"], "suggested_slot": saved["slot"] if saved else None,
                "pending_confirmation": pending,
                "draft_save_status": "saved" if saved else "failed" if state["save_attempted"] else "not_attempted",
                "draft_id": saved["draft_id"] if saved else None,
                "save_receipt": saved, "stop_reason": stop,
                "error": model_error or state["last_error"] or
                         (history[-1].get("observation", {}).get("code") if history and not history[-1].get("observation", {}).get("ok") else None),
                "published": False})
        for index, event in enumerate(events):
            nxt = events[index + 1] if index + 1 < len(events) else None
            event["next_action"] = (nxt.get("action", {}).get("tool", "model_error")
                                    if nxt and nxt["material_id"] == event["material_id"] else "stop")
        return {"schema_version": "1.0", "mode": self.model.mode, "model": self.model.name,
                "request": req, "started_at_utc": started, "dataset_sha256": digest(self.data),
                "max_steps": self.max_steps, "model_calls": calls,
                "tool_calls": sum("action" in e for e in events),
                "protocol_rejections": sum(e.get("recoverable", False) for e in events),
                "execution_complete": all(i["stop_reason"] in {"finished", "query_failed"} for i in items),
                "all_drafts_saved": all(i["draft_save_status"] == "saved" for i in items),
                "items": items, "trace": events,
                "boundary": "MOCK validates control flow only; no real model evidence" if self.model.mode == "offline_mock"
                else "Live model tool decisions; synthetic business data; draft only"}
