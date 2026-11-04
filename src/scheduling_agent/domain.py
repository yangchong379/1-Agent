"""Validate user authority before sending any data to the model."""
from datetime import datetime, timedelta
import hashlib
import json


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def slot_time(value):
    if not isinstance(value, str):
        raise ValueError("slot must be an ISO 8601 string")
    dt = datetime.fromisoformat(value)
    if dt.utcoffset() != timedelta(hours=8) or dt.second or dt.microsecond:
        raise ValueError("slot must contain explicit +08:00 offset with minute precision")
    return dt


def validate_request(raw):
    if not isinstance(raw, dict):
        raise ValueError("request must be an object")
    required = {"request_id", "material_ids", "channel", "preferred_slot", "hard_time"}
    if set(raw) - required - {"approved_slots"} or not required <= set(raw):
        raise ValueError("unknown or missing request fields")
    req = dict(raw)
    for field in ("request_id", "channel"):
        if not isinstance(req[field], str) or not 1 <= len(req[field]) <= 100:
            raise ValueError(f"invalid {field}")
    ids = req["material_ids"]
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 20
            or any(not isinstance(x, str) or not 1 <= len(x) <= 64 for x in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("material_ids must contain 1..20 unique strings")
    req["preferred_slot"] = slot_time(req["preferred_slot"]).isoformat(timespec="minutes")
    if type(req["hard_time"]) is not bool:
        raise ValueError("hard_time must be boolean")
    approvals = req.setdefault("approved_slots", {})
    if not isinstance(approvals, dict) or set(approvals) - set(ids):
        raise ValueError("approved_slots keys must be requested material IDs")
    req["approved_slots"] = {key: slot_time(value).isoformat(timespec="minutes")
                             for key, value in approvals.items()}
    return req


def review(material, rules):
    missing = [key for key in rules["required_fields"]
               if key not in material or material[key] is None or material[key] == ""]
    for key in ("title", "description"):
        if not isinstance(material.get(key), str):
            missing.append(key)
    if type(material.get("contains_private_data")) is not bool:
        missing.append("contains_private_data")
    risks = []
    if material.get("copyright") == "denied":
        risks.append({"code": "COPYRIGHT_DENIED", "reason": "素材明确无使用授权"})
    text = " ".join(str(material.get(k, "")) for k in ("title", "description"))
    for phrase in rules["blocked_phrases"]:
        if phrase in text:
            risks.append({"code": "PROHIBITED_CLAIM", "reason": f"包含禁用表述：{phrase}"})
    if material.get("contains_private_data") is True:
        risks.append({"code": "PRIVACY_RISK", "reason": "含未脱敏个人信息"})
    if material.get("copyright") not in (None, "", "licensed", "denied"):
        missing.append("valid_copyright_evidence")
    return {"status": "blocked" if risks else "needs_info" if missing else "approved",
            "missing_fields": sorted(set(missing)), "risks": risks}
