"""
/api/plan888/*  888 戰略指揮中心路由
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from services.plan888_service import (
    get_triage_list, analyze_patient_888, batch_analyze_888,
    check_and_trigger_triage_sync,
)
from services.family_med_service import send_push, get_diary, save_diary

router = APIRouter(prefix="/api/plan888", tags=["888戰略指揮"])


@router.get("/sync-status")
def api_sync_status():
    return check_and_trigger_triage_sync()


@router.get("/triage")
def api_triage(mode: str = Query("DM", description="DM | CKD | DKD | DKD2to3")):
    sync = check_and_trigger_triage_sync()
    patients = get_triage_list(mode)
    return {"patients": patients, "sync": sync}


class AnalyzeBody(BaseModel):
    pt: dict   # 完整病患資料 dict（從 triage 列表傳入）

@router.post("/analyze/{pid}")
def api_analyze(pid: str, body: AnalyzeBody):
    return analyze_patient_888(pid, body.pt)


class BatchBody(BaseModel):
    patients: list[dict]   # [{病歷號, 姓名, HbA1c, ...}]

@router.post("/batch-analyze")
def api_batch_analyze(body: BatchBody):
    return batch_analyze_888(body.patients)


class PushBody(BaseModel):
    message:  str
    campaign: str = "888專案 H2S 群發"

@router.post("/push/{pid}")
def api_push(pid: str, body: PushBody):
    return send_push(pid, body.message, body.campaign)


@router.get("/diary/{pid}")
def api_diary(pid: str):
    return get_diary(pid)


class DiaryBody(BaseModel):
    content: str

@router.put("/diary/{pid}")
def api_save_diary(pid: str, body: DiaryBody):
    return save_diary(pid, body.content)
