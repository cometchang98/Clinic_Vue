"""
/api/consultation/*  虛擬會診室 (BigQuery 大數據 + AI 分析 + 推播)
"""
import sqlite3, os
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from core.config import CO01M_DB, DIGITAL_DB
from services.iheal_service import send_push, log_push

router = APIRouter(prefix="/api/consultation", tags=["虛擬會診室"])

BQ_PROJECT = "goplace-488704"
CREDENTIALS = "/Users/cometmacmini/.openclaw/secrets/medibot_key.json"


def _bq_client():
    from google.cloud import bigquery
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(CREDENTIALS)
    return bigquery.Client(project=BQ_PROJECT, credentials=creds)


def _pid_filter(pid: str) -> str:
    p = pid.zfill(7)
    return f"LPAD(TRIM(REPLACE(CAST(Patient_ID AS STRING), '.0', '')), 7, '0') = '{p}'"


@router.get("/patient")
def get_patient(pid: str = Query(...)):
    """查詢病患基本資料 (CO01M.db)"""
    pid = pid.strip().zfill(7)
    if not os.path.exists(CO01M_DB):
        raise HTTPException(503, "CO01M.db 不可用")
    conn = sqlite3.connect(CO01M_DB)
    row = conn.execute(
        "SELECT TRIM(KCSTMR), TRIM(MNAME), TRIM(MPERSONID), TRIM(MTELE) FROM CO01M WHERE TRIM(KCSTMR)=?",
        (pid,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "找不到此病患")
    return {"pid": row[0], "name": row[1], "midno": row[2], "phone": row[3]}


@router.get("/labs")
def get_labs(pid: str = Query(...)):
    filt = _pid_filter(pid)
    sql = f"""SELECT Lab_Date, Lab_Name, Lab_Value
              FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
              WHERE {filt} AND Lab_Date >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 YEAR)
              ORDER BY Lab_Date ASC"""
    rows = _bq_client().query(sql).result()
    return {"labs": [dict(r) for r in rows]}


@router.get("/meds")
def get_meds(pid: str = Query(...)):
    filt = _pid_filter(pid)
    sql = f"""SELECT Order_Date, Drug_Name, ATC_Code, Days
              FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_prescriptions_with_atc`
              WHERE {filt} AND Order_Date >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 YEAR)
              ORDER BY Order_Date ASC"""
    rows = _bq_client().query(sql).result()
    return {"meds": [dict(r) for r in rows]}


@router.get("/vitals")
def get_vitals(pid: str = Query(...)):
    filt = _pid_filter(pid)
    sql = f"""SELECT Record_Date, Height, Weight, BMI, SBP, DBP, Blood_Pressure, Temperature
              FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_patient_vitals`
              WHERE {filt} ORDER BY Record_Date DESC"""
    rows = _bq_client().query(sql).result()
    return {"vitals": [dict(r) for r in rows]}


@router.get("/demographics")
def get_demographics(pid: str = Query(...)):
    filt = _pid_filter(pid)
    sql = f"""SELECT Sex, Age FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_patient_demographics`
              WHERE {filt} LIMIT 1"""
    rows = list(_bq_client().query(sql).result())
    if not rows:
        return {"sex": "未知", "age": None}
    r = dict(rows[0])
    return r


class AiBody(BaseModel):
    pid: str
    name: str
    labs_summary: str
    meds_summary: str
    vitals_summary: str

@router.post("/ai-consult")
def ai_consult(body: AiBody):
    from services.gemini_service import ask_gemini
    prompt = f"""你是凱程診所的智慧 AI 主治醫師助理。
病患：{body.name} (病歷號 {body.pid})
---
近兩年檢驗摘要：
{body.labs_summary}
---
近兩年用藥紀錄：
{body.meds_summary}
---
近期生命徵象：
{body.vitals_summary}
---
請以繁體中文，提供：
1. 🔍 臨床重點摘要（3~5個觀察點）
2. ⚠️ 警示事項（若有異常值請明確標出）
3. 💡 下次就診建議（包含追蹤項目）
字數控制在 300 字以內，請用 Markdown 格式。"""
    return {"analysis": ask_gemini(prompt)}


class PushBody(BaseModel):
    pid: str
    midno: str
    name: str
    content: str
    m_type: str = "fcm"
    campaign: str = "虛擬會診室推播"

@router.post("/push")
def push(body: PushBody):
    target = body.midno or body.pid
    r = send_push(body.m_type, target, body.content)
    log_push(body.pid, body.campaign, body.m_type, body.content)
    return r
