"""
凱程診所 Vue 後端 — FastAPI 主程式
啟動：uvicorn main:app --reload --port 8000
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.family_med       import router as family_med_router
from routers.plan888          import router as plan888_router
from routers.metabolic_recall import router as metabolic_recall_router
from routers.marketing        import router as marketing_router
from routers.consultation     import router as consultation_router
from routers.data_mining      import router as data_mining_router
from routers.nhi_audit        import router as nhi_audit_router
from routers.insulin_tracking import router as insulin_tracking_router
from routers.schedule         import router as schedule_router
from routers.dm_care          import router as dm_care_router
from routers.dm_followup      import router as dm_followup_router
from routers.educator         import router as educator_router

app = FastAPI(
    title="凱程診所戰情室 API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://100.116.84.3:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(family_med_router)
app.include_router(plan888_router)
app.include_router(metabolic_recall_router)
app.include_router(marketing_router)
app.include_router(consultation_router)
app.include_router(data_mining_router)
app.include_router(nhi_audit_router)
app.include_router(insulin_tracking_router)
app.include_router(schedule_router)
app.include_router(dm_care_router)
app.include_router(dm_followup_router)
app.include_router(educator_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "凱程診所戰情室 v2.0"}
