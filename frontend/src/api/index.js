import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// ==========================================
// 家醫計畫 API
// ==========================================
export const familyMedApi = {
  // 取得會員名冊（含燈號＆獎金計算）
  getMembers(params = {}) {
    return http.get('/family-med/members', { params })
  },

  // 取得單一會員病歷日誌
  getDiary(pid) {
    return http.get(`/family-med/diary/${pid}`)
  },

  // 儲存病歷日誌
  saveDiary(pid, content) {
    return http.put(`/family-med/diary/${pid}`, { content })
  },

  // AI 滾動式分析（含舊日誌＋用藥）
  generateDraft(pid, context) {
    return http.post(`/family-med/draft/${pid}`, context)
  },

  // 發送推播（LINE + APP 雙軌）
  sendPush(pid, message, campaign) {
    return http.post(`/family-med/push/${pid}`, { message, campaign })
  },

  // 批次 AI 分析
  batchAnalyze(pids) {
    return http.post('/family-med/batch-analyze', { pids })
  },

  // 取得獎金歷史趨勢
  getBonusHistory() {
    return http.get('/family-med/bonus-history')
  },

  // 取得品質警報（紅黃燈未達標）
  getAlerts() {
    return http.get('/family-med/alerts')
  },
}

// ==========================================
// 888 攻略計畫 API
// ==========================================
export const plan888Api = {
  getTriage(mode)              { return http.get('/plan888/triage', { params: { mode } }) },
  analyze(pid, pt)             { return http.post(`/plan888/analyze/${pid}`, { pt }) },
  batchAnalyze(patients)       { return http.post('/plan888/batch-analyze', { patients }, { timeout: 120000 }) },
  push(pid, message, campaign) { return http.post(`/plan888/push/${pid}`, { message, campaign }) },
  getDiary(pid)                { return http.get(`/plan888/diary/${pid}`) },
  saveDiary(pid, content)      { return http.put(`/plan888/diary/${pid}`, { content }) },
}
