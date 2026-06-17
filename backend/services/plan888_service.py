"""
888 戰略指揮中心業務邏輯
對應 Streamlit 版 app_888_manager.py
"""
import json
import os
import sqlite3
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Optional

from core.config import (
    ACTIVE_FM_DIR, ACTIVE_TRIAGE_JSON,
    TRACKING_DIR, DIGITAL_DB, IHEAL_SECRETS,
    CO01M_DB, CORE_DB, GEMINI_API_KEY,
)
from services.family_med_service import (
    get_diary, save_diary, _diary_path,
    send_push, _load_drug_master, _DRUG_MASTER,
    _get_medications_analyzed, _load_guidelines,
)

TRIAGE_DKD_JSON    = os.path.join(ACTIVE_FM_DIR, "dkd_888_triage_list.json")
STRATEGY_0TO1      = "/Users/cometmacmini/clinic_research/FM_115/strategy_888_0to1.py"
STRATEGY_DKD       = "/Users/cometmacmini/clinic_research/115_FM/strategy_dkd_triage.py"
SYNC_MAX_AGE       = timedelta(days=7)
_triage_sync_running = False


def _triage_last_modified() -> datetime | None:
    """取兩個 triage JSON 中較舊的那個，決定是否需要重跑"""
    from core.config import ACTIVE_TRIAGE_JSON
    paths = [ACTIVE_TRIAGE_JSON, TRIAGE_DKD_JSON]
    mtimes = [datetime.fromtimestamp(os.path.getmtime(p)) for p in paths if os.path.exists(p)]
    return min(mtimes) if mtimes else None


def _run_triage_background():
    global _triage_sync_running
    import sys
    try:
        for script in [STRATEGY_0TO1, STRATEGY_DKD]:
            if os.path.exists(script):
                r = subprocess.run(["python3", script], capture_output=True, text=True, timeout=180)
                if r.returncode != 0:
                    print(f"[888-triage] ERROR {script}: {r.stderr[-300:]}", file=sys.stderr)
    except Exception as e:
        print(f"[888-triage] 例外：{e}", file=sys.stderr)
    finally:
        _triage_sync_running = False


def check_and_trigger_triage_sync() -> dict:
    global _triage_sync_running
    last_mod = _triage_last_modified()
    now = datetime.now()
    if last_mod is None:
        return {"last_sync": None, "days_old": None, "syncing": _triage_sync_running}
    days_old = (now - last_mod).days
    triggered = False
    if days_old >= 7 and not _triage_sync_running:
        _triage_sync_running = True
        threading.Thread(target=_run_triage_background, daemon=True).start()
        triggered = True
    return {
        "last_sync": last_mod.strftime("%Y-%m-%d %H:%M"),
        "days_old":  days_old,
        "syncing":   _triage_sync_running or triggered,
    }


# ==========================================
# 讀取名冊 JSON
# ==========================================
def _load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_members_json() -> list[dict]:
    from core.config import ACTIVE_MEMBERS_DB
    if not os.path.exists(ACTIVE_MEMBERS_DB):
        return []
    with open(ACTIVE_MEMBERS_DB, encoding="utf-8") as f:
        return json.load(f)


def _dob_map() -> dict[str, str]:
    """pid → ROC 生日字串（for diary filename）"""
    members = _load_members_json()
    result  = {}
    for m in members:
        pid  = m.get("病歷號", "")
        bday = m.get("生日", "")
        if pid and "-" in bday:
            parts = bday.split("-")
            if len(parts) == 3:
                try:
                    result[pid] = f"{int(parts[0])-1911:03d}{parts[1]}{parts[2]}"
                    continue
                except:
                    pass
        result[pid] = "未知生日"
    return result


# ==========================================
# 時間錨點：預計藥物耗盡日
# ==========================================
def _calc_time_anchor(pid: str) -> dict:
    """
    從 FM_115_Core.db Medications 找最後一次 ≥28 天的處方，
    加 100 天推算耗盡日；回傳 dict。
    """
    result = {
        "last_rx_date":     None,
        "expected_refill":  None,
        "days_remaining":   None,
        "anchor_text":      "無法計算耗盡日（無慢箋記錄）",
    }
    if not os.path.exists(CORE_DB):
        return result
    try:
        conn = sqlite3.connect(CORE_DB)
        row  = conn.execute(
            "SELECT HDATE FROM Medications WHERE PID=? AND DAYS>=28 "
            "ORDER BY HDATE DESC LIMIT 1",
            (pid,)
        ).fetchone()
        conn.close()
        if not row:
            return result

        # ROC 民國日期 → 西元
        hdate = str(row[0]).strip().zfill(7)
        g_year = int(hdate[:3]) + 1911
        g_date = f"{g_year}-{hdate[3:5]}-{hdate[5:7]}"
        rx_date  = datetime.strptime(g_date, "%Y-%m-%d").date()
        exp_date = rx_date + timedelta(days=100)
        today    = datetime.now().date()
        remaining = (exp_date - today).days

        result.update({
            "last_rx_date":    g_date,
            "expected_refill": exp_date.strftime("%Y-%m-%d"),
            "days_remaining":  remaining,
            "anchor_text": (
                f"預計 {exp_date.strftime('%Y-%m-%d')} 耗盡（還有 {remaining} 天）"
                if remaining >= 0 else
                f"⚠️ 已逾期 {abs(remaining)} 天！（預計 {exp_date.strftime('%Y-%m-%d')} 耗盡）"
            ),
        })
    except:
        pass
    return result


# ==========================================
# 取得 triage 名單
# ==========================================
def get_triage_list(mode: str) -> list[dict]:
    """
    mode: 'DM' | 'CKD' | 'DKD' | 'DKD2to3'
    回傳每位病患的資料 dict（含時間錨點、日誌狀態、攻略難度）
    """
    dob  = _dob_map()
    rows = []

    if mode == "DKD2to3":
        data = _load_json(TRIAGE_DKD_JSON)
        for key, patients in data.items():
            if "最後一哩路" not in key:
                continue
            for pt in patients:
                pt["🎯 攻略難度"] = "差 " + key.split("_只差_")[1].split(" ")[0] if "_只差_" in key else key
                rows.append(pt)
    else:
        data   = _load_json(ACTIVE_TRIAGE_JSON)
        suffix = {"DM": "一", "CKD": "二", "DKD": "三"}.get(mode, "一")
        cat    = f"{mode}_樣態{suffix}"
        if cat in data:
            for star_key, patients in data[cat].items():
                if isinstance(patients, list):
                    for pt in patients:
                        pt["🎯 攻略難度"] = star_key
                        rows.append(pt)

    # 補充時間錨點、日誌狀態
    _load_drug_master()
    for pt in rows:
        pid = pt.get("病歷號", "")
        roc_dob = dob.get(pid, "未知生日")
        anchor  = _calc_time_anchor(pid)
        diary_file = os.path.join(TRACKING_DIR, f"{pid}_{roc_dob}_diary.md")

        pt["時間錨點"]    = anchor["anchor_text"]
        pt["預計耗盡日"]  = anchor["expected_refill"]
        pt["剩餘天數"]    = anchor["days_remaining"]
        pt["有日誌"]     = os.path.exists(diary_file)
        pt["roc_dob"]   = roc_dob

        # 從日誌撈最後一次推播草稿
        draft = ""
        if pt["有日誌"]:
            try:
                content = open(diary_file, encoding="utf-8").read()
                if "【推播草稿】" in content:
                    draft = content.split("【推播草稿】")[-1].split("---")[0].strip()
            except:
                pass
        pt["推播草稿"] = draft

    # NaN → None（JSON 不支援 float('nan')）
    import math
    def clean(v):
        if isinstance(v, float) and math.isnan(v): return None
        return v

    for pt in rows:
        for k in list(pt.keys()):
            pt[k] = clean(pt[k])

    return rows


# ==========================================
# 888 Betty 分析（含時間錨點）
# ==========================================
BETTY_SYSTEM = """你是凱程診所的「115 家醫 888 專案經理」。進行個案滾動式管理。
輸出格式：
### 💡 戰略洞察
（第一句話必須破題時間狀態，例如：「報告院長，預計 YYYY-MM-DD 耗盡，距離還有 X 天 / 已逾期 X 天。」）
### 📢 具體行動建議
（3-5點）
【推播草稿】
（100-150字LINE訊息，含Emoji，若即將斷藥語氣帶緊迫感）"""


def analyze_patient_888(pid: str, pt: dict) -> dict:
    """
    對單一 888 名單病患執行 Betty 分析，
    結果寫入 diary，回傳分析文字與草稿。
    """
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

        diary     = get_diary(pid)
        diary_bg  = diary["content"][-2000:] if diary["content"] else "（首次分析）"
        meds_data = _get_medications_analyzed(pid)
        tags      = pt.get("計畫類別", [])
        guidelines = _load_guidelines(tags)

        # Visit cycle from Core DB
        visit_cycle = "未知"
        if os.path.exists(CORE_DB):
            try:
                conn = sqlite3.connect(CORE_DB)
                row  = conn.execute("SELECT Visit_Cycle FROM Patients WHERE PID=?", (pid,)).fetchone()
                if row: visit_cycle = row[0]
                conn.close()
            except: pass

        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        name  = pt.get("姓名", "病患")

        prompt = f"""病患：{name}，病歷號：{pid}，回診週期：{visit_cycle}
【時間錨點】{pt.get('時間錨點', '未知')}（今日：{datetime.now().strftime('%Y-%m-%d')}）
數值：HbA1c={pt.get('HbA1c','未測')}（趨勢:{pt.get('HbA1c_趨勢','無')}），LDL={pt.get('LDL','未測')}（趨勢:{pt.get('LDL_趨勢','無')}），UACR={pt.get('UACR','未測')}（趨勢:{pt.get('UACR_趨勢','無')}）
攻略難度：{pt.get('🎯 攻略難度', '未知')}
【用藥分析】{meds_data['summary']}
【歷史日誌背景】{diary_bg}
{'【臨床指引】' + guidelines[:2000] if guidelines else ''}"""

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite-preview-06-17",
            config={"system_instruction": BETTY_SYSTEM},
            contents=prompt,
        )
        text = response.text

        # 萃取推播草稿
        draft = ""
        if "【推播草稿】" in text:
            draft = text.split("【推播草稿】")[-1].split("---")[0].strip()

        # 寫入 diary
        dob_map  = _dob_map()
        roc_dob  = dob_map.get(pid, "未知生日")
        safe_name = name[0] + "ＯＯ" if len(name) >= 2 else name
        diary_path = os.path.join(TRACKING_DIR, f"{pid}_{roc_dob}_diary.md")
        is_new     = not os.path.exists(diary_path)

        entry = f"\n\n## 🗓️ [{today}] 🤖 貝蒂888戰略分析\n"
        entry += f"- **當時數值**：HbA1c {pt.get('HbA1c')}, LDL {pt.get('LDL')}, UACR {pt.get('UACR')}\n"
        entry += f"- **⏰ 預計回診追蹤日**：{pt.get('預計耗盡日', '未知')}\n"
        entry += text.replace(name, safe_name) + "\n---\n"

        with open(diary_path, "a", encoding="utf-8") as f:
            if is_new:
                f.write(f"# 🏥 凱程診所個案追蹤檔\n- **病歷號**：{pid}\n- **生日**：{roc_dob}\n- **個案**：{safe_name}\n")
            f.write(entry)

        return {"ok": True, "text": text, "draft": draft, "analyzed_at": today}
    except Exception as e:
        return {"ok": False, "error": str(e), "text": "", "draft": ""}


def batch_analyze_888(pids_pts: list[dict]) -> dict:
    """批次分析，傳入 [{pid, ...pt}] 列表"""
    done, failed, drafts = [], [], {}
    for item in pids_pts:
        pid = item.get("病歷號", "")
        res = analyze_patient_888(pid, item)
        if res["ok"]:
            done.append(pid)
            drafts[pid] = res["draft"]
        else:
            failed.append(f"{pid}({res.get('error','')})")
    return {"done": len(done), "failed": failed, "drafts": drafts}
