"""
/api/vaccine/*  疫苗提醒 — 帶狀皰疹 (Shingrix) 催種名單

資料來源：clinic_research/vaccine_recall_engine.py 產出的 vaccine_report.json
（由 daily_pipeline 排程每日更新；本 router 只負責讀檔吐 API，不做運算）

端點：
  GET /api/vaccine/report      整份報告（含分組明細 + summary + rules）
  GET /api/vaccine/due         扁平 per-patient 提醒列表（前端清單用）
  GET /api/vaccine/{pid}       單一病人是否需提醒（看診工作區用）
"""
import os
import json
from fastapi import APIRouter

from core.config import VACCINE_REPORT

router = APIRouter(prefix="/api/vaccine", tags=["疫苗提醒"])


def _load():
    if not os.path.exists(VACCINE_REPORT):
        return None
    try:
        with open(VACCINE_REPORT, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


@router.get("/report")
def get_report():
    data = _load()
    if data is None:
        return {
            "available": False,
            "message": "尚未產生疫苗報告，請確認 vaccine_recall_engine.py 排程已執行。",
            "summary": {}, "patients": [],
            "dose2_normal": [], "dose2_urgent": [], "dose1_remind": [],
        }
    data["available"] = True
    return data


@router.get("/due")
def get_due():
    """扁平提醒列表，前端清單直接 render。"""
    data = _load()
    if data is None:
        return {"available": False, "generated_at": None, "patients": []}
    return {
        "available": True,
        "generated_at": data.get("generated_at"),
        "summary": data.get("summary", {}),
        "patients": data.get("patients", []),
    }


@router.get("/{pid}")
def get_for_patient(pid: str):
    """看診工作區：查單一病人是否在疫苗提醒名單上。"""
    p = str(pid).strip().zfill(7)
    data = _load()
    if data is None:
        return {"pid": p, "need_vaccine": False, "items": []}
    items = [x for x in data.get("patients", [])
             if str(x.get("病歷號", "")).strip().zfill(7) == p]
    return {
        "pid": p,
        "need_vaccine": len(items) > 0,
        "items": items,
    }
