"""
/api/insulin/*  胰島素追蹤滴定系統
讀取 CO02P.db (HIS 藥品記錄) + CO01M.db (病患基本資料) → 胰島素病患名單
BQ v_all_labs_human_readable → 近期空腹血糖 / HbA1c
"""
import os, sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.iheal_service import log_push
from core.config import DIGITAL_DB, CO01M_DB

router = APIRouter(prefix="/api/insulin", tags=["胰島素追蹤"])

CO02P_DB     = "/Users/cometmacmini/clinic_research/data_backup/CO02P.db"
BQ_PROJECT   = "goplace-488704"
CREDS_FILE   = "/Users/cometmacmini/.openclaw/secrets/medibot_key.json"
LOOKBACK_MONTHS = 6

# 藥品代碼對照
DRUG_MAP = {
    "TOU0": ("Toujeo", "長效"),
    "TRE0": ("Tresiba", "長效"),
    "API":  ("Apidra",  "速效"),
    "NOV2": ("Novorapid", "速效"),
    "RYZ0": ("Ryzodeg", "雙效"),
    "SOL3": ("Soliqua", "複方"),
}
ALL_CODES = list(DRUG_MAP.keys())

SOP_BY_STAGE = {
    "第 0 天 (建檔關懷)": [
        "確認病患了解注射筆操作",
        "協助病患綁定雲端上傳系統",
        "衛教單張與低血糖處置提醒",
    ],
    "第 3 天 (首次追蹤)": [
        "自我注射是否有問題",
        "是否發生低血糖",
        "藥物保存是否正確 (夏天防熱)",
        "是否規律上傳數據",
        "隨身攜帶糖果宣導",
    ],
    "第 7 天 (二次追蹤)": [
        "重新確認注射技術",
        "檢視一週血糖趨勢",
        "確認飲食碳水化合物比例",
        "低血糖處理覆核",
        "鼓勵持續紀錄",
    ],
    "第 26 天 (回診提醒)": [
        "提醒回診時間",
        "攜帶剩餘藥物 (空筆針) 回診",
        "攜帶完整血糖數據回診",
    ],
}


def _parse_roc_date(roc_str: str) -> Optional[datetime]:
    try:
        s = str(roc_str).strip()
        if len(s) == 7:
            y, m, d = int(s[:3]) + 1911, int(s[3:5]), int(s[5:7])
            return datetime(y, m, d)
    except Exception:
        pass
    return None


def _get_stage(rx_date: datetime) -> Optional[str]:
    days = (datetime.now() - rx_date).days
    if 0 <= days <= 2:   return "第 0 天 (建檔關懷)"
    if 3 <= days <= 6:   return "第 3 天 (首次追蹤)"
    if 7 <= days <= 10:  return "第 7 天 (二次追蹤)"
    if 26 <= days <= 29: return "第 26 天 (回診提醒)"
    return None


def _bq_client():
    from google.cloud import bigquery
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(
        CREDS_FILE, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return bigquery.Client(project=BQ_PROJECT, credentials=creds)


def _pid_filter(pid: str) -> str:
    p = str(pid).strip().zfill(7)
    return f"LPAD(TRIM(REPLACE(CAST(Patient_ID AS STRING), '.0', '')), 7, '0') = '{p}'"


# ─────────────────────────────────────────────
@router.get("/patients")
def get_patients():
    """讀取 CO02P.db 取得近半年有開立胰島素的病患名單"""
    if not os.path.exists(CO02P_DB):
        raise HTTPException(404, f"CO02P.db not found at {CO02P_DB}")
    if not os.path.exists(CO01M_DB):
        raise HTTPException(404, f"CO01M.db not found at {CO01M_DB}")

    past_date  = datetime.now() - relativedelta(months=LOOKBACK_MONTHS)
    roc_limit  = f"{past_date.year - 1911:03d}{past_date.month:02d}{past_date.day:02d}"
    codes_str  = "','".join(ALL_CODES)

    conn_m = sqlite3.connect(CO01M_DB)
    name_rows = conn_m.execute(
        "SELECT TRIM(KCSTMR), TRIM(MNAME), TRIM(MTELH) FROM CO01M"
    ).fetchall()
    conn_m.close()
    name_map = {r[0]: {"name": r[1], "phone": r[2] or ""} for r in name_rows}

    conn_p = sqlite3.connect(CO02P_DB)
    drug_rows = conn_p.execute(
        f"SELECT KCSTMR, KDRUG, PDATE, PQTY, PDAY "
        f"FROM CO02P WHERE PDATE >= '{roc_limit}' AND KDRUG IN ('{codes_str}')"
    ).fetchall()
    conn_p.close()

    records: dict = {}
    for (kcstmr, kdrug, pdate, pqty, pday) in drug_rows:
        pid  = str(kcstmr).strip().zfill(7)
        code = str(kdrug).strip().upper()
        info = name_map.get(pid, {"name": "未知", "phone": ""})

        if pid not in records:
            records[pid] = {
                "pid": pid,
                "name": info["name"],
                "phone": info["phone"],
                "rx_date": str(pdate).strip(),
                "days": int(pday or 0),
                "basal":  {"drug": "無", "dose": 0.0},
                "bolus":  {"drug": "無", "dose": 0.0},
                "dual":   {"drug": "無", "dose": 0.0},
                "combo":  {"drug": "無", "dose": 0.0},
            }

        drug_name, cat = DRUG_MAP.get(code, (code, "長效"))
        dose = float(pqty or 0)
        cat_key = {"長效": "basal", "速效": "bolus", "雙效": "dual", "複方": "combo"}[cat]
        records[pid][cat_key] = {"drug": drug_name, "dose": dose}

    patients = []
    for p in records.values():
        rx_dt = _parse_roc_date(p["rx_date"])
        p["stage"] = _get_stage(rx_dt) if rx_dt else None
        p["sop"]   = SOP_BY_STAGE.get(p["stage"], []) if p["stage"] else []
        patients.append(p)

    # 今日任務在前，其餘按日期降序
    patients.sort(key=lambda x: (0 if x["stage"] else 1, x["rx_date"]), reverse=False)
    patients.sort(key=lambda x: x["stage"] is None)
    return {"patients": patients, "total": len(patients)}


@router.get("/patient-data/{pid}")
def patient_data(pid: str):
    """BQ 近期空腹血糖趨勢 + HbA1c"""
    try:
        filt = _pid_filter(pid)
        bq = _bq_client()

        # 近期空腹血糖 (AC-Sugar) 最近 90 天
        sql_bg = f"""
            SELECT Lab_Value, Lab_Date
            FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
            WHERE {filt}
              AND Lab_Name = 'AC-Sugar'
              AND Lab_Date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            ORDER BY Lab_Date DESC
            LIMIT 20
        """
        bg_rows = list(bq.query(sql_bg).result())
        fasting_bg = [{"date": str(r["Lab_Date"]), "value": str(r["Lab_Value"])} for r in bg_rows]

        # 最近 HbA1c
        sql_hba = f"""
            SELECT Lab_Value, Lab_Date
            FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
            WHERE {filt} AND Lab_Name = 'HbA1c'
            ORDER BY Lab_Date DESC LIMIT 3
        """
        hba_rows = list(bq.query(sql_hba).result())
        hba1c = [{"date": str(r["Lab_Date"]), "value": str(r["Lab_Value"])} for r in hba_rows]

        # 簡易 AI 建議
        ai_suggestion = _compute_suggestion(fasting_bg)

        return {"fasting_bg": fasting_bg, "hba1c": hba1c, "ai": ai_suggestion}
    except Exception as e:
        return {"fasting_bg": [], "hba1c": [], "ai": None, "error": str(e)}


def _compute_suggestion(fasting_bg: list) -> Optional[dict]:
    """根據近5日空腹血糖給出簡易建議"""
    if not fasting_bg:
        return None
    recent = fasting_bg[:5]
    vals = []
    for r in recent:
        try:
            vals.append(float(r["value"]))
        except Exception:
            pass
    if not vals:
        return None

    days_over_180 = sum(1 for v in vals if v > 180)
    days_over_140 = sum(1 for v in vals if v > 140)
    has_hypo      = any(v < 70 for v in vals)

    if has_hypo:
        return {
            "pattern": "低血糖警訊",
            "color": "red",
            "msg": "🚨 近期出現低血糖！安全優先，建議減量或檢視飲食狀況。",
            "action": "減量 4U",
        }
    if days_over_180 >= 3:
        return {
            "pattern": "空腹顯著偏高 (>180 三天以上)",
            "color": "orange",
            "msg": "📈 近期空腹血糖持續偏高 (>180)，建議基礎胰島素加量 4U 滴定。",
            "action": "加量 4U",
        }
    if days_over_140 >= 3:
        return {
            "pattern": "空腹偏高 (>140 三天以上)",
            "color": "yellow",
            "msg": "📈 近期空腹血糖偏高 (>140)，建議基礎胰島素微調加量 2U。",
            "action": "加量 2U",
        }
    return {
        "pattern": "血糖控制平穩",
        "color": "green",
        "msg": "✅ 近期血糖控制良好，維持原劑量。",
        "action": "維持原劑量",
    }


class LogBody(BaseModel):
    pid: str
    name: str
    action: str       # push_line / push_fcm / skip / titrate
    note: str = ""
    stage: str = ""


@router.post("/log-action")
def log_action(body: LogBody):
    """記錄衛教追蹤動作"""
    pid = str(body.pid).strip().zfill(7)
    campaign = f"胰島素滴定追蹤_{body.stage}"
    log_push(pid, campaign, body.action, f"[{body.stage}] {body.note}")
    return {"ok": True}
