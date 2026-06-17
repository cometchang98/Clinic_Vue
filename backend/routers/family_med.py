"""
/api/family-med/*  所有路由
"""
from fastapi import APIRouter, Query, Body, HTTPException
from typing import Optional
from pydantic import BaseModel

from services.family_med_service import (
    get_members, get_diary, save_diary,
    get_bonus_history, generate_draft,
    send_push, batch_analyze, get_alerts,
    check_and_trigger_sync,
)

router = APIRouter(prefix="/api/family-med", tags=["家醫個管"])


# ──────────────────────────────────────────
# 會員名冊
# ──────────────────────────────────────────
@router.get("/sync-status")
def api_sync_status():
    """回傳名單最後更新時間與是否正在同步"""
    return check_and_trigger_sync()


@router.get("/members")
def api_get_members(
    search: str = Query("", description="關鍵字（姓名或身分證）"),
    tags: list[str] = Query([], description="計畫類別過濾"),
):
    sync = check_and_trigger_sync()
    members = get_members(search=search, tags=tags or None)
    return {"members": members, "sync": sync}


# ──────────────────────────────────────────
# 病歷日誌
# ──────────────────────────────────────────
@router.get("/diary/{pid}")
def api_get_diary(pid: str):
    return get_diary(pid)


class DiaryBody(BaseModel):
    content: str

@router.put("/diary/{pid}")
def api_save_diary(pid: str, body: DiaryBody):
    return save_diary(pid, body.content)


# ──────────────────────────────────────────
# AI 推播草稿
# ──────────────────────────────────────────
class DraftBody(BaseModel):
    HbA1c:    Optional[float] = None
    LDL:      Optional[float] = None
    UACR:     Optional[float] = None
    HbA1c趨勢: Optional[str]  = None
    LDL趨勢:   Optional[str]  = None
    UACR趨勢:  Optional[str]  = None
    姓名:      str = "病患"
    計畫類別:   list[str] = []
    品質燈號:   Optional[str] = None
    預估獎金:   Optional[int] = None

@router.post("/draft/{pid}")
def api_generate_draft(pid: str, body: DraftBody):
    return generate_draft(pid, body.model_dump())


# ──────────────────────────────────────────
# 雙軌推播
# ──────────────────────────────────────────
class PushBody(BaseModel):
    message:  str
    campaign: str = "家醫計畫日常關懷"

@router.post("/push/{pid}")
def api_send_push(pid: str, body: PushBody):
    result = send_push(pid, body.message, body.campaign)
    return result


# ──────────────────────────────────────────
# 批次 AI 分析
# ──────────────────────────────────────────
class BatchBody(BaseModel):
    pids: list[str]

@router.post("/batch-analyze")
def api_batch_analyze(body: BatchBody):
    return batch_analyze(body.pids)


# ──────────────────────────────────────────
# 獎金歷史
# ──────────────────────────────────────────
@router.get("/bonus-history")
def api_bonus_history():
    return get_bonus_history()


# ──────────────────────────────────────────
# 品質警報
# ──────────────────────────────────────────
@router.get("/alerts")
def api_alerts():
    return get_alerts()
