"""
/api/educator/*  M4 衛教師工作站
衛教產出畫面內嵌 educator_gas（iframe），這裡只負責：
把衛教完的 PDF / 圖片連結，用愛管家 send_push 推到病患 LINE + APP。
"""
from fastapi import APIRouter
from pydantic import BaseModel

from services.iheal_service import send_push, log_push

router = APIRouter(prefix="/api/educator", tags=["M4 衛教師工作站"])

# educator_gas 已部署的 web app exec 網址（給前端 iframe）
GAS_EXEC_URL = ("https://script.google.com/macros/s/"
                "AKfycbyBzbsBVlevDSfdV2Xndj6u2euoACQUENX4V-lwCUfA2NWgCUqMZ07_sNTBGu4hxHV-/exec")


@router.get("/gas-url")
def gas_url():
    return {"url": GAS_EXEC_URL}


class PushBody(BaseModel):
    pid: str
    target_id: str          # 身分證字號（愛管家 ide）
    pdf_url: str
    name: str = ""
    channels: list[str] = ["line", "fcm"]   # 預設雙軌
    message: str = ""       # 可自訂前導文字

@router.post("/push")
def push_education(body: PushBody):
    """把衛教單連結推給病患（LINE + APP 雙軌）"""
    if not body.target_id or not body.pdf_url:
        return {"ok": False, "error": "缺少身分證或 PDF 連結"}

    greeting = body.message.strip() or (
        f"{body.name}您好，這是您今天的專屬衛教單，請點開連結查看 🍎\n{body.pdf_url}"
    )
    if body.pdf_url not in greeting:
        greeting = f"{greeting}\n{body.pdf_url}"

    results = {}
    for ch in body.channels:
        r = send_push(ch, body.target_id, greeting)
        results[ch] = r
    ok = any(v.get("ok") for v in results.values())

    # 留紀錄
    try:
        log_push(body.pid, "衛教單推播", "+".join(body.channels), greeting)
    except Exception:
        pass

    return {"ok": ok, "results": results}
