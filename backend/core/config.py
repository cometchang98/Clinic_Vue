"""
後端設定：統一從 clinic_research/shared_paths.py 讀取路徑，
避免重複定義。
"""
import sys
sys.path.insert(0, "/Users/cometmacmini/clinic_research")
from shared_paths import (
    FM_114_DIR, FM_114_MEMBERS, FM_114_TRIAGE,
    FM_115_DIR, FM_115_MEMBERS, FM_115_TRIAGE,
    TRACKING_DIR, DIGITAL_DB, IHEAL_SECRETS,
    CO01M_DB, LAB_DICT, VACCINE_REPORT, DM_AUDIT_REPORT,
)
import os

# 目前使用哪一年的名冊（115年名單公告後改 FM_115_MEMBERS）
ACTIVE_MEMBERS_DB = FM_114_MEMBERS
ACTIVE_TRIAGE_JSON = FM_114_TRIAGE
ACTIVE_FM_DIR = FM_114_DIR

# FM_115_Core.db（用藥歷史、Labs）
CORE_DB = os.path.join(FM_114_DIR, "data", "FM_115_Core.db")

# Gemini API key（優先讀環境變數，fallback 到硬編碼）
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyAV52T2hmYxI8xrbOjh1AaknyVckGR1htA")
