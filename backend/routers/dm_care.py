"""
/api/dm-care/*  糖尿病管理模組化卡片 API

M1 數值概覽：HbA1c 趨勢 + 空腹血糖 + 達標判斷
M2 用藥分析：目前用藥 + 胰島素種類 + 用藥連續性甘特圖（慢箋合併）
M3 達標+888（區塊1/3）、可申報項目（區塊2）、健保用藥防呆（區塊4）
   規則來源：backend/reference/NHI_給付規則_DM_CKD_肝炎.md
"""
import os
import re
import sqlite3
from datetime import datetime, timedelta
from fastapi import APIRouter

BQ_PROJECT = "goplace-488704"
CREDS_FILE = "/Users/cometmacmini/.openclaw/secrets/medibot_key.json"
CO02P_DB   = "/Users/cometmacmini/clinic_research/data_backup/CO02P.db"

# ── 降糖藥 ATC 機轉分類（M3 區塊4 用藥防呆）─────────────────
# 複方：A10BD15/20=SGLT2i+Met、A10BD19=SGLT2i+DPP4i、A10BD05/08/11=DPP4i+Met
def _is_sglt2(atc): a=str(atc).upper(); return a.startswith("A10BK") or a in ("A10BD15","A10BD19","A10BD20")
def _is_dpp4(atc):  a=str(atc).upper(); return a.startswith("A10BH") or a in ("A10BD05","A10BD08","A10BD11","A10BD19")
def _is_glp1(atc):  a=str(atc).upper(); return a.startswith("A10BJ") or a == "A10AE54"   # A10AE54=Soliqua(含GLP1)
def _is_metformin(atc): a=str(atc).upper(); return a == "A10BA02" or a.startswith("A10BD")  # 多數複方含Met
def _is_su(atc):    return str(atc).upper().startswith("A10BB")
def _is_insulin(atc): return str(atc).upper().startswith("A10A")

# 健保申報碼（115年家醫/P4P）
PCODE_INFO = {
    "P1407": ("DM 新收案",   650, "收案"),
    "P1408": ("DM 追蹤",     200, "追蹤"),
    "P1409": ("DM 年度評估", 800, "年評"),
    "P7001": ("DKD 追蹤",    400, "追蹤"),
    "P7002": ("DKD 年度評估", 800, "年評"),
}

router = APIRouter(prefix="/api/dm-care", tags=["DM Care 模組"])


# ── BQ 工具 ──────────────────────────────────────────────
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


# ── 達標判斷 ─────────────────────────────────────────────
def _hba1c_status(val: float) -> dict:
    if val < 7.0:
        return {"label": "達標", "color": "green",  "icon": "✅"}
    if val < 9.0:
        return {"label": "未達標", "color": "yellow", "icon": "⚠️"}
    return     {"label": "危險",   "color": "red",    "icon": "🚨"}


def _trend_arrow(values: list[float]) -> str:
    """比較最新兩次數值，回傳趨勢箭頭"""
    if len(values) < 2:
        return "→"
    diff = values[0] - values[1]
    if diff > 0.3:  return "↑"
    if diff < -0.3: return "↓"
    return "→"


def _glucose_pattern(vals: list[float]) -> dict:
    """分析近期空腹血糖 pattern"""
    if not vals:
        return {"label": "無資料", "color": "gray", "icon": "—"}
    recent5 = vals[:5]
    if any(v < 70 for v in recent5):
        return {"label": "低血糖警訊", "color": "red",    "icon": "🚨"}
    if sum(1 for v in recent5 if v > 180) >= 3:
        return {"label": "顯著偏高",   "color": "orange", "icon": "📈"}
    if sum(1 for v in recent5 if v > 140) >= 3:
        return {"label": "輕度偏高",   "color": "yellow", "icon": "📊"}
    avg = sum(recent5) / len(recent5)
    if avg <= 130:
        return {"label": "控制良好",   "color": "green",  "icon": "✅"}
    return     {"label": "尚可",       "color": "blue",   "icon": "ℹ️"}


# ── M1 關鍵檢驗（腎/脂/肝）─────────────────────────────────
# Lab_Name 對照（已用 BQ v_all_labs_human_readable 實際盤點確認）：
#   Creatinine 精確比對（避開 'Creatinine - Urine' 尿肌酐）
#   eGFR='CKD-EPI eGFR'、UACR 用 '%ACR%'（涵蓋 'Urine ACR'/'U-ACR'）
#   LDL 無 'LDL-C'，分散成 'LDL Cholesterol'/'LDL(C)'/'*LDL-CHOL' → 用 '%LDL%'
#   TG='Triglyceride'、HDL='HDL-C'、GPT='SGPT(ALT)'
_M1_LAB_META = {
    "creatinine": {"name": "肌酸酐 Cr",   "unit": "mg/dL", "higher_bad": True},
    "egfr":       {"name": "腎絲球 eGFR",  "unit": "",      "higher_bad": False},
    "uacr":       {"name": "尿蛋白 UACR",  "unit": "mg/g",  "higher_bad": True},
    "ldl":        {"name": "壞膽固醇 LDL", "unit": "mg/dL", "higher_bad": True},
    "tg":         {"name": "三酸甘油酯 TG", "unit": "mg/dL", "higher_bad": True},
    "hdl":        {"name": "好膽固醇 HDL", "unit": "mg/dL", "higher_bad": False},
    "gpt":        {"name": "肝功能 GPT",   "unit": "U/L",   "higher_bad": True},
}
_M1_LAB_ORDER = ["creatinine", "egfr", "uacr", "ldl", "tg", "hdl", "gpt"]


def _lab_flag(ind: str, v: float) -> str:
    """關鍵檢驗紅黃綠燈（依常用臨床參考範圍 / DM 控制目標）"""
    if v is None:
        return "slate"
    if ind == "creatinine": return "green" if v < 1.3  else ("red" if v > 1.5  else "amber")
    if ind == "egfr":       return "green" if v >= 60  else ("red" if v < 30   else "amber")
    if ind == "uacr":       return "green" if v < 30   else ("red" if v > 300  else "amber")
    if ind == "ldl":        return "green" if v < 100  else ("red" if v > 160  else "amber")
    if ind == "tg":         return "green" if v < 150  else ("red" if v > 200  else "amber")
    if ind == "hdl":        return "green" if v >= 40  else "amber"   # 越低越差
    if ind == "gpt":        return "green" if v < 40   else ("red" if v > 80   else "amber")
    return "slate"


def _pct_trend(vals: list[float]) -> str:
    """以變化百分比判趨勢（適用各種量級的檢驗，門檻 ±5%）"""
    if len(vals) < 2 or not vals[1]:
        return "→"
    d = (vals[0] - vals[1]) / abs(vals[1])
    if d > 0.05:  return "↑"
    if d < -0.05: return "↓"
    return "→"


def _m1_extra_labs(bq, pid: str) -> list[dict]:
    """一次抓 Cr/eGFR/UACR/LDL/TG/HDL/GPT 最近 2 筆非空值（取趨勢），回傳排序後清單"""
    filt = _pid_filter(pid)
    sql = f"""
        WITH base AS (
          SELECT
            CASE
              WHEN Lab_Name = 'Creatinine'        THEN 'creatinine'
              WHEN UPPER(Lab_Name) LIKE '%EGFR%'  THEN 'egfr'
              WHEN UPPER(Lab_Name) LIKE '%ACR%'   THEN 'uacr'
              WHEN UPPER(Lab_Name) LIKE '%LDL%'   THEN 'ldl'
              WHEN Lab_Name = 'Triglyceride'      THEN 'tg'
              WHEN Lab_Name = 'HDL-C'             THEN 'hdl'
              WHEN Lab_Name = 'SGPT(ALT)'         THEN 'gpt'
            END AS ind,
            SAFE_CAST(Lab_Value AS FLOAT64) AS val,
            Lab_Date
          FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
          WHERE {filt}
            AND SAFE_CAST(Lab_Value AS FLOAT64) IS NOT NULL
            AND (
              Lab_Name = 'Creatinine' OR UPPER(Lab_Name) LIKE '%EGFR%'
              OR UPPER(Lab_Name) LIKE '%ACR%' OR UPPER(Lab_Name) LIKE '%LDL%'
              OR Lab_Name = 'Triglyceride' OR Lab_Name = 'HDL-C' OR Lab_Name = 'SGPT(ALT)'
            )
        ),
        ranked AS (
          SELECT ind, val, Lab_Date,
                 ROW_NUMBER() OVER (PARTITION BY ind ORDER BY Lab_Date DESC) rn
          FROM base WHERE ind IS NOT NULL
        )
        SELECT ind, val, Lab_Date, rn FROM ranked WHERE rn <= 2 ORDER BY ind, rn
    """
    by_ind: dict[str, list] = {}
    for r in bq.query(sql).result():
        by_ind.setdefault(r["ind"], []).append({"val": r["val"], "date": str(r["Lab_Date"])})

    out = []
    for key in _M1_LAB_ORDER:
        recs = by_ind.get(key)
        if not recs:
            continue
        meta = _M1_LAB_META[key]
        latest = recs[0]
        out.append({
            "key":        key,
            "name":       meta["name"],
            "unit":       meta["unit"],
            "higher_bad": meta["higher_bad"],
            "value":      round(latest["val"], 2),
            "date":       latest["date"],
            "trend":      _pct_trend([r["val"] for r in recs]),
            "status":     _lab_flag(key, latest["val"]),
        })
    return out


# ── M1 主要端點 ───────────────────────────────────────────
@router.get("/m1/{pid}")
def m1_overview(pid: str):
    """
    M1 數值概覽
    回傳：HbA1c (最近4次) + 空腹血糖 (近90天最多20筆) + 達標判斷 + 趨勢
          + 關鍵檢驗 labs（Cr/eGFR/UACR/LDL/TG/HDL/GPT 最近值）
    """
    try:
        filt = _pid_filter(pid)
        bq   = _bq_client()

        # ── HbA1c 最近 4 次 ──────────────────────────────
        sql_hba = f"""
            SELECT Lab_Value, Lab_Date
            FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
            WHERE {filt} AND Lab_Name = 'HbA1c'
            ORDER BY Lab_Date DESC
            LIMIT 4
        """
        hba_rows = list(bq.query(sql_hba).result())
        hba1c_list = [
            {"date": str(r["Lab_Date"]), "value": float(r["Lab_Value"])}
            for r in hba_rows
        ]

        # ── 空腹血糖 近 90 天 ─────────────────────────────
        sql_bg = f"""
            SELECT Lab_Value, Lab_Date
            FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
            WHERE {filt}
              AND Lab_Name = 'AC-Sugar'
              AND Lab_Date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            ORDER BY Lab_Date DESC
            LIMIT 20
        """
        bg_rows  = list(bq.query(sql_bg).result())
        bg_list  = [
            {"date": str(r["Lab_Date"]), "value": float(r["Lab_Value"])}
            for r in bg_rows
        ]
        bg_vals  = [r["value"] for r in bg_list]

        # ── 關鍵檢驗（腎/脂/肝）──────────────────────────
        extra_labs = _m1_extra_labs(bq, pid)

        # ── 組合回傳 ─────────────────────────────────────
        latest_hba1c = hba1c_list[0]["value"] if hba1c_list else None
        hba_vals     = [r["value"] for r in hba1c_list]

        return {
            "pid": pid,
            # HbA1c
            "hba1c": {
                "records":  hba1c_list,
                "latest":   latest_hba1c,
                "trend":    _trend_arrow(hba_vals),
                "status":   _hba1c_status(latest_hba1c) if latest_hba1c else None,
                "days_since": (
                    _days_since(hba1c_list[0]["date"]) if hba1c_list else None
                ),
            },
            # 空腹血糖
            "fasting_bg": {
                "records": bg_list,
                "avg_30d": round(sum(bg_vals[:10]) / len(bg_vals[:10]), 1) if bg_vals else None,
                "min":     min(bg_vals) if bg_vals else None,
                "max":     max(bg_vals) if bg_vals else None,
                "pattern": _glucose_pattern(bg_vals),
            },
            # 關鍵檢驗（腎/脂/肝）
            "labs": extra_labs,
        }

    except Exception as e:
        return {"pid": pid, "error": str(e), "hba1c": None, "fasting_bg": None, "labs": []}


def _days_since(date_str: str) -> int:
    from datetime import date
    d = date.fromisoformat(str(date_str))
    return (date.today() - d).days


# ══════════════════════════════════════════════════════════
# M2 用藥分析
# ══════════════════════════════════════════════════════════

# 三高 ATC 分類（ATC 空白時用藥名補判，避免 QTERN/RYBELSUS 等掉到「其他」）
def _categorize_atc(atc: str, name: str = "") -> str:
    a = str(atc).upper().strip()
    n = str(name).upper()
    if a.startswith("A10") or re.search(_DM_BRAND_RE, n):
        return "🩸 血糖"
    if a.startswith(("C02", "C03", "C07", "C08", "C09")):
        return "🫀 血壓"
    if a.startswith("C10"):
        return "🧈 血脂"
    return "其他"


# 口服降糖神藥（ATC 抓不到時用藥名補抓）
_DM_BRAND_RE = "QTERN|GLYXAMBI|JARDIANCE|FORXIGA|XIGDUO|TRAJENTA|JANUVIA|RYBELSUS"


def _insulin_kind(name: str, atc: str) -> str | None:
    """從藥名 / ATC 判斷胰島素種類；非胰島素回 None"""
    n = str(name).upper()
    a = str(atc).upper()
    if not (a.startswith("A10A") or any(k in n for k in
            ["TOUJEO", "TRESIBA", "LANTUS", "LEVEMIR", "APIDRA", "NOVORAPID",
             "RYZODEG", "SOLIQUA", "HUMALOG", "NOVOMIX", "INSULIN"])):
        return None
    # 雙效 / 複方優先判斷
    if "RYZODEG" in n:               return "雙效"
    if "SOLIQUA" in n:               return "複方"
    if "NOVOMIX" in n or "MIX" in n: return "預混"
    # 長效（基礎）
    if any(k in n for k in ["TOUJEO", "TRESIBA", "LANTUS", "LEVEMIR"]) or a.startswith("A10AE"):
        return "長效"
    # 速效（餐前）
    if any(k in n for k in ["APIDRA", "NOVORAPID", "HUMALOG"]) or a.startswith("A10AB"):
        return "速效"
    return "胰島素"


def _coverage_days(days: float) -> int:
    """
    把一次處方的「給藥日數」換算成甘特圖上的實際覆蓋天數。

    ⚠️ 這是 fallback：當 CO03L 慢箋視圖 join 不到該筆處方時才用。
       正常情況覆蓋天數直接取 BQ v_chronic_prescriptions.Gantt_Coverage_Days
       （慢箋 = 單次×LLDTT總次數 +14 緩衝；急性 = 原天數，不誤判）。
       此處 *3+14 僅為保險近似。
    """
    return int(days * 3 + 14)


def _merge_segments(records: list[dict]) -> list[dict]:
    """
    把同一支藥的多次處方，依 Order_Date 排序後合併成連續區段。
    ★ 分組鍵＝健保代號(code)，非藥名：同代號＝同一條線（名稱字串略異也合併），
       換廠牌(不同代號)才另開一列。
    records: [{date, coverage, cat, drug, code, atc}]
    回傳: [{cat, drug, code, start, end}]
    """
    by_code: dict[str, list[dict]] = {}
    for r in records:
        key = str(r.get("code") or r["drug"])   # 無代號時退回用藥名
        by_code.setdefault(key, []).append(r)

    merged = []
    for code, items in by_code.items():
        items.sort(key=lambda x: x["date"])
        s_date = e_date = None
        cat  = items[0]["cat"]
        drug = items[-1]["drug"]                 # 用最新一筆的藥名當標籤
        for it in items:
            start = datetime.fromisoformat(it["date"])
            cover = it.get("coverage") or _coverage_days(it["days"])
            end   = start + timedelta(days=cover)
            if s_date is None:
                s_date, e_date = start, end
            elif start <= e_date:            # 與前段重疊 → 延伸
                e_date = max(e_date, end)
            else:                            # 斷開 → 收一段、開新段
                merged.append({"cat": cat, "drug": drug, "code": code,
                               "start": s_date.date().isoformat(),
                               "end":   e_date.date().isoformat()})
                s_date, e_date = start, end
        if s_date is not None:
            merged.append({"cat": cat, "drug": drug, "code": code,
                           "start": s_date.date().isoformat(),
                           "end":   e_date.date().isoformat()})
    return merged


@router.get("/m2/{pid}")
def m2_medications(pid: str):
    """
    M2 用藥分析（醫師版）
    - current_dm：最新一次處方裡的 DM 用藥（含胰島素種類、天數）
    - last_rx_date / expected_refill：最後處方日 + 推算耗盡日
    - gantt：三高用藥連續性區段（慢箋合併）
    """
    try:
        bq = _bq_client()
        p  = str(pid).strip().zfill(7)
        # pa.* = v_prescriptions_with_atc（ATC 分類 + 藥名）
        # cp.* = v_chronic_prescriptions（CO03L 真實慢箋覆蓋天數，已含 +14 緩衝/急性原天數）
        pid_pa = f'LPAD(TRIM(REPLACE(CAST(pa.Patient_ID AS STRING), ".0", "")), 7, "0") = "{p}"'

        sql = f"""
            SELECT pa.Order_Date, pa.Drug_Name, pa.ATC_Code, pa.Internal_Code, pa.Days,
                   cp.Gantt_Coverage_Days, cp.True_Coverage_Days,
                   cp.Is_Chronic, cp.Refill_Count_Raw
            FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_prescriptions_with_atc` pa
            LEFT JOIN `{BQ_PROJECT}.kaicheng_cdss_us.v_chronic_prescriptions` cp
              ON LPAD(TRIM(REPLACE(CAST(pa.Patient_ID AS STRING), ".0", "")), 7, "0") = cp.Patient_ID
              AND pa.Order_Date    = cp.Visit_Date
              AND pa.Internal_Code = cp.Drug_Code
            WHERE {pid_pa}
              AND SAFE_CAST(pa.Order_Date AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 YEAR)
              AND (
                    UPPER(pa.ATC_Code) LIKE 'A10%'
                 OR UPPER(pa.ATC_Code) LIKE 'C02%' OR UPPER(pa.ATC_Code) LIKE 'C03%'
                 OR UPPER(pa.ATC_Code) LIKE 'C07%' OR UPPER(pa.ATC_Code) LIKE 'C08%'
                 OR UPPER(pa.ATC_Code) LIKE 'C09%' OR UPPER(pa.ATC_Code) LIKE 'C10%'
                 OR REGEXP_CONTAINS(UPPER(pa.Drug_Name), r'{_DM_BRAND_RE}')
              )
            ORDER BY pa.Order_Date DESC
        """
        rows = list(bq.query(sql).result())

        recs = []
        for r in rows:
            date_raw = str(r["Order_Date"])[:10]
            if not date_raw or date_raw == "None":
                continue
            atc  = r["ATC_Code"] or ""
            name = (r["Drug_Name"] or "").strip()
            days = float(r["Days"] or 30)
            gcov = r["Gantt_Coverage_Days"]   # CO03L 真實覆蓋（含緩衝），可能為 None
            recs.append({
                "date":     date_raw,
                "drug":     name,
                "atc":      atc,
                "code":     r["Internal_Code"],
                "days":     days,
                "coverage": int(gcov) if gcov is not None else None,
                "chronic":  bool(r["Is_Chronic"]) if r["Is_Chronic"] is not None else None,
                "refills":  r["Refill_Count_Raw"],
                "cat":      _categorize_atc(atc, name),
            })

        if not recs:
            return {"pid": pid, "current_dm": [], "gantt": [],
                    "last_rx_date": None, "expected_refill": None}

        # ── 最後處方日 → 推算耗盡日（只看 DM 藥）─────────────
        dm_recs   = [r for r in recs if r["cat"] == "🩸 血糖"]
        last_date = max((r["date"] for r in dm_recs), default=None)

        current_dm, expected_refill = [], None
        if last_date:
            for r in dm_recs:
                if r["date"] == last_date:
                    current_dm.append({
                        "drug":    r["drug"],
                        "atc":     r["atc"],
                        "days":    int(r["days"]),
                        "insulin": _insulin_kind(r["drug"], r["atc"]),
                        "chronic": r["chronic"],
                        "refills": r["refills"],
                    })
            # 耗盡日 = 最後處方日 + 真實覆蓋天數（取該次最大覆蓋）
            covers = [
                (r["coverage"] if r["coverage"] is not None else _coverage_days(r["days"]))
                for r in dm_recs if r["date"] == last_date
            ]
            exp = datetime.fromisoformat(last_date) + timedelta(days=max(covers, default=_coverage_days(30)))
            expected_refill = exp.date().isoformat()

        # ── 甘特圖區段（三高全包，覆蓋天數用 CO03L 真實值）──────
        gantt = _merge_segments(recs)
        gantt.sort(key=lambda x: (x["cat"], x["drug"]))

        return {
            "pid":             pid,
            "current_dm":      current_dm,
            "last_rx_date":    last_date,
            "expected_refill": expected_refill,
            "days_to_refill":  (_days_until(expected_refill) if expected_refill else None),
            "gantt":           gantt,
        }

    except Exception as e:
        return {"pid": pid, "error": str(e),
                "current_dm": [], "gantt": [],
                "last_rx_date": None, "expected_refill": None}


def _days_until(date_str: str) -> int:
    from datetime import date
    return (date.fromisoformat(str(date_str)) - date.today()).days


# ══════════════════════════════════════════════════════════
# M3 達標 + 888 獎金狀態（醫師版）
# 區塊 1：HbA1c 達標判定
# 區塊 3：888 0轉1 獎金狀態（HbA1c<7 / LDL<100 / UACR<30 三關）
# ══════════════════════════════════════════════════════════

# 888 達標門檻（與 strategy_888_0to1.py 一致；越接近門檻星越多＝越易攻略）
_888_RULES = {
    "HbA1c": {"target": 7.0,  "op": "<", "unit": "%",     "name": "糖化血色素"},
    "LDL":   {"target": 100,  "op": "<", "unit": "mg/dL", "name": "壞膽固醇 LDL"},
    "UACR":  {"target": 30,   "op": "<", "unit": "mg/g",  "name": "尿蛋白 UACR"},
}


def _star(indicator: str, v: float) -> int:
    """攻略難度星等：99=已達標、3=極易、2=中等、1=困難、0=無資料"""
    try:
        v = float(v)
    except Exception:
        return 0
    if indicator == "HbA1c":
        if v < 7.0:  return 99
        if v <= 8.0: return 3
        if v <= 9.0: return 2
        return 1
    if indicator == "LDL":
        if v < 100:  return 99
        if v <= 130: return 3
        if v <= 160: return 2
        return 1
    if indicator == "UACR":
        if v < 30:   return 99
        if v <= 200: return 3
        if v <= 500: return 2
        return 1
    return 0


_STAR_LABEL = {99: "✅ 已達標", 3: "⭐⭐⭐ 極易", 2: "⭐⭐ 中等", 1: "⭐ 困難", 0: "—"}


def _member_pattern(pid: str) -> tuple[str, list[str]]:
    """
    從個管名冊判斷 888 樣態與該看哪些指標。
    回傳 (樣態標籤, [指標清單])。非名冊內病患預設 DM 樣態一。
    """
    import json
    from core.config import ACTIVE_MEMBERS_DB
    tags = []
    try:
        members = json.load(open(ACTIVE_MEMBERS_DB, encoding="utf-8"))
        p = str(pid).strip().zfill(7)
        for m in members:
            if str(m.get("病歷號", "")).strip().zfill(7) == p:
                tags = m.get("計畫類別", []) or []
                break
    except Exception:
        pass
    joined = " ".join(tags)
    if "DKD" in joined or "腎病變" in joined:
        return "DKD 樣態三", ["HbA1c", "LDL", "UACR"]
    if "CKD" in joined or "慢性腎病" in joined:
        return "CKD 樣態二", ["LDL", "UACR"]
    return "DM 樣態一", ["HbA1c", "LDL"]


def _latest_labs(bq, pid: str) -> dict:
    """一次抓 HbA1c / LDL / UACR 最新值（各取最近一筆）"""
    filt = _pid_filter(pid)
    sql = f"""
        WITH ranked AS (
          SELECT
            CASE
              WHEN Lab_Name = 'HbA1c' THEN 'HbA1c'
              WHEN UPPER(Lab_Name) LIKE '%LDL%' THEN 'LDL'
              WHEN UPPER(Lab_Name) LIKE '%ACR%' THEN 'UACR'
            END AS ind,
            SAFE_CAST(Lab_Value AS FLOAT64) AS val,
            Lab_Date,
            ROW_NUMBER() OVER (
              PARTITION BY CASE
                WHEN Lab_Name = 'HbA1c' THEN 'HbA1c'
                WHEN UPPER(Lab_Name) LIKE '%LDL%' THEN 'LDL'
                WHEN UPPER(Lab_Name) LIKE '%ACR%' THEN 'UACR'
              END
              ORDER BY Lab_Date DESC
            ) AS rn
          FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
          WHERE {filt}
            AND (Lab_Name = 'HbA1c' OR UPPER(Lab_Name) LIKE '%LDL%' OR UPPER(Lab_Name) LIKE '%ACR%')
            AND SAFE_CAST(Lab_Value AS FLOAT64) IS NOT NULL
        )
        SELECT ind, val, Lab_Date FROM ranked WHERE rn = 1 AND ind IS NOT NULL
    """
    out = {}
    for r in bq.query(sql).result():
        out[r["ind"]] = {"value": r["val"], "date": str(r["Lab_Date"])}
    return out


def _lab_year_counts(bq, pid: str) -> dict:
    """本年度 HbA1c / LDL 檢驗次數 + 最新 eGFR（區塊2 定期檢驗、區塊4 防呆用）"""
    filt = _pid_filter(pid)
    sql = f"""
        SELECT
          COUNTIF(Lab_Name='HbA1c' AND EXTRACT(YEAR FROM Lab_Date)=EXTRACT(YEAR FROM CURRENT_DATE())) AS hba1c_yr,
          COUNTIF(UPPER(Lab_Name) LIKE '%LDL%' AND EXTRACT(YEAR FROM Lab_Date)=EXTRACT(YEAR FROM CURRENT_DATE())) AS ldl_yr
        FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
        WHERE {filt}
    """
    r = list(bq.query(sql).result())[0]
    out = {"hba1c_yr": int(r["hba1c_yr"] or 0), "ldl_yr": int(r["ldl_yr"] or 0), "egfr": None}
    # 最新 eGFR
    sql2 = f"""
        SELECT SAFE_CAST(Lab_Value AS FLOAT64) v, Lab_Date
        FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_all_labs_human_readable`
        WHERE {filt} AND UPPER(Lab_Name) LIKE '%EGFR%'
          AND SAFE_CAST(Lab_Value AS FLOAT64) IS NOT NULL
        ORDER BY Lab_Date DESC LIMIT 1
    """
    rows = list(bq.query(sql2).result())
    if rows:
        out["egfr"] = {"value": rows[0]["v"], "date": str(rows[0]["Lab_Date"])}
    return out


def _roc_today_year() -> str:
    return str(datetime.now().year - 1911)


def _claims_status(pid: str, pattern: str, lab_counts: dict, has_dm_drug_latest: bool) -> dict:
    """區塊2：本年度健保申報碼狀態 + 可申報提示"""
    track_dkd = "DKD" in pattern
    yr = _roc_today_year() + "0101"   # 民國7碼 當年1/1
    rows = []
    if os.path.exists(CO02P_DB):
        try:
            conn = sqlite3.connect(CO02P_DB)
            rows = conn.execute(
                "SELECT DISTINCT PDATE, KDRUG FROM CO02P "
                "WHERE KCSTMR=? AND PDATE>=? AND KDRUG IN ('P1407','P1408','P1409','P7001','P7002') "
                "ORDER BY PDATE",
                (str(pid).zfill(7), yr),
            ).fetchall()
            conn.close()
        except Exception:
            pass

    enrolled_date = None                  # P1407 收案日
    followups, annual = [], None
    for pdate, code in rows:
        if code == "P1407":
            enrolled_date = pdate
        elif code in ("P1408", "P7001"):
            followups.append(pdate)
        elif code in ("P1409", "P7002"):
            annual = pdate

    def _roc_to_date(s):
        s = str(s).zfill(7)
        return datetime(int(s[:3]) + 1911, int(s[3:5]), int(s[5:7]))

    # 距上次追蹤天數 → 可否申報下次追蹤（間隔需 ≥70 天）
    last_fu = max(followups) if followups else None
    days_since_fu = (datetime.now() - _roc_to_date(last_fu)).days if last_fu else None
    fu_code = "P7001" if track_dkd else "P1408"
    fu_label, fu_pts = PCODE_INFO[fu_code][0], PCODE_INFO[fu_code][1]

    # 申報建議
    suggestions = []
    if not enrolled_date and len(followups) == 0:
        suggestions.append({"icon": "📋", "color": "amber",
                            "text": f"尚未收案，可評估申報 P1407 新收案（650點）"})
    else:
        if days_since_fu is None or days_since_fu >= 70:
            if not has_dm_drug_latest:
                suggestions.append({"icon": "🚫", "color": "red",
                    "text": f"可申報 {fu_code} {fu_label}，但⚠️家醫2.0須當次有開DM藥才給付（目前未開）"})
            else:
                suggestions.append({"icon": "✅", "color": "green",
                    "text": f"距上次追蹤{days_since_fu if days_since_fu is not None else '—'}天（≥70），可申報 {fu_code} {fu_label}（{fu_pts}點）"})
        else:
            suggestions.append({"icon": "⏳", "color": "gray",
                "text": f"距上次追蹤僅{days_since_fu}天，需滿70天才可再申報 {fu_code}"})
        # 年度評估：合計≥3次且當年未報
        annual_code = "P7002" if track_dkd else "P1409"
        if len(followups) >= 3 and not annual:
            suggestions.append({"icon": "🏅", "color": "green",
                "text": f"追蹤已{len(followups)}次（≥3），可申報 {annual_code} 年度評估（{PCODE_INFO[annual_code][1]}點）"})

    # 定期檢驗達成加成（家醫2.0：2次HbA1c + 2次LDL/年 → 100元/年）
    hba1c_ok = lab_counts["hba1c_yr"] >= 2
    ldl_ok   = lab_counts["ldl_yr"] >= 2
    lab_bonus = {
        "hba1c": {"count": lab_counts["hba1c_yr"], "need": 2, "ok": hba1c_ok},
        "ldl":   {"count": lab_counts["ldl_yr"],   "need": 2, "ok": ldl_ok},
        "achieved": hba1c_ok and ldl_ok,
    }

    return {
        "track":         "DKD" if track_dkd else "DM",
        "enrolled":      enrolled_date is not None,
        "enrolled_date": enrolled_date,
        "followup_count": len(followups),
        "last_followup": last_fu,
        "days_since_followup": days_since_fu,
        "annual_done":   annual is not None,
        "suggestions":   suggestions,
        "lab_bonus":     lab_bonus,
    }


def _drug_safety(pid: str, labs: dict, lab_counts: dict) -> dict:
    """區塊4：健保用藥防呆（依 NHI 給付規則檢查當次/近期用藥）"""
    # 用 BQ 取最近一次處方日的 A10 藥（含 ATC）+ 近2年是否曾用 Metformin
    cur, ever_metformin = [], False
    try:
        bq = _bq_client()
        filt = _pid_filter(pid)
        sql = f"""
            SELECT Order_Date, ATC_Code, Drug_Name
            FROM `{BQ_PROJECT}.kaicheng_cdss_us.v_prescriptions_with_atc`
            WHERE {filt} AND UPPER(ATC_Code) LIKE 'A10%'
              AND SAFE_CAST(Order_Date AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 YEAR)
            ORDER BY Order_Date DESC
        """
        rows = list(bq.query(sql).result())
        latest_date = str(rows[0]["Order_Date"])[:10] if rows else None
        for r in rows:
            atc = r["ATC_Code"] or ""
            if _is_metformin(atc):
                ever_metformin = True
            if str(r["Order_Date"])[:10] == latest_date:
                cur.append({"atc": atc, "name": (r["Drug_Name"] or "").strip()})
    except Exception as e:
        return {"error": str(e), "checks": []}

    has_sglt2 = any(_is_sglt2(d["atc"]) for d in cur)
    has_dpp4  = any(_is_dpp4(d["atc"])  for d in cur)
    has_glp1  = any(_is_glp1(d["atc"])  for d in cur)
    # 是否為「單一複方A10BD19」造成的同時 true（Glyxambi 本身合法）
    only_combo = all(str(d["atc"]).upper() == "A10BD19" for d in cur if _is_sglt2(d["atc"]) or _is_dpp4(d["atc"]))

    hba1c_v = labs.get("HbA1c", {}).get("value")
    egfr_v  = (lab_counts.get("egfr") or {}).get("value")

    checks = []
    # 1) SGLT2i + DPP4i 同開（非單一複方）
    if has_sglt2 and has_dpp4 and not only_combo:
        checks.append({"level": "danger", "icon": "🚫",
            "text": "同時含 SGLT2i 與 DPP4i：健保規定三擇一，恐核刪（Glyxambi 單方複方除外）"})
    # 2) GLP-1 + SGLT2i/DPP4i
    if has_glp1 and (has_sglt2 or has_dpp4):
        checks.append({"level": "danger", "icon": "🚫",
            "text": "GLP-1 RA 不得與 SGLT2i 或 DPP4i 合併給付"})
    # 3) SGLT2i 但無 Metformin 病史
    if has_sglt2 and not ever_metformin:
        checks.append({"level": "warn", "icon": "⚠️",
            "text": "使用 SGLT2i 但近2年無 Metformin 紀錄：健保要求先用最大耐受 Metformin"})
    # 4) GLP-1 但 HbA1c <8.5%
    if has_glp1 and hba1c_v is not None and hba1c_v < 8.5:
        checks.append({"level": "warn", "icon": "⚠️",
            "text": f"使用 GLP-1 RA 但 HbA1c {hba1c_v}%（<8.5）：除非心血管豁免，恐不符給付門檻"})
    # 5) SGLT2i + eGFR 過低
    if has_sglt2 and egfr_v is not None and egfr_v < 15:
        checks.append({"level": "warn", "icon": "⚠️",
            "text": f"eGFR {egfr_v}（<15）：SGLT2i 應停止健保給付"})

    return {
        "current_meds":  cur,
        "classes": {"sglt2": has_sglt2, "dpp4": has_dpp4, "glp1": has_glp1, "metformin_ever": ever_metformin},
        "checks": checks,
        "ok": len(checks) == 0 and len(cur) > 0,
    }


@router.get("/m3/{pid}")
def m3_targets(pid: str):
    """
    M3 達標 + 888 + 可申報 + 用藥防呆
    - hba1c：達標判定（區塊1）
    - plan888：0轉1 獎金狀態（區塊3）
    - claims：本年度申報碼狀態 + 可申報提示（區塊2）
    - drug_safety：健保用藥防呆（區塊4）
    """
    try:
        bq   = _bq_client()
        labs = _latest_labs(bq, pid)
        pattern, indicators = _member_pattern(pid)
        lab_counts = _lab_year_counts(bq, pid)

        # ── 區塊 1：HbA1c 達標判定 ───────────────────────────
        hba1c = None
        if "HbA1c" in labs:
            v = labs["HbA1c"]["value"]
            if v < 7.0:
                status = {"label": "達標", "color": "green", "icon": "✅"}
            elif v < 9.0:
                status = {"label": "未達標", "color": "yellow", "icon": "⚠️"}
            else:
                status = {"label": "危險", "color": "red", "icon": "🚨"}
            hba1c = {
                "value":     v,
                "date":      labs["HbA1c"]["date"],
                "target":    7.0,            # 個體化目標（未來可調）
                "status":    status,
                "gap":       round(v - 7.0, 1),   # 距達標還差多少（負=已達標）
            }

        # ── 區塊 3：888 0轉1 獎金狀態 ────────────────────────
        checks, met_count = [], 0
        for ind in indicators:
            rule = _888_RULES[ind]
            rec  = labs.get(ind)
            if rec is None:
                checks.append({"indicator": ind, "name": rule["name"], "value": None,
                               "target": rule["target"], "unit": rule["unit"],
                               "met": None, "star": 0, "star_label": "無資料"})
                continue
            st  = _star(ind, rec["value"])
            met = st == 99
            if met:
                met_count += 1
            checks.append({
                "indicator":  ind,
                "name":       rule["name"],
                "value":      rec["value"],
                "date":       rec["date"],
                "target":     rule["target"],
                "unit":       rule["unit"],
                "met":        met,
                "star":       st,
                "star_label": _STAR_LABEL.get(st, "—"),
            })

        # 優先攻略：未達標中星等最高（最接近門檻）
        unmet = [c for c in checks if c["met"] is False]
        priority = max(unmet, key=lambda c: c["star"], default=None)

        if met_count >= 1:
            summary = {"label": f"已達陣 {met_count}/{len(indicators)} 項",
                       "color": "green", "icon": "🏆"}
        elif priority:
            summary = {"label": f"尚未首勝，最易攻略：{priority['name']}",
                       "color": "amber", "icon": "🎯"}
        else:
            summary = {"label": "資料不足", "color": "gray", "icon": "—"}

        # ── 區塊 4：健保用藥防呆（先算，順便得知當次是否有 DM 藥）──
        drug_safety = _drug_safety(pid, labs, lab_counts)
        has_dm_drug = len(drug_safety.get("current_meds", [])) > 0

        # ── 區塊 2：可申報項目提示 ───────────────────────────
        claims = _claims_status(pid, pattern, lab_counts, has_dm_drug)

        return {
            "pid":     pid,
            "hba1c":   hba1c,
            "plan888": {
                "pattern":     pattern,
                "checks":      checks,
                "met_count":   met_count,
                "total":       len(indicators),
                "priority":    (priority["indicator"] if priority else None),
                "summary":     summary,
            },
            "claims":       claims,
            "drug_safety":  drug_safety,
        }

    except Exception as e:
        return {"pid": pid, "error": str(e), "hba1c": None, "plan888": None}
