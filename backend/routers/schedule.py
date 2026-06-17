"""
/api/schedule/*  今日看診名單（讀 dashboard_data.json）+ 任意病患查詢（讀 CO01M.db）
"""
import json
import os
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Query

from core.config import CO01M_DB

DASHBOARD_JSON = "/Users/cometmacmini/.openclaw/workspace/medical-assistant/dashboard_data.json"

BQ_PROJECT = "goplace-488704"
CREDS_FILE = "/Users/cometmacmini/.openclaw/secrets/medibot_key.json"

router = APIRouter(prefix="/api/schedule", tags=["今日名單"])


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


def _load() -> dict:
    if not os.path.exists(DASHBOARD_JSON):
        return {}
    with open(DASHBOARD_JSON, encoding="utf-8") as f:
        return json.load(f)


@router.get("/meta")
def api_meta():
    """回傳可選的日期、醫師、診別列表，供前端選單用"""
    data = _load()
    if not data:
        return {"dates": [], "doctors": [], "sessions": []}

    dates = sorted(data.keys(), reverse=True)[:30]

    # 收集所有醫師和診別
    doctors_set, sessions_set = set(), set()
    for d in dates[:7]:
        for doc in data[d]:
            doctors_set.add(doc)
            for sess in data[d][doc]:
                sessions_set.add(sess)

    return {
        "dates":   dates,
        "doctors": sorted(doctors_set),
        "sessions": ["早診", "午診", "晚診"],
    }


@router.get("/patients")
def api_patients(
    date:    str = Query(None, description="YYYY-MM-DD，預設今天"),
    session: str = Query(None, description="早診/午診/晚診，預設依時間自動選"),
):
    data = _load()
    if not data:
        return {"patients": [], "date": date, "session": session}

    # 預設今天
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    # 預設診別：依當下時間
    if not session:
        hour = datetime.now().hour
        session = "早診" if hour < 13 else ("午診" if hour < 18 else "晚診")

    day_data = data.get(date, {})

    # 合併所有醫師（張凱傑 + 衛教檢查室）的同診別名單
    DOCTORS = ["張凱傑", "衛教檢查室"]
    seen, unique = set(), []
    for doc in DOCTORS:
        for p in day_data.get(doc, {}).get(session, []):
            k = f"{p.get('病歷號')}_{p.get('姓名')}"
            if k not in seen:
                unique.append(p)
                seen.add(k)

    # 收集當日可用診別（取聯集）
    all_sessions = set()
    for doc in DOCTORS:
        all_sessions.update(day_data.get(doc, {}).keys())

    return {
        "patients":           unique,
        "date":               date,
        "session":            session,
        "available_sessions": sorted(all_sessions),
    }


@router.get("/summary/{pid}")
def api_summary(pid: str):
    """
    鎖定病患速覽：性別/年齡（v_patient_demographics）＋ 最近生命徵象
    （v_patient_vitals：身高/體重/BMI/腰圍/血壓）。
    各欄位取「最近一筆非空值」（最新那筆常缺身高/腰圍），BMI 缺值時用身高體重回算。
    """
    try:
        bq   = _bq_client()
        filt = _pid_filter(pid)

        # 性別 / 年齡
        demo = {"sex": None, "age": None}
        for r in bq.query(
            f"SELECT Sex, Age FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_patient_demographics` "
            f"WHERE {filt} LIMIT 1"
        ).result():
            demo = {"sex": r["Sex"], "age": r["Age"]}

        # 生命徵象：近 12 筆，逐欄取最近非空
        rows = list(bq.query(
            f"SELECT Record_Date, Height, Weight, BMI, SBP, DBP, Waist "
            f"FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_patient_vitals` "
            f"WHERE {filt} ORDER BY Record_Date DESC LIMIT 12"
        ).result())

        vit = {"height": None, "weight": None, "bmi": None,
               "waist": None, "sbp": None, "dbp": None,
               "date": None, "bp_date": None}
        for r in rows:
            if vit["date"] is None:
                vit["date"] = str(r["Record_Date"])
            for k, col in (("height", "Height"), ("weight", "Weight"),
                           ("bmi", "BMI"), ("waist", "Waist")):
                if vit[k] is None and r[col] is not None:
                    vit[k] = float(r[col])
            if vit["sbp"] is None and r["SBP"] is not None:
                vit["sbp"]     = int(r["SBP"])
                vit["dbp"]     = int(r["DBP"]) if r["DBP"] is not None else None
                vit["bp_date"] = str(r["Record_Date"])

        # BMI 缺值 → 用身高(cm)、體重回算
        if vit["bmi"] is None and vit["height"] and vit["weight"]:
            h = vit["height"] / 100.0
            if h > 0:
                vit["bmi"] = round(vit["weight"] / (h * h), 1)

        return {"pid": pid, "demographics": demo, "vitals": vit}

    except Exception as e:
        return {"pid": pid, "error": str(e), "demographics": {}, "vitals": {}}


@router.get("/search")
def api_search(q: str = Query(..., description="身分證字號 或 病歷號")):
    """
    任意病患查詢（仿 dashboard2.py 門診大門手動鎖定）：
    用身分證字號或病歷號到 CO01M.db 撈一筆，回傳與名單相容的病患物件。
    """
    key = (q or "").strip().upper()
    if not key:
        return {"patient": None, "error": "請輸入身分證字號或病歷號"}
    if not os.path.exists(CO01M_DB):
        return {"patient": None, "error": "CO01M.db 不存在"}

    try:
        conn = sqlite3.connect(CO01M_DB)
        conn.row_factory = sqlite3.Row
        # 病歷號可能有前導零，兩種寫法都試
        row = conn.execute(
            "SELECT KCSTMR, MNAME, MPERSONID, MBIRTHDT, "
            "       COALESCE(NULLIF(MREC,''), MTELH) AS PHONE "
            "FROM CO01M "
            "WHERE UPPER(MPERSONID)=? OR KCSTMR=? OR KCSTMR=? "
            "LIMIT 1",
            (key, key, key.zfill(7)),
        ).fetchone()
        conn.close()
    except Exception as e:
        return {"patient": None, "error": str(e)}

    if not row:
        return {"patient": None, "error": f"查無此病患：{q}"}

    pid = str(row["KCSTMR"]).strip().zfill(7)
    patient = {
        "姓名":     str(row["MNAME"] or "").strip(),
        "病歷號":   pid,
        "身分證":   str(row["MPERSONID"] or "").strip(),
        "電話":     str(row["PHONE"] or "").strip(),
        "預約生日": str(row["MBIRTHDT"] or "").strip(),
        "標籤":     "",
        "風險燈號": "🔍 手動查詢",
        "最新檢驗": {},
    }
    return {"patient": patient}
