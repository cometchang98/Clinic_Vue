"""
/api/nhi-audit/*  健保抽審與 SOAP 筆記
"""
import os, sqlite3
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.gemini_service import ask_gemini

router = APIRouter(prefix="/api/nhi-audit", tags=["健保抽審"])

BQ_PROJECT  = "goplace-488704"
CREDENTIALS = "/Users/cometmacmini/.openclaw/secrets/medibot_key.json"
CO01M_DB    = "/Users/cometmacmini/clinic_research/data_backup/CO01M.db"

TOTFA_XML   = "/Users/cometmacmini/clinic_research/TOTFA.xml"


def _bq_client():
    from google.cloud import bigquery
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(CREDENTIALS)
    return bigquery.Client(project=BQ_PROJECT, credentials=creds)


@router.get("/parse-xml")
def parse_xml(limit: int = Query(200)):
    """解析 TOTFA.xml 回傳抽審名單"""
    if not os.path.exists(TOTFA_XML):
        raise HTTPException(404, "TOTFA.xml 不存在")
    import xml.etree.ElementTree as ET
    tree = ET.parse(TOTFA_XML)
    root = tree.getroot()
    records = []
    for elem in root.iter():
        row = {child.tag: (child.text or "").strip() for child in elem}
        if row:
            records.append(row)
        if len(records) >= limit:
            break
    return {"records": records, "total": len(records)}


@router.get("/patient-labs")
def patient_labs(pid: str = Query(...)):
    p = pid.strip().zfill(7)
    filt = f"LPAD(TRIM(REPLACE(CAST(Patient_ID AS STRING), '.0', '')), 7, '0') = '{p}'"
    sql = f"""SELECT Lab_Date, Lab_Name, Lab_Value
              FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
              WHERE {filt} ORDER BY Lab_Date DESC LIMIT 50"""
    rows = _bq_client().query(sql).result()
    return {"labs": [dict(r) for r in rows]}


@router.get("/patient-prescriptions")
def patient_prescriptions(pid: str = Query(...)):
    p = pid.strip().zfill(7)
    filt = f"LPAD(TRIM(REPLACE(CAST(Patient_ID AS STRING), '.0', '')), 7, '0') = '{p}'"
    sql = f"""SELECT Order_Date, Drug_Name, ATC_Code, Days
              FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_prescriptions_with_atc`
              WHERE {filt} ORDER BY Order_Date DESC LIMIT 100"""
    rows = _bq_client().query(sql).result()
    return {"prescriptions": [dict(r) for r in rows]}


class SoapBody(BaseModel):
    pid: str
    chief_complaint: str
    labs_summary: str
    meds_summary: str
    custom_notes: str = ""

@router.post("/generate-soap")
def generate_soap(body: SoapBody):
    prompt = f"""你是凱程診所的智慧病歷助理。根據以下資訊，以標準 SOAP 格式撰寫健保抽審病歷 (繁體中文)。

主訴：{body.chief_complaint}
檢驗摘要：{body.labs_summary}
用藥紀錄：{body.meds_summary}
補充說明：{body.custom_notes}

請輸出：
**S (Subjective):** 主觀敘述（病患主訴）
**O (Objective):** 客觀資料（生命徵象、檢驗值）
**A (Assessment):** 評估與診斷
**P (Plan):** 治療計畫（用藥、追蹤）

語氣專業，符合健保申報格式。"""
    return {"soap": ask_gemini(prompt)}


class BettyAuditBody(BaseModel):
    question: str
    context: str = ""

@router.post("/betty-audit")
def betty_audit(body: BettyAuditBody):
    prompt = f"""你是凱程診所的健保申報輔導員貝蒂。
背景資訊：{body.context}
院長問：{body.question}
請提供健保抽審因應建議，語氣專業且具操作性。字數 200 字以內。"""
    return {"reply": ask_gemini(prompt)}
