"""
/api/data-mining/*  雲端大數據探勘 (BigQuery 隊列建構 + Betty SQL)
"""
import os
from fastapi import APIRouter
from pydantic import BaseModel

from services.gemini_service import ask_gemini

router = APIRouter(prefix="/api/data-mining", tags=["大數據探勘"])

BQ_PROJECT   = "goplace-488704"
CREDENTIALS  = "/Users/cometmacmini/.openclaw/secrets/medibot_key.json"
REPORTS_DIR  = "/Users/cometmacmini/clinic_research/reports"


def _bq_client():
    from google.cloud import bigquery
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(CREDENTIALS)
    return bigquery.Client(project=BQ_PROJECT, credentials=creds)


class BettyBody(BaseModel):
    question: str
    history: list[dict] = []

@router.post("/betty-sql")
def betty_sql(body: BettyBody):
    """貝蒂 AI SQL 寫手：把自然語言轉成 BigQuery SQL"""
    ctx = "\n".join([f"{m['role']}: {m['content']}" for m in body.history[-4:]])
    prompt = f"""你是凱程診所的資料工程師貝蒂。
可用 BigQuery 資料表（project: goplace-488704, dataset: kaicheng_cdss_us）：
- v_prescriptions_with_atc (Patient_ID, Order_Date, Drug_Name, ATC_Code, Days)
- v_all_labs_human_readable (Patient_ID, Lab_Date, Lab_Name, Lab_Value)
- v_patient_vitals (Patient_ID, Record_Date, Height, Weight, BMI, SBP, DBP)
- v_patient_demographics (Patient_ID, Sex, Age)

對話脈絡：
{ctx}

院長問：{body.question}

請回傳：
1. 一段可直接執行的 BigQuery SQL (用 ```sql ... ``` 包起來)
2. 簡短說明 (50字內)
"""
    reply = ask_gemini(prompt)
    return {"reply": reply}


class RunSqlBody(BaseModel):
    sql: str
    limit: int = 500

@router.post("/run-sql")
def run_sql(body: RunSqlBody):
    """直接執行 BigQuery SQL，回傳結果"""
    safe_sql = body.sql.strip()
    if not safe_sql.upper().startswith("SELECT"):
        return {"error": "只允許 SELECT 查詢"}
    # 加上 LIMIT 保護
    if "LIMIT" not in safe_sql.upper():
        safe_sql += f" LIMIT {body.limit}"
    try:
        rows = list(_bq_client().query(safe_sql).result())
        if not rows:
            return {"columns": [], "rows": [], "count": 0}
        cols = list(rows[0].keys())
        data = [[str(r[c]) for c in cols] for r in rows]
        return {"columns": cols, "rows": data, "count": len(data)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/export-csv")
def export_csv(body: RunSqlBody):
    """執行 SQL 並將結果存為 CSV 到 REPORTS_DIR"""
    import csv, datetime
    result = run_sql(body)
    if "error" in result:
        return result
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORTS_DIR, f"query_{ts}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(result["columns"])
        w.writerows(result["rows"])
    return {"ok": True, "path": path, "count": result["count"]}
