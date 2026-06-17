<template>
  <div class="p-6 max-w-5xl mx-auto">
    <!-- Header -->
    <div class="flex items-start justify-between mb-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-800">🏃 代謝症候群防治計畫</h1>
        <p class="text-sm text-slate-500 mt-1">衛教師追蹤紀錄同步 → 院長審核申報 (P7501C / P7502C / P7503C)</p>
      </div>
      <div class="flex items-center gap-2">
        <a
          href="https://script.google.com/macros/s/AKfycbyBzbsBVlevDSfdV2Xndj6u2euoACQUENX4V-lwCUfA2NWgCUqMZ07_sNTBGu4hxHV-/exec"
          target="_blank"
          rel="noopener"
          class="flex items-center gap-1.5 px-3 py-2 bg-emerald-50 text-emerald-700 border border-emerald-200 text-sm font-medium rounded-lg hover:bg-emerald-100 transition-colors"
        >
          ☁️ 衛教師雲端版
        </a>
        <button
          @click="syncSheets"
          :disabled="syncing"
          class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          <span v-if="syncing" class="animate-spin">⏳</span>
          <span v-else>🔄</span>
          {{ syncing ? '同步中...' : '同步 Google Sheets' }}
        </button>
      </div>
    </div>

    <!-- 衛教師 GAS iframe 快覽 -->
    <div class="mb-5 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div class="flex items-center justify-between px-4 py-2.5 bg-emerald-50 border-b border-emerald-100">
        <span class="text-sm font-semibold text-emerald-800">☁️ 衛教師雲端版即時預覽</span>
        <div class="flex items-center gap-2">
          <button @click="showGas = !showGas" class="text-xs text-emerald-600 hover:text-emerald-800 underline">
            {{ showGas ? '收起' : '展開預覽' }}
          </button>
          <a href="https://script.google.com/macros/s/AKfycbyBzbsBVlevDSfdV2Xndj6u2euoACQUENX4V-lwCUfA2NWgCUqMZ07_sNTBGu4hxHV-/exec"
            target="_blank" class="text-xs text-emerald-600 hover:text-emerald-800 underline">↗ 獨立視窗開啟</a>
        </div>
      </div>
      <div v-if="showGas" class="relative">
        <iframe
          src="https://script.google.com/macros/s/AKfycbyBzbsBVlevDSfdV2Xndj6u2euoACQUENX4V-lwCUfA2NWgCUqMZ07_sNTBGu4hxHV-/exec"
          class="w-full border-0"
          style="height: 520px;"
          title="衛教師雲端大腦"
          allow="same-origin"
        />
      </div>
    </div>

    <!-- Sync info bar -->
    <div v-if="syncedAt" class="mb-4 text-xs text-slate-400 text-right">
      最後同步：{{ formatDateTime(syncedAt) }}
      ｜共 {{ patients.length }} 位追蹤中
    </div>

    <!-- Empty state -->
    <div v-if="!syncing && patients.length === 0" class="text-center py-20 text-slate-400">
      <div class="text-5xl mb-3">📋</div>
      <p class="text-lg font-medium">尚無追蹤資料</p>
      <p class="text-sm mt-1">點擊右上角「同步 Google Sheets」載入衛教師的最新追蹤記錄</p>
    </div>

    <!-- Patient cards -->
    <div class="space-y-4">
      <div
        v-for="pt in patients"
        :key="pt.pid"
        class="bg-white rounded-xl border shadow-sm overflow-hidden"
        :class="{
          'border-green-200': pt.contacted && !pt.approved,
          'border-red-100':   pt.failed && !pt.contacted,
          'border-slate-200': !pt.contacted && !pt.failed,
          'border-purple-200 opacity-70': pt.approved,
        }"
      >
        <!-- Card header -->
        <div class="flex items-center justify-between px-5 py-3 border-b"
          :class="{
            'bg-green-50':  pt.contacted && !pt.approved,
            'bg-red-50':    pt.failed && !pt.contacted,
            'bg-slate-50':  !pt.contacted && !pt.failed,
            'bg-purple-50': pt.approved,
          }"
        >
          <div class="flex items-center gap-3">
            <!-- Contact status badge -->
            <span v-if="pt.approved" class="text-xs font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">✅ 已申報</span>
            <span v-else-if="pt.contacted" class="text-xs font-bold px-2 py-0.5 rounded-full bg-green-100 text-green-700">🟢 已接通</span>
            <span v-else-if="pt.failed"    class="text-xs font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-600">🔴 未接通</span>
            <span v-else                   class="text-xs font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">⏳ 追蹤中</span>

            <span class="font-bold text-slate-800 text-lg">{{ pt.name || '未知個案' }}</span>
            <span class="text-sm text-slate-500">病歷 {{ pt.pid }}</span>
            <span v-if="pt.enrolled" class="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">已正式收案</span>
          </div>

          <div class="flex items-center gap-2 text-xs text-slate-400">
            <span>{{ pt.latest_type }}</span>
            <span>{{ formatDateTime(pt.latest_date) }}</span>
          </div>
        </div>

        <!-- Card body -->
        <div class="px-5 py-4">
          <!-- Latest educator note -->
          <div class="mb-4 p-3 bg-slate-50 rounded-lg text-sm text-slate-700 whitespace-pre-line leading-relaxed border-l-4 border-slate-300">
            <p class="text-xs font-semibold text-slate-400 mb-1">📋 衛教師最新追蹤記錄</p>
            {{ pt.latest_note || '（無備註）' }}
          </div>

          <!-- 病患回報生理數據（衛教師電訪記錄） -->
          <div v-if="reportedVitals(pt).length > 0" class="mb-4 p-3 bg-green-50 rounded-lg border-l-4 border-green-400">
            <p class="text-xs font-semibold text-green-700 mb-2">
              📞 病患回報生理數據
              <span class="font-normal text-green-600">（{{ reportedVitalsDate(pt) }} 衛教師記錄）</span>
            </p>
            <div class="flex flex-wrap gap-2">
              <div v-for="item in reportedVitals(pt)" :key="item.label"
                class="rounded-lg px-3 py-1.5 text-center bg-white border"
                :class="item.alert ? 'border-red-300' : 'border-green-200'"
              >
                <span class="text-xs text-slate-400">{{ item.label }}</span>
                <span class="text-sm font-bold ml-1.5" :class="item.alert ? 'text-red-600' : 'text-green-700'">
                  {{ item.value }}
                </span>
              </div>
            </div>
          </div>

          <!-- BQ Labs section -->
          <div class="mb-4">
            <div class="flex items-center gap-2 mb-2">
              <p class="text-xs font-semibold text-slate-500">🔬 BigQuery 近期生理數據</p>
              <button
                v-if="!pt._labsLoaded"
                @click="loadLabs(pt)"
                :disabled="pt._labsLoading"
                class="text-xs text-blue-600 hover:text-blue-800 underline"
              >
                {{ pt._labsLoading ? '載入中...' : '載入檢驗數值' }}
              </button>
            </div>

            <!-- Labs grid -->
            <div v-if="pt._labsLoaded" class="grid grid-cols-3 sm:grid-cols-6 gap-2">
              <div v-for="item in labItems(pt)" :key="item.key"
                class="rounded-lg p-2 text-center"
                :class="item.alert ? 'bg-red-50 border border-red-200' : 'bg-slate-50'"
              >
                <p class="text-xs text-slate-400 leading-tight">{{ item.label }}</p>
                <p class="text-sm font-bold mt-0.5" :class="item.alert ? 'text-red-600' : 'text-slate-700'">
                  {{ item.value }}
                </p>
                <p class="text-xs text-slate-400">{{ item.date }}</p>
              </div>
            </div>
          </div>

          <!-- Followup history toggle -->
          <button
            @click="pt._showHistory = !pt._showHistory"
            class="text-xs text-slate-400 hover:text-slate-600 underline mb-3"
          >
            {{ pt._showHistory ? '▲ 隱藏追蹤歷程' : `▼ 查看全部追蹤歷程 (共 ${pt.followups.length} 筆)` }}
          </button>

          <div v-if="pt._showHistory" class="space-y-2 mb-4">
            <div
              v-for="f in pt.followups"
              :key="f.id"
              class="flex gap-3 text-xs text-slate-600 p-2 rounded bg-slate-50"
            >
              <span class="text-slate-400 whitespace-nowrap">{{ f.date?.slice(0, 16) }}</span>
              <span class="px-1.5 py-0.5 rounded text-xs font-medium"
                :class="{
                  'bg-green-100 text-green-700': f.outcome === '接通',
                  'bg-red-100 text-red-600':     f.outcome?.includes('未接通') || f.outcome?.includes('失敗'),
                  'bg-blue-100 text-blue-700':   !f.outcome,
                }"
              >{{ f.type }}</span>
              <span v-if="f.outcome" class="font-medium">{{ f.outcome }}</span>
              <span v-if="followupVitalsStr(f)" class="px-1.5 py-0.5 rounded bg-green-100 text-green-700 font-medium whitespace-nowrap">
                {{ followupVitalsStr(f) }}
              </span>
              <span class="text-slate-500 truncate">{{ f.note }}</span>
            </div>
          </div>

          <!-- ── Decision zone ── -->
          <div v-if="!pt.approved" class="border-t pt-4">

            <!-- 未接通：鎖定不可申報 -->
            <div v-if="pt.failed && !pt.contacted" class="flex items-center gap-2 text-sm text-slate-500">
              <span>🔴 未接通，衛教師持續追蹤中</span>
            </div>

            <!-- 接通：申報決策區 -->
            <div v-else-if="pt.contacted">
              <p class="text-xs font-semibold text-slate-500 mb-2">⚕️ 院長申報決策</p>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="item in approvalCodes"
                  :key="item.code"
                  @click="openApproveModal(pt, item.code)"
                  class="px-3 py-1.5 text-sm font-bold rounded-lg border-2 transition-colors"
                  :class="item.cls"
                >
                  {{ item.code }}
                  <span class="font-normal text-xs ml-1">{{ item.label }}</span>
                </button>

                <button
                  @click="notApprove(pt)"
                  class="px-3 py-1.5 text-sm text-slate-500 rounded-lg border border-slate-200 hover:bg-slate-50"
                >
                  暫不申報
                </button>
              </div>
            </div>

          </div>

          <!-- Already approved -->
          <div v-else class="border-t pt-3 text-sm text-purple-600 font-medium">
            ✅ 已完成健保申報鎖定 — 隔天名單將自動從衛教師清單消失
          </div>

        </div>
      </div>
    </div>

    <!-- Approve confirm modal -->
    <div v-if="approveModal.open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      @click.self="approveModal.open = false"
    >
      <div class="bg-white rounded-2xl shadow-xl p-6 w-96 max-w-full">
        <h3 class="text-lg font-bold text-slate-800 mb-1">
          確認申報 {{ approveModal.code }}
          <span class="text-sm font-normal text-slate-500 ml-1">
            ({{ approvalCodes.find(c => c.code === approveModal.code)?.label }})
          </span>
        </h3>
        <p class="text-sm text-slate-500 mb-4">
          病患：<strong>{{ approveModal.pt?.name }}</strong>（{{ approveModal.pt?.pid }}）
        </p>

        <label class="block text-xs font-semibold text-slate-500 mb-1">備註（選填）</label>
        <textarea
          v-model="approveModal.note"
          rows="3"
          placeholder="例：電話接通，HbA1c 7.2%，血壓 138/86，符合追蹤條件"
          class="w-full border border-slate-200 rounded-lg p-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-green-300"
        />

        <div class="flex gap-2 mt-4">
          <button
            @click="confirmApprove"
            :disabled="approving"
            class="flex-1 py-2 bg-green-600 text-white font-bold rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {{ approving ? '鎖定中...' : '✅ 確認申報鎖定' }}
          </button>
          <button
            @click="approveModal.open = false"
            class="px-4 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50"
          >
            取消
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'

const API = 'http://localhost:8000/api/metabolic-recall'

const patients  = ref([])
const syncing   = ref(false)
const syncedAt  = ref(null)
const approving = ref(false)
const showGas   = ref(false)

const approvalCodes = [
  { code: 'P7501C', label: '初次收案', cls: 'border-blue-400 text-blue-700 hover:bg-blue-50' },
  { code: 'P7502C', label: '代謝追蹤', cls: 'border-green-400 text-green-700 hover:bg-green-50' },
  { code: 'P7503C', label: '代謝年度', cls: 'border-purple-400 text-purple-700 hover:bg-purple-50' },
]

const approveModal = reactive({
  open: false,
  pt:   null,
  code: 'P7502C',
  note: '',
})

async function syncSheets() {
  syncing.value = true
  try {
    const res = await fetch(`${API}/sync-sheets`)
    const data = await res.json()
    patients.value = (data.patients || []).map(p => ({
      ...p,
      _labsLoaded:  false,
      _labsLoading: false,
      _labs:        {},
      _vitals:      {},
      _showHistory: false,
    }))
    syncedAt.value = data.synced_at
  } catch (e) {
    alert('同步失敗：' + e.message)
  } finally {
    syncing.value = false
  }
}

async function loadLabs(pt) {
  pt._labsLoading = true
  try {
    const res  = await fetch(`${API}/patient-labs/${pt.pid}`)
    const data = await res.json()
    pt._labs   = data.labs   || {}
    pt._vitals = data.vitals || {}
    pt._labsLoaded = true
  } catch (e) {
    alert('BigQuery 連線失敗：' + e.message)
  } finally {
    pt._labsLoading = false
  }
}

function labItems(pt) {
  const l = pt._labs
  const v = pt._vitals
  const items = [
    { key: 'HbA1c',        label: 'HbA1c (%)',  value: l['HbA1c']?.value        || '—', date: l['HbA1c']?.date?.slice(0,7)        || '', alert: parseFloat(l['HbA1c']?.value) >= 7.0 },
    { key: 'AC-Sugar',     label: '空腹血糖',    value: l['AC-Sugar']?.value     || '—', date: l['AC-Sugar']?.date?.slice(0,7)     || '', alert: parseFloat(l['AC-Sugar']?.value) >= 126 },
    { key: 'SBP',          label: '收縮壓',      value: v.SBP                    || '—', date: v.Record_Date?.slice(0,7)           || '', alert: parseInt(v.SBP) >= 130 },
    { key: 'DBP',          label: '舒張壓',      value: v.DBP                    || '—', date: v.Record_Date?.slice(0,7)           || '', alert: parseInt(v.DBP) >= 85 },
    { key: 'Weight',       label: '體重 (kg)',   value: v.Weight                 || '—', date: v.Record_Date?.slice(0,7)           || '', alert: false },
    { key: 'Waist',        label: '腰圍 (cm)',   value: v.Waist                  || '—', date: v.Record_Date?.slice(0,7)           || '', alert: parseFloat(v.Waist) >= (pt.sex === 'F' ? 80 : 90) },
    { key: 'Triglyceride', label: 'TG (mg/dL)', value: l['Triglyceride']?.value  || '—', date: l['Triglyceride']?.date?.slice(0,7) || '', alert: parseFloat(l['Triglyceride']?.value) >= 150 },
    { key: 'HDL-C',        label: 'HDL (mg/dL)', value: l['HDL-C']?.value        || '—', date: l['HDL-C']?.date?.slice(0,7)        || '', alert: false },
  ]
  return items
}

// 找出最近一筆有填生理數據的追蹤記錄
function latestVitalsFollowup(pt) {
  if (!pt.followups) return null
  return pt.followups.find(f => f.weight || f.waist || f.sbp || f.dbp || f.fpg || f.hba1c) || null
}

function reportedVitals(pt) {
  const f = latestVitalsFollowup(pt)
  if (!f) return []
  const items = []
  if (f.weight) items.push({ label: '體重',  value: f.weight + ' kg',  alert: false })
  if (f.waist)  items.push({ label: '腰圍',  value: f.waist + ' cm',   alert: parseFloat(f.waist) >= (pt.sex === 'F' ? 80 : 90) })
  if (f.sbp || f.dbp) items.push({
    label: '血壓',
    value: `${f.sbp || '—'}/${f.dbp || '—'}`,
    alert: parseInt(f.sbp) >= 130 || parseInt(f.dbp) >= 85,
  })
  if (f.fpg)   items.push({ label: '空腹血糖', value: f.fpg,        alert: parseFloat(f.fpg) >= 100 })
  if (f.hba1c) items.push({ label: 'HbA1c',   value: f.hba1c + '%', alert: parseFloat(f.hba1c) >= 5.7 })
  return items
}

function reportedVitalsDate(pt) {
  const f = latestVitalsFollowup(pt)
  return f?.date?.slice(0, 10) || ''
}

// 歷程列的數據摘要字串
function followupVitalsStr(f) {
  const parts = []
  if (f.weight) parts.push(`${f.weight}kg`)
  if (f.waist)  parts.push(`腰${f.waist}`)
  if (f.sbp || f.dbp) parts.push(`BP ${f.sbp || '—'}/${f.dbp || '—'}`)
  if (f.fpg)   parts.push(`FPG ${f.fpg}`)
  if (f.hba1c) parts.push(`A1c ${f.hba1c}`)
  return parts.join('・')
}

function openApproveModal(pt, code) {
  approveModal.pt   = pt
  approveModal.code = code
  approveModal.note = ''
  approveModal.open = true
}

async function confirmApprove() {
  if (!approveModal.pt) return
  approving.value = true
  try {
    const res = await fetch(`${API}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pid:  approveModal.pt.pid,
        name: approveModal.pt.name,
        code: approveModal.code,
        note: approveModal.note,
      }),
    })
    const data = await res.json()
    if (data.ok) {
      approveModal.pt.approved = true
      approveModal.open = false
    }
  } catch (e) {
    alert('申報失敗：' + e.message)
  } finally {
    approving.value = false
  }
}

function notApprove(pt) {
  pt._notApproved = true
}

function formatDateTime(str) {
  if (!str) return ''
  return str.slice(0, 16).replace('T', ' ')
}
</script>
