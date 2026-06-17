"""
/api/marketing/*  營運發想與群發測試大本營
"""
from fastapi import APIRouter
from pydantic import BaseModel

from services.iheal_service import send_push, log_push, lookup_patients
from services.gemini_service import ask_gemini

router = APIRouter(prefix="/api/marketing", tags=["營運發想"])


class ChatBody(BaseModel):
    history: list[dict]   # [{role, content}, ...]
    message: str

@router.post("/betty-chat")
def betty_chat(body: ChatBody):
    ctx = "\n".join([f"{m['role']}: {m['content']}" for m in body.history[-4:]])
    prompt = f"你是凱程診所張院長的行銷衛教副手貝蒂。請針對想法給予具體活動建議。目前對話：\n{ctx}\nuser: {body.message}"
    return {"reply": ask_gemini(prompt)}


class WriteScriptBody(BaseModel):
    context: str   # 最後一段討論內容

@router.post("/write-script")
def write_script(body: WriteScriptBody):
    prompt = f"""
請根據這段討論：『{body.context}』幫院長寫一則 LINE 推播。
1. 100~150字，溫暖親切Emoji。
2. 結尾加上強烈行動呼籲：「我們非常關心您的健康狀況，提醒您以下事項：請在家量測近期的血壓、體重與腰圍並回傳紀錄給我們，以及記得空腹回診抽血喔！」
3. 開頭務必使用變數「{{姓名}}」！例如：『親愛的{{姓名}}您好呀！...』
4. ⚠️絕對不要寫出「提醒長輩」等字眼。
"""
    return {"text": ask_gemini(prompt)}


class LookupBody(BaseModel):
    raw: str   # 換行/空白/逗號分隔的病歷號或身分證

@router.post("/lookup-patients")
def lookup(body: LookupBody):
    import re
    tokens = [t.strip().upper() for t in re.split(r"[\n,\s\t]+", body.raw) if t.strip()]
    patients = lookup_patients(tokens)
    return {"patients": patients}


class BulkSendBody(BaseModel):
    patients: list[dict]   # [{pid, name, midno}]
    content: str
    m_type: str = "line"   # "line" | "fcm"
    campaign: str = "企劃群發測試"

@router.post("/bulk-send")
def bulk_send(body: BulkSendBody):
    results = []
    for p in body.patients:
        pid   = p.get("pid", "")
        name  = p.get("name", "")
        midno = p.get("midno", "")
        msg   = body.content.replace("{姓名}", name)
        target = midno or pid
        r = send_push(body.m_type, target, msg)
        log_content = f"{msg}\n\n[{'假性錯誤: ' + r['error'] if not r['ok'] else '成功'}]"
        log_push(pid, body.campaign, body.m_type, log_content)
        results.append({"pid": pid, "name": name, **r})
    return {"results": results}
