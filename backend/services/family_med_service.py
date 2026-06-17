"""
家醫個管業務邏輯
從 Streamlit 版本提煉出來的純 Python 函式，不依賴 st.*
"""
import json
import os
import re
import sqlite3
import subprocess
import threading
import requests
from datetime import datetime, timedelta
from functools import lru_cache

from core.config import (
    ACTIVE_MEMBERS_DB, ACTIVE_TRIAGE_JSON, ACTIVE_FM_DIR,
    TRACKING_DIR, DIGITAL_DB, IHEAL_SECRETS, CO01M_DB,
    GEMINI_API_KEY, CORE_DB,
)

# ==========================================
# 自動同步：member_sync_engine.py
# ==========================================
SYNC_ENGINE  = "/Users/cometmacmini/clinic_research/FM_115/member_sync_engine.py"
SYNC_MAX_AGE = timedelta(days=7)   # 超過 7 天自動觸發
_sync_running = False              # 防止重複觸發


def _members_last_modified() -> datetime | None:
    if os.path.exists(ACTIVE_MEMBERS_DB):
        return datetime.fromtimestamp(os.path.getmtime(ACTIVE_MEMBERS_DB))
    return None


def _run_sync_background():
    """在獨立 thread 跑 member_sync_engine.py，跑完寫 log"""
    global _sync_running
    try:
        result = subprocess.run(
            ["python3", SYNC_ENGINE],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            import sys
            print(f"[member_sync] ERROR: {result.stderr[-500:]}", file=sys.stderr)
        else:
            print(f"[member_sync] 完成：{result.stdout[-200:]}")
    except Exception as e:
        import sys
        print(f"[member_sync] 例外：{e}", file=sys.stderr)
    finally:
        _sync_running = False


def check_and_trigger_sync() -> dict:
    """
    回傳 sync 狀態資訊，若超過 7 天且未在跑則背景觸發。
    回傳：{last_sync, days_old, syncing}
    """
    global _sync_running
    last_mod = _members_last_modified()
    now = datetime.now()

    if last_mod is None:
        return {"last_sync": None, "days_old": None, "syncing": _sync_running}

    days_old = (now - last_mod).days
    triggered = False

    if days_old >= 7 and not _sync_running and os.path.exists(SYNC_ENGINE):
        _sync_running = True
        t = threading.Thread(target=_run_sync_background, daemon=True)
        t.start()
        triggered = True

    return {
        "last_sync":  last_mod.strftime("%Y-%m-%d %H:%M"),
        "days_old":   days_old,
        "syncing":    _sync_running or triggered,
    }


# ==========================================
# 獎金計算（單一真實來源）
# ==========================================
def calculate_reward(tags: list, a1c, ldl, uacr) -> tuple[str, int]:
    """回傳 (燈號文字, 獎金元)"""
    def met(val, target):
        try:    return val is not None and float(val) < target
        except: return False

    if "糖尿病合併腎病變 (DKD)" in tags:
        score = sum([met(a1c, 7.0), met(ldl, 100), met(uacr, 30)])
        label = {3: "🟢 綠燈 (3項)", 2: "🟡 黃燈 (2項)",
                 1: "🟠 橘燈 (1項)", 0: "🔴 紅燈 (0項/缺值)"}[score]
        bonus = {3: 900, 2: 600, 1: 500, 0: 0}[score]
        return label, bonus

    if "糖尿病 (DM)" in tags:
        score = sum([met(a1c, 7.0), met(ldl, 100)])
        label = {2: "🟢 綠燈 (2項)", 1: "🟡 黃燈 (1項)", 0: "🔴 紅燈 (0項/缺值)"}[score]
        bonus = {2: 600, 1: 500, 0: 0}[score]
        return label, bonus

    if "初期慢性腎病 (CKD)" in tags:
        score = sum([met(ldl, 130), met(uacr, 30)])
        label = {2: "🟢 綠燈 (2項)", 1: "🟡 黃燈 (1項)", 0: "🔴 紅燈 (0項/缺值)"}[score]
        bonus = {2: 500, 1: 300, 0: 0}[score]
        return label, bonus

    return "⚪ 無特殊指標", 0


def _extract_latest(history: dict, key: str):
    recs = history.get(key, [])
    return recs[0].get("num_val") if recs else None


# ==========================================
# 會員名冊
# ==========================================
def get_members(search: str = "", tags: list[str] | None = None) -> list[dict]:
    if not os.path.exists(ACTIVE_MEMBERS_DB):
        return []

    with open(ACTIVE_MEMBERS_DB, "r", encoding="utf-8") as f:
        members = json.load(f)

    result = []
    for m in members:
        # 搜尋過濾
        if search:
            kw = search.upper()
            if kw not in m.get("姓名", "") and kw not in m.get("身分證", "").upper():
                continue
        # 標籤過濾
        if tags:
            if not any(t in m.get("計畫類別", []) for t in tags):
                continue

        hist = m.get("指標歷史", {})
        a1c  = _extract_latest(hist, "HbA1c")
        ldl  = _extract_latest(hist, "LDL-C")
        uacr = _extract_latest(hist, "UACR")

        light, bonus = calculate_reward(m.get("計畫類別", []), a1c, ldl, uacr)

        # 取最近一次的 date 做趨勢（簡化版）
        def trend(key):
            recs = hist.get(key, [])
            if len(recs) < 2: return "-"
            delta = round(recs[0]["num_val"] - recs[1]["num_val"], 2)
            return f"🔺 +{delta}" if delta > 0 else (f"🟢 {delta}" if delta < 0 else "➖ 持平")

        result.append({
            **{k: m[k] for k in ("身分證","生日","姓名","電話","計畫類別","收案日期","病歷號","最後診視日")
               if k in m},
            "HbA1c":    a1c,
            "HbA1c趨勢": trend("HbA1c"),
            "LDL":      ldl,
            "LDL趨勢":  trend("LDL-C"),
            "UACR":     uacr,
            "UACR趨勢": trend("UACR"),
            "品質燈號":  light,
            "預估獎金":  bonus,
            "有日誌":   _diary_exists(m.get("病歷號", "")),
        })

    return result


# ==========================================
# 病歷日誌
# ==========================================
def _diary_path(pid: str) -> str | None:
    if not os.path.exists(TRACKING_DIR):
        return None
    for fname in os.listdir(TRACKING_DIR):
        if fname.startswith(f"{pid}_") and fname.endswith("_diary.md"):
            return os.path.join(TRACKING_DIR, fname)
    return None


def _diary_exists(pid: str) -> bool:
    return _diary_path(pid) is not None


def get_diary(pid: str) -> dict:
    path = _diary_path(pid)
    if not path:
        return {"content": "", "exists": False}
    with open(path, "r", encoding="utf-8") as f:
        return {"content": f.read(), "exists": True, "path": path}


def save_diary(pid: str, content: str) -> dict:
    path = _diary_path(pid)
    if not path:
        # 建新檔（需要生日才能命名，先用 unknown）
        path = os.path.join(TRACKING_DIR, f"{pid}_未知生日_diary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "path": path}


# ==========================================
# 獎金歷史
# ==========================================
def get_bonus_history() -> list[dict]:
    history_csv = os.path.join(ACTIVE_FM_DIR, "data", "bonus_history.csv")
    if not os.path.exists(history_csv):
        return []
    import csv
    with open(history_csv, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ==========================================
# 藥品主檔 ATC 對照表（模組載入時建立一次）
# ==========================================
_DRUG_MASTER: dict = {}   # kdrug → {name, atc}

def _load_drug_master():
    global _DRUG_MASTER
    if _DRUG_MASTER:
        return
    drug_file = "/Users/cometmacmini/clinic_research/data_backup/R13530藥材資料檔列印.csv"
    if not os.path.exists(drug_file):
        return
    import csv
    try:
        with open(drug_file, encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()
        # 第 4 行（index 3）是真正的 header
        header = lines[3].strip().split(",")
        kdrug_idx = header.index("kdrug") if "kdrug" in header else None
        name_idx  = header.index("藥名")  if "藥名"  in header else 3
        # datc 欄位是第 137 欄（從解析結果確認）
        atc_idx   = next((i for i,h in enumerate(header) if h.strip().lower() == "datc"), None)
        if kdrug_idx is None or atc_idx is None:
            return
        reader = csv.reader(lines[4:])
        for row in reader:
            if len(row) <= max(kdrug_idx, atc_idx):
                continue
            kdrug = row[kdrug_idx].strip()
            atc   = row[atc_idx].strip()
            name  = row[name_idx].strip() if len(row) > name_idx else ""
            if kdrug and atc:
                _DRUG_MASTER[kdrug] = {"name": name, "atc": atc}
    except Exception:
        pass

_load_drug_master()

# ATC 分類設定
_CHRONIC_ATC_PREFIXES = [
    ("A10", "糖尿病用藥"),
    ("C02", "降血壓藥"),
    ("C03", "利尿劑"),
    ("C07", "乙型阻斷劑"),
    ("C08", "鈣離子阻斷劑"),
    ("C09", "ACE抑制劑/ARB"),
    ("C10", "降血脂藥/Statin"),
]
_NEPHROTOXIC_ATC = [
    ("M01A", "NSAIDs（腎毒性風險）"),
    ("M01AB", "NSAIDs-吲哚類（腎毒性）"),
    ("M01AE", "NSAIDs-丙酸類（腎毒性）"),
    ("A02B", "氫離子幫浦阻斷劑(PPI)"),
]
_INTERACTION_PAIRS = [
    # (atc_prefix_a, atc_prefix_b, 警告訊息)
    ("M01A", "C09", "⚠️ NSAIDs + ACE/ARB：腎毒性三重奏風險（若同時用利尿劑更危險）"),
    ("M01A", "C03", "⚠️ NSAIDs + 利尿劑：血壓控制可能下降，腎灌流風險"),
    ("C10AA", "C07", "ℹ️ Statin + Beta-blocker：注意橫紋肌溶解風險（運動後肌痛）"),
    ("C03A", "C09", "⚠️ 保鉀利尿劑 + ACE/ARB：高血鉀風險"),
]

# ==========================================
# 用藥分析（查最近 50 筆，依 ATC 分類篩選）
# ==========================================
def _get_medications_analyzed(pid: str) -> dict:
    """回傳分類後的用藥摘要與交互作用警示"""
    result = {
        "chronic":      [],   # 三高慢性病用藥
        "nephrotoxic":  [],   # 腎毒性/腎風險藥物
        "interactions": [],   # 交互作用警示
        "summary":      "無相關用藥記錄",
    }
    if not os.path.exists(CORE_DB):
        return result
    try:
        conn  = sqlite3.connect(CORE_DB)
        rows  = conn.execute(
            "SELECT HDATE, DRUG_CODE, DAYS FROM Medications "
            "WHERE PID=? ORDER BY HDATE DESC LIMIT 50",
            (pid,)
        ).fetchall()
        conn.close()
    except:
        return result

    if not rows:
        return result

    seen_kdrug  = {}   # kdrug → {name, atc, date, days}
    for hdate, kdrug, days in rows:
        kdrug = kdrug.strip()
        if kdrug in seen_kdrug:
            continue   # 只取每種藥最新那筆
        info = _DRUG_MASTER.get(kdrug, {})
        atc  = info.get("atc", "")
        name = info.get("name", kdrug)
        seen_kdrug[kdrug] = {"name": name, "atc": atc, "date": hdate, "days": int(days or 0)}

    # 分類
    active_atc_list = []
    for kdrug, info in seen_kdrug.items():
        atc = info["atc"].upper()
        if not atc:
            continue
        active_atc_list.append(atc)
        label_added = False
        for prefix, category in _CHRONIC_ATC_PREFIXES:
            if atc.startswith(prefix):
                result["chronic"].append(f"{info['name']}（{category} / {atc}，{info['date']}）")
                label_added = True
                break
        if not label_added:
            for prefix, category in _NEPHROTOXIC_ATC:
                if atc.startswith(prefix):
                    result["nephrotoxic"].append(f"⚠️ {info['name']}（{category} / {atc}，{info['date']}）")
                    break

    # 交互作用檢核
    for atc_a, atc_b, warning in _INTERACTION_PAIRS:
        has_a = any(a.startswith(atc_a) for a in active_atc_list)
        has_b = any(a.startswith(atc_b) for a in active_atc_list)
        if has_a and has_b:
            result["interactions"].append(warning)

    # 組合摘要文字
    parts = []
    if result["chronic"]:
        parts.append("【三高慢性病用藥】\n" + "\n".join(f"  • {d}" for d in result["chronic"]))
    if result["nephrotoxic"]:
        parts.append("【腎毒性/腎風險藥物 ⚠️】\n" + "\n".join(f"  {d}" for d in result["nephrotoxic"]))
    if result["interactions"]:
        parts.append("【藥物交互作用警示】\n" + "\n".join(f"  {w}" for w in result["interactions"]))
    result["summary"] = "\n\n".join(parts) if parts else "近期無三高相關或腎毒性用藥記錄"
    return result


# ==========================================
# Library 指引載入（依病患 tags 選擇相關 md）
# ==========================================
_LIBRARY_DIR = "/Users/cometmacmini/clinic_research/library"

def _load_guidelines(tags: list) -> str:
    """根據計畫類別選擇相關指引，各取關鍵段落，總長控制在 3000 字內"""
    files = []
    has_dm  = any("糖尿病" in t for t in tags)
    has_ckd = any("腎病" in t or "CKD" in t for t in tags)
    has_dkd = any("DKD" in t or "腎病變" in t for t in tags)

    if has_dkd:
        files.append("dkd_care_guidelines.md")
    elif has_ckd:
        files.append("ckd_care_guildelines.md")
    elif has_dm:
        files.append("dm_care_guidelines.md")
    # 藥物交互作用指引對三高病患都適用
    files.append("門診常見高風險藥物交互作用指引.md")

    combined = []
    budget   = 3000
    for fname in files:
        path = os.path.join(_LIBRARY_DIR, fname)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        take = text[:budget]
        combined.append(f"=== {fname} ===\n{take}")
        budget -= len(take)
        if budget <= 0:
            break

    return "\n\n".join(combined) if combined else ""


# ==========================================
# Gemini AI 滾動式分析（舊日誌＋ATC篩選用藥＋指引 RAG）
# ==========================================
def generate_draft(pid: str, context: dict) -> dict:
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

        # 讀取完整舊日誌（背景，取最後 2000 字）
        diary     = get_diary(pid)
        diary_bg  = diary["content"][-2000:] if diary["content"] else "（首次分析，無歷史日誌）"
        has_diary = diary["exists"]

        # 分析用藥（ATC 篩選後的三高慢性病藥 + 腎毒性藥 + 交互作用警示）
        meds_data = _get_medications_analyzed(pid)

        tags  = context.get("計畫類別", [])
        name  = context.get("姓名", "病患")
        today = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 臨床指引 RAG
        guidelines = _load_guidelines(tags)

        def trend_text(key):
            t = context.get(f"{key}趨勢", "-") or "-"
            if "🔺" in t: return f"↑ 上升（{t.replace('🔺 ', '+')}）"
            if "🟢" in t: return f"↓ 下降（{t.replace('🟢 ', '')}）"
            return "持平"

        system_instruction = (
            "你是凱程診所的家醫個管師貝蒂（Betty）。\n"
            "任務：進行家醫888計畫滾動式個案分析，風格專業、有溫度、具體。\n"
            "⚠️ 若用藥出現腎毒性藥物或高風險交互作用，必須在「📢 具體行動建議」中明確提醒醫師。\n"
            "輸出固定格式：\n"
            "  💡 戰略洞察（200字內）\n"
            "  📢 具體行動建議（3-5點）\n"
            "  【推播草稿】（LINE訊息，稱呼姓名，100-150字，含Emoji，結尾提醒空腹回診抽血）"
        )

        prompt = f"""病患資料（分析時間：{today}）
姓名：{name}，病歷號：{pid}
計畫類別：{'、'.join(tags) or '未分類'}
品質燈號：{context.get('品質燈號', '未計算')}，預估獎金：{context.get('預估獎金', 0)} 元

【最新檢驗數值】
- HbA1c：{context.get('HbA1c', '未測')}（趨勢：{trend_text('HbA1c')}）
- LDL-C：{context.get('LDL',   '未測')}（趨勢：{trend_text('LDL')}）
- UACR：{context.get('UACR',  '未測')}（趨勢：{trend_text('UACR')}）

【用藥分析（近50筆，ATC篩選）】
{meds_data['summary']}

【歷史病歷日誌（背景參考）】
{diary_bg}

{'【臨床指引參考】' + chr(10) + guidelines if guidelines else ''}

請根據以上資料，輸出滾動式個案分析。"""

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite-preview-06-17",
            config={"system_instruction": system_instruction},
            contents=prompt,
        )

        return {
            "draft":           response.text,
            "analyzed_at":     today,
            "has_prior_diary": has_diary,
            "meds_chronic":    meds_data["chronic"],
            "meds_nephrotoxic": meds_data["nephrotoxic"],
            "meds_interactions": meds_data["interactions"],
        }
    except Exception as e:
        return {"draft": "", "error": str(e)}


# ==========================================
# iHeal 雙軌推播
# ==========================================
def _get_iheal_token(m_type: str):
    with open(IHEAL_SECRETS, "r") as f:
        s = json.load(f)
    mod_key = s.get("MOD_KEY_APP") if m_type == "fcm" else s.get("MOD_KEY_LINE")
    if not mod_key:
        raise ValueError(f"找不到 {m_type} 金鑰")
    r = requests.post(
        f"{s['BASE_URL']}/External/auth",
        headers={"X-Clinic-ID": s["CLINIC_ID"], "X-Mod-Key": mod_key},
    )
    res = r.json()
    if not res.get("status"):
        raise ValueError(res.get("error", "驗證失敗"))
    return res["data"], s["CLINIC_ID"], s["BASE_URL"]


def _lookup_midno(pid: str) -> str:
    """用病歷號查出身分證字號（iHeal 發送必備）"""
    if not os.path.exists(CO01M_DB):
        return ""
    try:
        conn = sqlite3.connect(CO01M_DB)
        row = conn.execute(
            "SELECT TRIM(MPERSONID) FROM CO01M WHERE TRIM(KCSTMR)=?", (pid,)
        ).fetchone()
        conn.close()
        return row[0] if row else ""
    except:
        return ""


def send_push(pid: str, message: str, campaign: str) -> dict:
    midno = _lookup_midno(pid)
    target = midno if midno else pid

    results = {}
    for ch in ("line", "fcm"):
        try:
            token, cid, base_url = _get_iheal_token(ch)
            url = f"{base_url}/{'fcm' if ch=='fcm' else 'line'}_service/message"
            payload = {
                "cid": cid,
                "ide": target,
                ("content" if ch == "fcm" else "1content"): message,
            }
            res = requests.post(
                url, headers={"Authorization": f"Bearer {token}"}, data=payload
            ).json()
            results[ch] = "成功" if res.get("status") else f"失敗({res.get('error','')})"
        except Exception as e:
            results[ch] = f"失敗({e})"

    # 寫入 digital DB
    _log_push(pid, campaign, message, results)

    return {
        "line_status": results.get("line", ""),
        "fcm_status":  results.get("fcm", ""),
        "ok": "成功" in results.get("line", "") or "成功" in results.get("fcm", ""),
    }


def _log_push(pid, campaign, content, results):
    try:
        conn = sqlite3.connect(DIGITAL_DB)
        conn.execute("""CREATE TABLE IF NOT EXISTS marketing_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pid TEXT, campaign_name TEXT, send_date TEXT,
            push_type TEXT, content TEXT)""")
        log_content = f"{content}\n\n[LINE:{results.get('line','')} | APP:{results.get('fcm','')}]"
        conn.execute(
            "INSERT INTO marketing_logs (pid,campaign_name,send_date,push_type,content) "
            "VALUES (?,?,datetime('now','localtime'),?,?)",
            (pid, campaign, "dual_shot", log_content),
        )
        conn.commit()
        conn.close()
    except:
        pass


# ==========================================
# 批次 AI 分析（寫入日誌）
# ==========================================
def batch_analyze(pids: list[str]) -> dict:
    members = get_members()
    pid_map  = {m["病歷號"]: m for m in members}
    done, failed = [], []

    for pid in pids:
        m = pid_map.get(pid)
        if not m:
            failed.append(pid)
            continue
        try:
            result = generate_draft(pid, m)
            draft  = result.get("draft", "")

            # 追加寫入日誌
            today = datetime.now().strftime("%Y-%m-%d %H:%M")
            path  = _diary_path(pid) or os.path.join(TRACKING_DIR, f"{pid}_未知生日_diary.md")
            entry = (
                f"\n\n## 🗓️ [{today}] 🤖 貝蒂批次分析\n"
                f"- HbA1c: {m.get('HbA1c','未知')}, LDL: {m.get('LDL','未知')}, UACR: {m.get('UACR','未知')}\n"
                f"{draft}\n---\n"
            )
            with open(path, "a", encoding="utf-8") as f:
                f.write(entry)
            done.append(pid)
        except Exception as e:
            failed.append(f"{pid}({e})")

    return {"done": len(done), "failed": failed}


# ==========================================
# 品質警報
# ==========================================
def get_alerts() -> dict:
    members = get_members()

    def alerts_for(filter_tag, checks, exclude_tag=None):
        out = []
        for m in members:
            tags = m.get("計畫類別", [])
            if filter_tag not in tags: continue
            if exclude_tag and exclude_tag in tags: continue
            reasons = []
            for c in checks:
                v = m.get(c["key"])
                if v is None:
                    reasons.append(f"缺 {c['key']}")
                elif float(v) >= c["target"]:
                    reasons.append(f"{c['key']}: {v}")
            if reasons:
                out.append({"pid": m["病歷號"], "name": m["姓名"], "reasons": reasons})
        return out

    return {
        "DM":  alerts_for("糖尿病 (DM)",
                           [{"key":"HbA1c","target":7.0},{"key":"LDL","target":100}],
                           exclude_tag="糖尿病合併腎病變 (DKD)"),
        "CKD": alerts_for("初期慢性腎病 (CKD)",
                           [{"key":"LDL","target":130},{"key":"UACR","target":30}],
                           exclude_tag="糖尿病合併腎病變 (DKD)"),
        "DKD": alerts_for("糖尿病合併腎病變 (DKD)",
                           [{"key":"HbA1c","target":7.0},{"key":"LDL","target":100},{"key":"UACR","target":30}]),
    }
