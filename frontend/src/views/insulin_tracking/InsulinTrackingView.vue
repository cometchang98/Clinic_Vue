<template>
  <div class="p-4 max-w-6xl mx-auto">

    <!-- 頁首 -->
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">💉 胰島素追蹤滴定</h1>
        <p class="text-sm text-gray-500 mt-0.5">追蹤第 0/3/7/26 天滴定任務，提供 AI 建議與衛教發送</p>
      </div>
      <div class="flex gap-2 flex-wrap">
        <a href="https://script.google.com/macros/s/AKfycbyBzbsBVlevDSfdV2Xndj6u2euoACQUENX4V-lwCUfA2NWgCUqMZ07_sNTBGu4hxHV-/exec"
           target="_blank"
           class="px-3 py-2 bg-blue-100 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-200 transition">
          ☁️ 衛教師雲端版
        </a>
        <button @click="loadPatients"
                :disabled="loading"
                class="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition flex items-center gap-1">
          <span v-if="loading" class="animate-spin">⏳</span>
          <span v-else>🔄</span> 讀取名單
        </button>
      </div>
    </div>

    <!-- 錯誤訊息 -->
    <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
      {{ error }}
    </div>

    <!-- 尚未載入 -->
    <div v-if="!loaded && !loading" class="text-center py-16 text-gray-400">
      <div class="text-5xl mb-3">💉</div>
      <p class="text-lg">點擊「讀取名單」載入胰島素病患追蹤清單</p>
    </div>

    <!-- 載入中 -->
    <div v-if="loading" class="text-center py-16 text-gray-400">
      <div class="text-4xl mb-3 animate-bounce">⏳</div>
      <p>正在讀取 HIS 資料...</p>
    </div>

    <!-- 已載入 -->
    <div v-if="loaded && !loading">

      <!-- 統計列 -->
      <div class="grid grid-cols-3 gap-3 mb-5">
        <div class="bg-white rounded-xl p-3 border border-gray-100 shadow-sm text-center">
          <div class="text-2xl font-bold text-indigo-600">{{ patients.length }}</div>
          <div class="text-xs text-gray-500 mt-0.5">追蹤中病患</div>
        </div>
        <div class="bg-white rounded-xl p-3 border border-amber-100 shadow-sm text-center">
          <div class="text-2xl font-bold text-amber-600">{{ todayTasks.length }}</div>
          <div class="text-xs text-gray-500 mt-0.5">今日滴定任務</div>
        </div>
        <div class="bg-white rounded-xl p-3 border border-green-100 shadow-sm text-center">
          <div class="text-2xl font-bold text-green-600">{{ patients.filter(p => !p.stage).length }}</div>
          <div class="text-xs text-gray-500 mt-0.5">例行觀察中</div>
        </div>
      </div>

      <!-- 今日任務 -->
      <div v-if="todayTasks.length > 0" class="mb-6">
        <h2 class="text-lg font-bold text-amber-700 mb-3 flex items-center gap-2">
          🎯 今日滴定任務
          <span class="bg-amber-100 text-amber-700 text-xs px-2 py-0.5 rounded-full">{{ todayTasks.length }} 人</span>
        </h2>
        <div class="space-y-3">
          <PatientCard
            v-for="pt in todayTasks"
            :key="pt.pid"
            :patient="pt"
            :expanded-pid="expandedPid"
            :patient-data="patientDataCache[pt.pid]"
            :loading-data="loadingDataPid === pt.pid"
            @toggle="toggleExpand(pt)"
            @load-data="loadPatientData(pt.pid)"
            @log-action="logAction"
          />
        </div>
      </div>

      <!-- 全部病患 -->
      <div>
        <h2 class="text-lg font-bold text-gray-700 mb-3 flex items-center gap-2">
          👥 所有病患
          <button @click="showAll = !showAll" class="text-xs text-indigo-500 hover:underline ml-1">
            {{ showAll ? '收合' : '展開' }}
          </button>
        </h2>
        <div v-if="showAll" class="space-y-3">
          <PatientCard
            v-for="pt in patients"
            :key="pt.pid"
            :patient="pt"
            :expanded-pid="expandedPid"
            :patient-data="patientDataCache[pt.pid]"
            :loading-data="loadingDataPid === pt.pid"
            @toggle="toggleExpand(pt)"
            @load-data="loadPatientData(pt.pid)"
            @log-action="logAction"
          />
        </div>
        <div v-else class="space-y-2">
          <!-- 摺疊狀態顯示小卡 -->
          <div v-for="pt in patients" :key="'mini-' + pt.pid"
               class="flex items-center justify-between bg-white rounded-lg px-4 py-2 border border-gray-100 hover:border-indigo-200 cursor-pointer transition"
               @click="showAll = true; expandedPid = pt.pid">
            <div class="flex items-center gap-3">
              <span class="text-gray-700 font-medium text-sm">{{ pt.name }}</span>
              <DrugBadges :patient="pt" />
            </div>
            <div class="flex items-center gap-2">
              <span v-if="pt.stage" class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">{{ pt.stage.split(' ')[0] + ' ' + pt.stage.split(' ')[1] }}</span>
              <span class="text-xs text-gray-400">{{ pt.rx_date }}</span>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- 操作日誌 toast -->
    <div v-if="toastMsg"
         class="fixed bottom-6 right-6 bg-gray-800 text-white px-4 py-3 rounded-xl shadow-xl text-sm z-50 transition">
      {{ toastMsg }}
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

// ── 子元件 ─────────────────────────────────────
const DrugBadges = {
  props: ['patient'],
  template: `
    <span class="flex gap-1 flex-wrap">
      <span v-if="patient.basal.drug !== '無'" class="text-xs bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded">【長】{{ patient.basal.drug }} {{ patient.basal.dose }}U</span>
      <span v-if="patient.bolus.drug !== '無'" class="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded">【速】{{ patient.bolus.drug }} {{ patient.bolus.dose }}U</span>
      <span v-if="patient.dual.drug  !== '無'" class="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">【雙】{{ patient.dual.drug }} {{ patient.dual.dose }}U</span>
      <span v-if="patient.combo.drug !== '無'" class="text-xs bg-teal-100 text-teal-700 px-1.5 py-0.5 rounded">【複】{{ patient.combo.drug }} {{ patient.combo.dose }}U</span>
    </span>
  `
}

const PatientCard = {
  props: ['patient', 'expandedPid', 'patientData', 'loadingData'],
  emits: ['toggle', 'load-data', 'log-action'],
  components: { DrugBadges },
  template: `
    <div class="bg-white rounded-xl border shadow-sm overflow-hidden"
         :class="patient.stage ? 'border-amber-200' : 'border-gray-100'">

      <!-- 卡片頭 -->
      <div class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50"
           @click="$emit('toggle', patient)">
        <div class="flex items-center gap-3 flex-wrap">
          <span class="font-semibold text-gray-800">{{ patient.name }}</span>
          <span class="text-xs text-gray-400">{{ patient.pid }}</span>
          <DrugBadges :patient="patient" />
          <span v-if="patient.stage" class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
            🎯 {{ patient.stage }}
          </span>
        </div>
        <span class="text-gray-400 text-sm">{{ expandedPid === patient.pid ? '▲' : '▼' }}</span>
      </div>

      <!-- 展開內容 -->
      <div v-if="expandedPid === patient.pid" class="border-t border-gray-100 px-4 pb-4">

        <!-- 聯絡資訊 -->
        <div class="mt-3 flex gap-4 text-sm text-gray-600">
          <span>📞 {{ patient.phone || '無資料' }}</span>
          <span>📅 處方日: {{ patient.rx_date }}</span>
          <span>🗓️ 開立天數: {{ patient.days }} 天</span>
        </div>

        <!-- SOP checklist -->
        <div v-if="patient.sop && patient.sop.length > 0" class="mt-3">
          <div class="text-xs font-medium text-amber-700 mb-1.5">📋 今日追蹤 SOP</div>
          <div class="space-y-1">
            <label v-for="(item, i) in patient.sop" :key="i"
                   class="flex items-start gap-2 text-sm cursor-pointer">
              <input type="checkbox" class="mt-0.5 rounded" />
              <span class="text-gray-700">{{ item }}</span>
            </label>
          </div>
        </div>

        <!-- BQ 數據 -->
        <div class="mt-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-xs font-medium text-gray-600">📊 BigQuery 血糖數據</span>
            <button v-if="!patientData"
                    @click.stop="$emit('load-data', patient.pid)"
                    :disabled="loadingData"
                    class="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50">
              {{ loadingData ? '讀取中...' : '載入' }}
            </button>
          </div>

          <div v-if="patientData">
            <!-- AI 建議 -->
            <div v-if="patientData.ai"
                 class="mb-3 px-3 py-2 rounded-lg text-sm"
                 :class="{
                   'bg-red-50 text-red-800 border border-red-200':    patientData.ai.color === 'red',
                   'bg-orange-50 text-orange-800 border border-orange-200': patientData.ai.color === 'orange',
                   'bg-yellow-50 text-yellow-800 border border-yellow-200': patientData.ai.color === 'yellow',
                   'bg-green-50 text-green-800 border border-green-200':  patientData.ai.color === 'green',
                 }">
              <div class="font-medium mb-0.5">{{ patientData.ai.pattern }}</div>
              <div>{{ patientData.ai.msg }}</div>
              <div v-if="patientData.ai.action" class="mt-1 font-semibold">建議操作：{{ patientData.ai.action }}</div>
            </div>

            <!-- HbA1c -->
            <div v-if="patientData.hba1c && patientData.hba1c.length > 0" class="mb-2">
              <div class="text-xs text-gray-500 mb-1">HbA1c</div>
              <div class="flex gap-2 flex-wrap">
                <span v-for="r in patientData.hba1c" :key="r.date"
                      class="text-sm bg-gray-100 rounded px-2 py-0.5">
                  {{ r.value }}% <span class="text-xs text-gray-400">{{ r.date }}</span>
                </span>
              </div>
            </div>

            <!-- 空腹血糖表格 -->
            <div v-if="patientData.fasting_bg && patientData.fasting_bg.length > 0">
              <div class="text-xs text-gray-500 mb-1">近期空腹血糖 (AC-Sugar)</div>
              <div class="grid grid-cols-4 gap-1">
                <div v-for="r in patientData.fasting_bg.slice(0, 8)" :key="r.date"
                     class="text-center rounded px-1 py-1 text-sm"
                     :class="{
                       'bg-red-100 text-red-700':    parseFloat(r.value) < 70,
                       'bg-orange-100 text-orange-700': parseFloat(r.value) > 180,
                       'bg-yellow-100 text-yellow-700': parseFloat(r.value) > 140 && parseFloat(r.value) <= 180,
                       'bg-green-50 text-green-700':   parseFloat(r.value) >= 70  && parseFloat(r.value) <= 140,
                     }">
                  <div class="font-bold">{{ r.value }}</div>
                  <div class="text-xs opacity-70">{{ r.date.slice(5) }}</div>
                </div>
              </div>
            </div>

            <div v-if="patientData.error" class="text-xs text-red-500 mt-1">{{ patientData.error }}</div>
          </div>
        </div>

        <!-- 操作按鈕 -->
        <div class="mt-4 flex gap-2 flex-wrap">
          <button @click.stop="$emit('log-action', { patient, action: 'push_line', label: 'LINE 推播' })"
                  class="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition">
            📱 LINE 推播
          </button>
          <button @click.stop="$emit('log-action', { patient, action: 'push_fcm', label: 'APP 推播' })"
                  class="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition">
            📲 APP 推播
          </button>
          <button @click.stop="$emit('log-action', { patient, action: 'titrate', label: '已完成滴定' })"
                  class="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition">
            ✅ 已完成滴定
          </button>
          <button @click.stop="$emit('log-action', { patient, action: 'skip', label: '豁免跳過' })"
                  class="px-3 py-1.5 bg-gray-200 text-gray-600 text-sm rounded-lg hover:bg-gray-300 transition">
            🚫 豁免跳過
          </button>
        </div>

      </div>
    </div>
  `
}

// ── 主邏輯 ─────────────────────────────────────
const patients       = ref([])
const loading        = ref(false)
const loaded         = ref(false)
const error          = ref('')
const expandedPid    = ref(null)
const showAll        = ref(false)
const patientDataCache  = ref({})
const loadingDataPid    = ref(null)
const toastMsg       = ref('')

const todayTasks = computed(() => patients.value.filter(p => p.stage))

async function loadPatients() {
  loading.value = true
  error.value   = ''
  try {
    const res  = await fetch('/api/insulin/patients')
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    patients.value = data.patients
    loaded.value   = true
    showAll.value  = true
  } catch (e) {
    error.value = '讀取失敗：' + e.message
  } finally {
    loading.value = false
  }
}

function toggleExpand(pt) {
  expandedPid.value = expandedPid.value === pt.pid ? null : pt.pid
}

async function loadPatientData(pid) {
  if (patientDataCache.value[pid]) return
  loadingDataPid.value = pid
  try {
    const res  = await fetch(`/api/insulin/patient-data/${pid}`)
    const data = await res.json()
    patientDataCache.value = { ...patientDataCache.value, [pid]: data }
  } catch (e) {
    patientDataCache.value = { ...patientDataCache.value, [pid]: { error: e.message } }
  } finally {
    loadingDataPid.value = null
  }
}

async function logAction({ patient, action, label }) {
  try {
    await fetch('/api/insulin/log-action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pid:   patient.pid,
        name:  patient.name,
        action,
        stage: patient.stage || '',
        note:  label,
      }),
    })
    showToast(`✅ ${patient.name}：${label} 已記錄`)
  } catch (e) {
    showToast('記錄失敗：' + e.message)
  }
}

function showToast(msg) {
  toastMsg.value = msg
  setTimeout(() => { toastMsg.value = '' }, 3000)
}
</script>
