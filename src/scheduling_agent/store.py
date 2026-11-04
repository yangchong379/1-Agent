"""SQLite transactions enforce idempotency and interval conflicts at write time."""
import json
import sqlite3
from datetime import timedelta
from .domain import canonical, digest, slot_time


class Store:
    def __init__(self, path, data):
        self.db = sqlite3.connect(str(path), timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS schedules(
          id TEXT PRIMARY KEY, channel TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS drafts(
          id TEXT PRIMARY KEY, material_id TEXT NOT NULL, channel TEXT NOT NULL,
          requirement TEXT NOT NULL, slot TEXT NOT NULL, end TEXT NOT NULL,
          confirmation TEXT NOT NULL, UNIQUE(material_id, channel));
        """)
        self.data = data
        self.db.execute("BEGIN IMMEDIATE")
        try:
            version = digest(data)
            old = self.db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()
            if old and old[0] != version:
                raise ValueError("dataset changed: use a fresh database; never silently reset state")
            if not old:
                for row in data["existing_schedule"]:
                    self.db.execute("INSERT INTO schedules VALUES(?,?,?,?)",
                                    (row["id"], row["channel"], row["start"], row["end"]))
                self.db.execute("INSERT INTO metadata VALUES('dataset',?)", (version,))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            self.close()
            raise

    def close(self):
        self.db.close()

    def bind_request(self, req):
        fingerprint = digest(req)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT fingerprint FROM requests WHERE id=?",
                                  (req["request_id"],)).fetchone()
            if row and row[0] != fingerprint:
                raise ValueError("REQUEST_ID_REUSED: changed payload requires a new request_id")
            self.db.execute("INSERT OR IGNORE INTO requests VALUES(?,?)",
                            (req["request_id"], fingerprint))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def draft(self, material_id, channel):
        row = self.db.execute("SELECT * FROM drafts WHERE material_id=? AND channel=?",
                              (material_id, channel)).fetchone()
        return dict(row) if row else None

    def conflicts(self, channel, slot, material_id):
        start = slot_time(slot)
        end = start + timedelta(minutes=self.data["rules"]["duration_minutes"])
        rows = [dict(r) for r in self.db.execute(
            "SELECT id, start, end FROM schedules WHERE channel=?", (channel,))]
        rows += [dict(r) for r in self.db.execute(
            "SELECT id, slot AS start, end FROM drafts WHERE channel=? AND material_id<>?",
            (channel, material_id))]
        return [r["id"] for r in rows
                if start < slot_time(r["end"]) and slot_time(r["start"]) < end]

    def query(self, req, material_id):
        slots = [s for s in self.data["slots"]
                 if slot_time(s).date() == slot_time(req["preferred_slot"]).date()]
        available, occupied = [], []
        for slot in slots:
            collisions = self.conflicts(req["channel"], slot, material_id)
            (occupied if collisions else available).append(
                {"slot": slot, "conflicts": collisions} if collisions else slot)
        return {"ok": True, "available": available, "occupied": occupied,
                "preferred_slot": req["preferred_slot"],
                "preferred_available": req["preferred_slot"] in available}

    def save(self, req, material_id, slot, fail=False):
        # Confirmation is derived ONLY from validated user input; model has no such parameter.
        if slot not in self.data["slots"]:
            return {"ok": False, "code": "INVALID_SLOT"}
        if slot_time(slot).date() != slot_time(req["preferred_slot"]).date():
            return {"ok": False, "code": "OUTSIDE_REQUEST_DAY"}
        requirement = canonical({k: req[k] for k in ("preferred_slot", "hard_time")})
        approved = req["approved_slots"].get(material_id)
        confirmation = ("confirmed" if slot == req["preferred_slot"] or approved == slot
                        or not req["hard_time"] else "pending_user")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            old = self.draft(material_id, req["channel"])
            if old and old["requirement"] != requirement:
                self.db.execute("ROLLBACK")
                return {"ok": False, "code": "EXISTING_DRAFT_REQUIREMENT_CONFLICT",
                        "draft_id": old["id"]}
            if old and old["slot"] != slot and approved != slot:
                self.db.execute("ROLLBACK")
                return {"ok": False, "code": "DRAFT_CHANGE_NEEDS_EXPLICIT_APPROVAL",
                        "draft_id": old["id"]}
            collisions = self.conflicts(req["channel"], slot, material_id)
            if collisions:
                self.db.execute("ROLLBACK")
                return {"ok": False, "code": "SLOT_CONFLICT", "conflicts": collisions}
            if old and old["slot"] == slot and (old["confirmation"] == confirmation
                                                or old["confirmation"] == "confirmed"):
                self.db.execute("COMMIT")
                return {"ok": True, "code": "DUPLICATE", "draft_id": old["id"],
                        "slot": old["slot"], "confirmation": old["confirmation"]}
            identifier = "draft-" + digest([material_id, req["channel"]])[:16]
            self.db.execute("""INSERT INTO drafts VALUES(?,?,?,?,?,?,?)
              ON CONFLICT(material_id,channel) DO UPDATE SET
              slot=excluded.slot,end=excluded.end,confirmation=excluded.confirmation""",
                            (identifier, material_id, req["channel"], requirement, slot,
                             (slot_time(slot) + timedelta(minutes=self.data["rules"]["duration_minutes"])).isoformat(),
                             confirmation))
            if fail:
                raise sqlite3.OperationalError("injected write failure before commit")
            self.db.execute("COMMIT")
            return {"ok": True, "code": "UPDATED" if old else "CREATED", "draft_id": identifier,
                    "slot": slot, "confirmation": confirmation}
        except sqlite3.Error:
            try:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            return {"ok": False, "code": "SAVE_FAILED", "retryable": True}

    def count(self):
        return self.db.execute("SELECT count(*) FROM drafts").fetchone()[0]
