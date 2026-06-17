"""
iHeal 愛管家 API 共用服務 (LINE + APP FCM 雙軌推播)
"""
import json, sqlite3, requests
from datetime import datetime
from core.config import DIGITAL_DB, IHEAL_SECRETS, CO01M_DB


def _get_token(m_type: str):
    with open(IHEAL_SECRETS) as f:
        s = json.load(f)
    mod_key = s.get("MOD_KEY_APP") if m_type == "fcm" else s.get("MOD_KEY_LINE")
    if not mod_key:
        raise ValueError(f"找不到 {m_type} 的金鑰")
    r = requests.post(
        f"{s['BASE_URL']}/External/auth",
        headers={"X-Clinic-ID": s["CLINIC_ID"], "X-Mod-Key": mod_key},
    )
    res = r.json()
    if not res.get("status"):
        raise RuntimeError(res.get("error", "auth failed"))
    return res["data"], s["CLINIC_ID"], s["BASE_URL"]


def send_push(m_type: str, target_id: str, content: str) -> dict:
    """發送推播。回傳 {ok, error}"""
    try:
        token, cid, base_url = _get_token(m_type)
        url = f"{base_url}/{'fcm' if m_type=='fcm' else 'line'}_service/message"
        payload = {
            "cid": cid,
            "ide": target_id,
            ("content" if m_type == "fcm" else "1content"): content,
        }
        res = requests.post(url, headers={"Authorization": f"Bearer {token}"}, data=payload).json()
        return {"ok": bool(res.get("status")), "error": res.get("error", "")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def log_push(pid: str, campaign: str, push_type: str, content: str):
    """存入 kaicheng_digital.db marketing_push_logs"""
    conn = sqlite3.connect(DIGITAL_DB)
    try:
        conn.execute("""
            INSERT INTO marketing_push_logs (pid, campaign_name, push_type, push_content, sent_at)
            VALUES (?, ?, ?, ?, ?)
        """, (pid, campaign, push_type, content, datetime.now().isoformat()))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_sent_pids() -> set:
    """回傳所有已處理過的 PID 集合"""
    conn = sqlite3.connect(DIGITAL_DB)
    try:
        rows = conn.execute("SELECT DISTINCT pid FROM marketing_push_logs").fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()
    finally:
        conn.close()


def lookup_patients(pids: list[str]) -> list[dict]:
    """從 CO01M.db 查詢病患姓名與身分證"""
    if not pids:
        return []
    placeholders = ",".join(["?"] * len(pids))
    conn = sqlite3.connect(CO01M_DB)
    try:
        rows = conn.execute(
            f"""SELECT TRIM(KCSTMR), TRIM(MNAME), TRIM(MPERSONID)
                FROM CO01M WHERE TRIM(KCSTMR) IN ({placeholders})
                OR UPPER(TRIM(MPERSONID)) IN ({placeholders})""",
            pids * 2,
        ).fetchall()
        return [{"pid": r[0].zfill(7), "name": r[1], "midno": r[2]} for r in rows]
    except Exception:
        return []
    finally:
        conn.close()
