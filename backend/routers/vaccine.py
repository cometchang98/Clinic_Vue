"""
/api/vaccine/*  疫苗提醒 — 帶狀皰疹 (Shingrix) + 肺炎鏈球菌 (PCV) 催種名單

資料來源：clinic_research/vaccine_recall_engine.py 產出的 vaccine_report.json
（由 daily_pipeline 排程每日更新；本 router 只負責讀檔吐 API，不做運算）

駁回紀錄：vaccine_dismissals.json（同目錄，不入 git）
  action=vaccinated → 永久略過（病人在他院已打）
  action=explained  → 6個月後恢復（本診說明過，半年內不再提醒）

端點：
  GET  /api/vaccine/report         整份報告（含分組明細 + summary + rules）
  GET  /api/vaccine/due            扁平 per-patient 提醒列表
  POST /api/vaccine/dismiss        記錄「已施打」或「已說明」
  GET  /api/vaccine/{pid}          單一病人是否需提醒（看診工作區用）
"""
import os
import json
import threading
from datetime import datetime, date, timedelta
from fastapi import APIRouter
from pydantic import BaseModel

from core.config import VACCINE_REPORT, VACCINE_DISMISSALS

router = APIRouter(prefix="/api/vaccine", tags=["疫苗提醒"])

_dismiss_lock = threading.Lock()


# ── 讀報告 ───────────────────────────────────────────────
def _load():
    if not os.path.exists(VACCINE_REPORT):
        return None
    try:
        with open(VACCINE_REPORT, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ── 讀/寫駁回紀錄 ────────────────────────────────────────
def _load_dismissals() -> dict:
    if not os.path.exists(VACCINE_DISMISSALS):
        return {}
    try:
        with open(VACCINE_DISMISSALS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_dismissals(d: dict):
    os.makedirs(os.path.dirname(VACCINE_DISMISSALS), exist_ok=True)
    with open(VACCINE_DISMISSALS, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def _is_dismissed(dismissals: dict, pid: str, vaccine_type: str) -> bool:
    """回傳 True 表示此 pid + vaccine_type 目前應略過（永久或尚在6個月內）"""
    rec = dismissals.get(pid, {}).get(vaccine_type)
    if not rec:
        return False
    if rec.get("action") == "vaccinated":
        return True   # 永久
    expires = rec.get("expires")
    if expires and date.today().isoformat() < expires:
        return True   # 已說明，6個月內
    return False      # 已過期，恢復提醒


def _vaccine_type(item: dict) -> str:
    """從 item 推算疫苗類型字串（對應 dismissals key）"""
    cat = item.get("類別", "")
    vac = item.get("疫苗", "")
    if "PCV" in cat or vac == "PCV":
        return "PCV"
    return "Shingrix"


# ── 端點 ─────────────────────────────────────────────────

@router.get("/report")
def get_report():
    data = _load()
    if data is None:
        return {
            "available": False,
            "message": "尚未產生疫苗報告，請確認 vaccine_recall_engine.py 排程已執行。",
            "summary": {}, "patients": [],
            "dose2_normal": [], "dose2_urgent": [],
            "dose1_remind": [], "pcv_remind": [],
        }
    data["available"] = True
    return data


@router.get("/due")
def get_due():
    data = _load()
    if data is None:
        return {"available": False, "generated_at": None, "patients": []}
    return {
        "available": True,
        "generated_at": data.get("generated_at"),
        "summary": data.get("summary", {}),
        "patients": data.get("patients", []),
    }


class DismissRequest(BaseModel):
    pid: str
    vaccine: str    # "PCV" 或 "Shingrix"
    action: str     # "vaccinated" 或 "explained"


@router.post("/dismiss")
def dismiss(req: DismissRequest):
    """記錄「已施打（永久）」或「已說明（6個月）」。"""
    pid = str(req.pid).strip().zfill(7)
    vaccine = req.vaccine.strip()
    action  = req.action.strip()

    if action not in ("vaccinated", "explained"):
        return {"ok": False, "error": "action 必須是 vaccinated 或 explained"}

    expires = None
    if action == "explained":
        expires = (date.today() + timedelta(days=180)).isoformat()

    with _dismiss_lock:
        dismissals = _load_dismissals()
        dismissals.setdefault(pid, {})[vaccine] = {
            "action":  action,
            "at":      datetime.now().isoformat(timespec="seconds"),
            "expires": expires,
        }
        _save_dismissals(dismissals)

    return {
        "ok":      True,
        "pid":     pid,
        "vaccine": vaccine,
        "action":  action,
        "expires": expires,
    }


@router.get("/{pid}")
def get_for_patient(pid: str):
    """看診工作區：查單一病人是否在疫苗提醒名單上（已過濾駁回紀錄）。"""
    p = str(pid).strip().zfill(7)
    data = _load()
    if data is None:
        return {"pid": p, "need_vaccine": False, "items": []}

    dismissals = _load_dismissals()
    raw_items = [x for x in data.get("patients", [])
                 if str(x.get("病歷號", "")).strip().zfill(7) == p]

    items = [item for item in raw_items
             if not _is_dismissed(dismissals, p, _vaccine_type(item))]

    return {
        "pid":          p,
        "need_vaccine": len(items) > 0,
        "items":        items,
    }
