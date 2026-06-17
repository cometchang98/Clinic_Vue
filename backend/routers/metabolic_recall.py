"""
/api/metabolic-recall/*  代謝症候群防治計畫（衛教師 GAS ⇄ 院長 Vue3）
"""
import json, os, re, sqlite3, subprocess, sys
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.iheal_service import send_push, log_push, lookup_patients
from services.gemini_service import ask_gemini
from core.config import DIGITAL_DB, CO01M_DB

router = APIRouter(prefix="/api/metabolic-recall", tags=["代謝召回"])

SHEET_ID     = "1xIzrmcNRWK03WBrHnBMOCv5bR-NuFalpCeE2WvgGr5E"
CREDS_FILE   = "/Users/cometmacmini/.openclaw/secrets/medibot_key.json"
BQ_PROJECT   = "goplace-488704"
SCOPES       = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


# ─────────────────────────────────────────────
# Google Sheets helpers
# ─────────────────────────────────────────────
def _sheets_svc():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _read_sheet(range_: str) -> list[dict]:
    svc = _sheets_svc()
    res = svc.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=range_).execute()
    rows = res.get("values", [])
    if len(rows) < 2:
        return []
    headers = rows[0]
    return [dict(zip(headers, r + [""] * (len(headers) - len(r)))) for r in rows[1:]]


# ─────────────────────────────────────────────
# CO01M patient lookup (by list of PIDs)
# ─────────────────────────────────────────────
def _enrich_names(pid_set: set) -> dict:
    """回傳 {pid: {name, midno, phone}}"""
    if not pid_set or not os.path.exists(CO01M_DB):
        return {}
    pids = [str(p).strip().zfill(7) for p in pid_set]
    placeholders = ",".join(["?"] * len(pids))
    conn = sqlite3.connect(CO01M_DB)
    rows = conn.execute(
        f"SELECT TRIM(KCSTMR), TRIM(MNAME), TRIM(MPERSONID), TRIM(MTELH) FROM CO01M WHERE TRIM(KCSTMR) IN ({placeholders})",
        pids,
    ).fetchall()
    conn.close()
    return {r[0]: {"name": r[1], "midno": r[2], "phone": r[3]} for r in rows}


# ─────────────────────────────────────────────
# BigQuery: pull recent labs for one patient
# ─────────────────────────────────────────────
def _bq_client():
    from google.cloud import bigquery
    from google.oauth2 import service_account
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(
        CREDS_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return bigquery.Client(project=BQ_PROJECT, credentials=creds)


def _pid_filter(pid: str) -> str:
    p = str(pid).strip().zfill(7)
    return f"LPAD(TRIM(REPLACE(CAST(Patient_ID AS STRING), '.0', '')), 7, '0') = '{p}'"


def _fetch_recent_labs(pid: str) -> dict:
    """取得最近一筆重要檢驗值 (HbA1c, AC-Sugar, TG, HDL, LDL)"""
    filt = _pid_filter(pid)
    sql = f"""
        SELECT Lab_Name, Lab_Value, Lab_Date
        FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
        WHERE {filt}
          AND Lab_Name IN ('HbA1c','AC-Sugar','Triglyceride','HDL-C','LDL-C','Creatinine')
          AND Lab_Date >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 YEAR)
        ORDER BY Lab_Date DESC
    """
    rows = list(_bq_client().query(sql).result())
    latest = {}
    for r in rows:
        name = r["Lab_Name"]
        if name not in latest:
            latest[name] = {"value": str(r["Lab_Value"]), "date": str(r["Lab_Date"])}
    return latest


def _fetch_recent_vitals(pid: str) -> dict:
    """取得最近一筆生命徵象 (SBP, DBP, Weight, Waist)"""
    filt = _pid_filter(pid)
    sql = f"""
        SELECT SBP, DBP, Weight, Waist, Record_Date
        FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_patient_vitals`
        WHERE {filt} AND SBP IS NOT NULL
        ORDER BY Record_Date DESC LIMIT 1
    """
    rows = list(_bq_client().query(sql).result())
    if not rows:
        return {}
    r = rows[0]
    return {k: str(r[k]) for k in ["SBP", "DBP", "Weight", "Waist", "Record_Date"] if r[k] is not None}


# ─────────────────────────────────────────────
# 主要 API
# ─────────────────────────────────────────────

@router.get("/sync-sheets")
def sync_sheets():
    """
    從 Google Sheets 拉取 Metabolic_Enrolled + Metabolic_Followups，
    以病患為單位整合，回傳院長決策頁所需的完整清單。
    """
    enrolled_rows  = _read_sheet("Metabolic_Enrolled!A:N")
    followup_rows  = _read_sheet("Metabolic_Followups!A:M")

    # 所有出現過的 PID
    all_pids = set()
    for r in enrolled_rows:
        all_pids.add(str(r.get("Patient_ID", "")).strip().zfill(7))
    for r in followup_rows:
        all_pids.add(str(r.get("Patient_ID", "")).strip().zfill(7))
    all_pids.discard("0000000")

    name_map = _enrich_names(all_pids)

    # 已申報 PID（本機 DB）
    approved_pids = _get_approved_pids()

    # 整合：以 pid 為 key
    patients: dict[str, dict] = {}
    for r in enrolled_rows:
        pid = str(r.get("Patient_ID", "")).strip().zfill(7)
        if not pid or pid == "0000000":
            continue
        patients.setdefault(pid, {
            "pid": pid, "enrolled": True, "enrolled_date": r.get("Enrolled_Date"),
            "followups": [], "approved": pid in approved_pids,
        })
        patients[pid].update(name_map.get(pid, {}))

    for r in followup_rows:
        pid = str(r.get("Patient_ID", "")).strip().zfill(7)
        if not pid or pid == "0000000":
            continue
        patients.setdefault(pid, {
            "pid": pid, "enrolled": False, "enrolled_date": None,
            "followups": [], "approved": pid in approved_pids,
        })
        patients[pid].update(name_map.get(pid, {}))

        content = r.get("Advice_Content", "")
        # 解析通話結果
        outcome_match = re.search(r"\[通話結果: (.+?)\]", content)
        outcome = outcome_match.group(1) if outcome_match else ""
        patients[pid]["followups"].append({
            "id":        r.get("Followup_ID"),
            "date":      r.get("Followup_Date"),
            "type":      r.get("Followup_Type"),
            "outcome":   outcome,
            "note":      re.sub(r"\[通話結果: .+?\]\n?", "", content).strip(),
            "weight":    r.get("Weight"),
            "waist":     r.get("Waist"),
            "sbp":       r.get("SBP"),
            "dbp":       r.get("DBP"),
            "fpg":       r.get("FPG"),
            "hba1c":     r.get("HbA1c"),
        })

    # 決定每位病患的 latest_contact 狀態
    result = []
    for pid, p in patients.items():
        followups_sorted = sorted(p["followups"], key=lambda x: x["date"] or "", reverse=True)
        latest = followups_sorted[0] if followups_sorted else {}
        latest_outcome = latest.get("outcome", "")

        # 是否接通（「接通」但排除「未接通」，或正式追蹤類型）
        contacted = (("接通" in latest_outcome) and ("未接通" not in latest_outcome)) \
                    or latest.get("type") in ("Followup_2", "Followup_3", "Followup_Annual")
        # 未接通或推播失敗
        failed    = "未接通" in latest_outcome or "失敗" in latest_outcome

        result.append({
            **p,
            "followups":       followups_sorted,
            "latest_type":     latest.get("type", ""),
            "latest_date":     latest.get("date", ""),
            "latest_outcome":  latest_outcome,
            "latest_note":     latest.get("note", ""),
            "contacted":       contacted,
            "failed":          failed,
        })

    # 排序：接通優先、未接通其次、無聯絡最後
    result.sort(key=lambda x: (0 if x["contacted"] else (2 if x["failed"] else 1)))
    return {"patients": result, "synced_at": datetime.now().isoformat()}


@router.get("/patient-labs/{pid}")
def patient_labs(pid: str):
    """從 BigQuery 取得該病患近期檢驗 + 生命徵象"""
    try:
        labs   = _fetch_recent_labs(pid)
        vitals = _fetch_recent_vitals(pid)
        return {"labs": labs, "vitals": vitals}
    except Exception as e:
        return {"labs": {}, "vitals": {}, "error": str(e)}


class ApproveBody(BaseModel):
    pid: str
    name: str
    code: str = "P7502C"       # P7501C / P7502C / P7503C
    note: str = ""

@router.post("/approve")
def approve(body: ApproveBody):
    """記錄院長申報決定 → Case_Enrollment + marketing_logs"""
    now = datetime.now().isoformat()
    pid = str(body.pid).strip().zfill(7)
    conn = sqlite3.connect(DIGITAL_DB)
    try:
        # 寫入 Case_Enrollment（主要申報紀錄）
        conn.execute("""
            INSERT INTO Case_Enrollment (PID, Last_Code, Last_Date, Is_Metabolic_Syndrome, Last_Updated)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(PID) DO UPDATE SET
                Last_Code=excluded.Last_Code,
                Last_Date=excluded.Last_Date,
                Last_Updated=excluded.Last_Updated
        """, (pid, body.code, now[:10], now))
        # 同時寫入 marketing_logs 保留文字備註
        conn.execute("""
            INSERT INTO marketing_logs (pid, campaign_name, send_date, push_type, content)
            VALUES (?, ?, ?, ?, ?)
        """, (
            pid,
            f"代謝症候群防治_{body.code}",
            now[:10],
            "nhi_approved",
            f"【{body.code}】{body.note}",
        ))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "code": body.code, "pid": pid}


def _get_approved_pids() -> set:
    conn = sqlite3.connect(DIGITAL_DB)
    try:
        rows = conn.execute(
            "SELECT DISTINCT PID FROM Case_Enrollment WHERE Last_Code IN ('P7501C','P7502C','P7503C')"
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()
    finally:
        conn.close()


# ─────────────────────────────────────────────
# Streamlit 版保留功能 (舊 cards JSON 流程)
# ─────────────────────────────────────────────
CARDS_JSON   = "/Users/cometmacmini/clinic_research/reports/metabolic_recall_cards.json"
AGENT_SCRIPT = "/Users/cometmacmini/clinic_research/metabolic_recall_agent.py"

@router.post("/run-agent")
def run_agent():
    if not os.path.exists(AGENT_SCRIPT):
        raise HTTPException(404, "agent script not found")
    result = subprocess.run([sys.executable, AGENT_SCRIPT], capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise HTTPException(500, result.stderr[-2000:])
    return {"ok": True}


class SkipBody(BaseModel):
    pid: str
    note: str
    campaign: str = "代謝症候群防治計畫"

@router.post("/skip")
def skip_patient(body: SkipBody):
    log_push(body.pid, body.campaign, "clinical_skip", f"【院長臨床豁免】{body.note}")
    return {"ok": True}
