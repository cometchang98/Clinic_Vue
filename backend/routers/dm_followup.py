"""
/api/dm-care/m5/*  M5 追蹤 SOP — 醫師↔衛教師衛教協作板（讀寫）

- 衛教 checklist：醫師指派 / 衛教師自選，雙人筆記，AI 補筆記
- 下次回診約定
- 檢查完成度：重用 yearly_checklists（眼底/UACR/LDL/疫苗）
儲存：本機 SQLite（DIGITAL_DB）。第二階段再決定是否同步 Google Sheets 給衛教師。
"""
import sqlite3
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from core.config import DIGITAL_DB, GEMINI_API_KEY

router = APIRouter(prefix="/api/dm-care/m5", tags=["M5 追蹤SOP"])

# 常用衛教主題（前端快速新增用）
SUGGESTED_TOPICS = ["低血糖", "飲食控制", "用藥順從性", "足部護理", "血糖自我監測 SMBG",
                    "運動建議", "戒菸", "腎臟保養", "胰島素注射技巧", "體重管理"]


def _conn():
    c = sqlite3.connect(DIGITAL_DB)
    c.row_factory = sqlite3.Row
    return c


def _init():
    c = _conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS dm_followup_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pid TEXT NOT NULL,
            topic TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            requested_by TEXT DEFAULT 'educator',
            doctor_note TEXT DEFAULT '',
            educator_note TEXT DEFAULT '',
            created_at TEXT,
            completed_at TEXT,
            completed_by TEXT DEFAULT ''
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_followup_pid ON dm_followup_items(pid)")
    c.execute("""
        CREATE TABLE IF NOT EXISTS dm_next_visit (
            pid TEXT PRIMARY KEY,
            visit_date TEXT,
            note TEXT DEFAULT '',
            set_by TEXT DEFAULT '',
            set_at TEXT
        )
    """)
    c.commit()
    c.close()


_init()


# ── 讀取整張卡 ────────────────────────────────────────────
@router.get("/{pid}")
def get_m5(pid: str):
    p = str(pid).strip().zfill(7)
    c = _conn()

    items = [dict(r) for r in c.execute(
        "SELECT * FROM dm_followup_items WHERE pid=? ORDER BY "
        "CASE status WHEN 'pending' THEN 0 ELSE 1 END, "
        "COALESCE(completed_at, created_at) DESC", (p,)
    ).fetchall()]

    nv = c.execute("SELECT * FROM dm_next_visit WHERE pid=?", (p,)).fetchone()
    next_visit = dict(nv) if nv else None

    # 檢查完成度（重用 yearly_checklists，當年度）
    roc_year = str(datetime.now().year - 1911)
    yc = c.execute(
        "SELECT * FROM yearly_checklists WHERE pid=? AND roc_year=?", (p, roc_year)
    ).fetchone()
    c.close()

    exams = []
    if yc:
        y = dict(yc)
        exams = [
            {"key": "eye",  "name": "眼底檢查", "done": bool(y.get("eye_exam_done")),  "date": y.get("eye_exam_date") or ""},
            {"key": "uacr", "name": "UACR",    "done": bool(y.get("uacr_done")),      "date": y.get("uacr_date") or ""},
            {"key": "ldl",  "name": "LDL",     "done": bool(y.get("ldl_done")),       "date": y.get("ldl_date") or ""},
            {"key": "flu",  "name": "流感疫苗", "done": bool(y.get("flu_vaccine_done")), "date": y.get("flu_vaccine_date") or ""},
        ]

    pending = [i for i in items if i["status"] == "pending"]
    history = [i for i in items if i["status"] == "done"]

    return {
        "pid":         p,
        "pending":     pending,
        "history":     history,
        "next_visit":  next_visit,
        "exams":       exams,
        "exam_year":   roc_year,
        "suggested_topics": SUGGESTED_TOPICS,
    }


# ── 新增衛教項目 ──────────────────────────────────────────
class AddItem(BaseModel):
    topic: str
    requested_by: str = "educator"   # doctor | educator
    doctor_note: str = ""
    educator_note: str = ""

@router.post("/{pid}/item")
def add_item(pid: str, body: AddItem):
    p = str(pid).strip().zfill(7)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    c = _conn()
    cur = c.execute(
        "INSERT INTO dm_followup_items(pid,topic,status,requested_by,doctor_note,educator_note,created_at) "
        "VALUES(?,?,'pending',?,?,?,?)",
        (p, body.topic.strip(), body.requested_by, body.doctor_note, body.educator_note, now)
    )
    c.commit()
    new_id = cur.lastrowid
    c.close()
    return {"ok": True, "id": new_id}


# ── 更新項目（完成 / 改筆記）────────────────────────────────
class UpdateItem(BaseModel):
    status: Optional[str] = None          # pending | done
    doctor_note: Optional[str] = None
    educator_note: Optional[str] = None
    completed_by: Optional[str] = None    # doctor | educator

@router.patch("/item/{item_id}")
def update_item(item_id: int, body: UpdateItem):
    c = _conn()
    row = c.execute("SELECT * FROM dm_followup_items WHERE id=?", (item_id,)).fetchone()
    if not row:
        c.close()
        return {"ok": False, "error": "找不到項目"}
    sets, vals = [], []
    if body.doctor_note is not None:
        sets.append("doctor_note=?"); vals.append(body.doctor_note)
    if body.educator_note is not None:
        sets.append("educator_note=?"); vals.append(body.educator_note)
    if body.status is not None:
        sets.append("status=?"); vals.append(body.status)
        if body.status == "done":
            sets.append("completed_at=?"); vals.append(datetime.now().strftime("%Y-%m-%d %H:%M"))
            sets.append("completed_by=?"); vals.append(body.completed_by or "")
        else:
            sets.append("completed_at=?"); vals.append(None)
    if sets:
        vals.append(item_id)
        c.execute(f"UPDATE dm_followup_items SET {','.join(sets)} WHERE id=?", vals)
        c.commit()
    c.close()
    return {"ok": True}


@router.delete("/item/{item_id}")
def delete_item(item_id: int):
    c = _conn()
    c.execute("DELETE FROM dm_followup_items WHERE id=?", (item_id,))
    c.commit()
    c.close()
    return {"ok": True}


# ── 複習：把歷史項目重新開一筆 pending ──────────────────────
@router.post("/item/{item_id}/review")
def review_item(item_id: int):
    c = _conn()
    row = c.execute("SELECT * FROM dm_followup_items WHERE id=?", (item_id,)).fetchone()
    if not row:
        c.close(); return {"ok": False, "error": "找不到項目"}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur = c.execute(
        "INSERT INTO dm_followup_items(pid,topic,status,requested_by,doctor_note,created_at) "
        "VALUES(?,?,'pending','educator',?,?)",
        (row["pid"], row["topic"], f"（複習自 {row['completed_at'] or '前次'}）", now)
    )
    c.commit(); new_id = cur.lastrowid; c.close()
    return {"ok": True, "id": new_id}


# ── 下次回診 ──────────────────────────────────────────────
class NextVisit(BaseModel):
    visit_date: str
    note: str = ""
    set_by: str = "educator"

@router.put("/{pid}/next-visit")
def set_next_visit(pid: str, body: NextVisit):
    p = str(pid).strip().zfill(7)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    c = _conn()
    c.execute(
        "INSERT INTO dm_next_visit(pid,visit_date,note,set_by,set_at) VALUES(?,?,?,?,?) "
        "ON CONFLICT(pid) DO UPDATE SET visit_date=excluded.visit_date, note=excluded.note, "
        "set_by=excluded.set_by, set_at=excluded.set_at",
        (p, body.visit_date, body.note, body.set_by, now)
    )
    c.commit(); c.close()
    return {"ok": True}


# ── AI 代寫衛教筆記（Gemini）──────────────────────────────
class AiNote(BaseModel):
    topic: str
    patient_context: str = ""   # 前端可帶病患數值摘要（HbA1c 等）

@router.post("/ai-note")
def ai_note(body: AiNote):
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""你是糖尿病衛教師。請針對衛教主題「{body.topic}」，
為這位病患寫一段「給衛教師參考的重點提示」，2-3 句、條列亦可，口語務實，
聚焦今天衛教時該強調什麼、要提醒病患的具體行動。
{('病患現況：' + body.patient_context) if body.patient_context else ''}
請直接給內容，不要前言客套。"""
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        return {"ok": True, "note": (resp.text or "").strip()}
    except Exception as e:
        return {"ok": False, "error": str(e), "note": ""}
