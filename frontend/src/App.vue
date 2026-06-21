<template>
  <div class="flex h-screen bg-slate-50">

    <!-- ====== 左側欄：導覽 + 今日名單 ====== -->
    <aside class="w-64 bg-white border-r border-slate-200 flex flex-col shrink-0">

      <!-- 診所標頭 -->
      <div class="px-4 py-3 border-b border-slate-100">
        <h1 class="text-sm font-bold text-slate-800">🏥 凱程診所</h1>
        <p class="text-xs text-slate-400 mt-0.5">智慧戰情室</p>
      </div>

      <!-- 導覽選單（shrink-0：不壓縮，讓下方名單 section 填滿剩餘空間） -->
      <nav class="shrink-0 px-3 pt-2 pb-1 space-y-0">
        <!-- 個管系統（可折疊） -->
        <button
          @click="openCore = !openCore"
          class="w-full flex items-center justify-between px-3 pb-0.5 text-xs font-semibold text-slate-400 uppercase tracking-wide hover:text-slate-600"
        >
          <span>個管系統</span>
          <span class="text-[10px] transition-transform" :class="openCore ? 'rotate-90' : ''">▶</span>
        </button>
        <RouterLink
          v-show="openCore"
          v-for="item in coreItems" :key="item.to"
          :to="item.to"
          class="flex items-center gap-2 px-3 py-1 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          active-class="bg-indigo-50 text-indigo-700 font-medium"
        >
          <span class="text-sm">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </RouterLink>

        <!-- 診所大腦（可折疊） -->
        <button
          @click="openClinic = !openClinic"
          class="w-full flex items-center justify-between px-3 pt-1.5 pb-0.5 text-xs font-semibold text-slate-400 uppercase tracking-wide hover:text-slate-600"
        >
          <span>診所大腦</span>
          <span class="text-[10px] transition-transform" :class="openClinic ? 'rotate-90' : ''">▶</span>
        </button>
        <RouterLink
          v-show="openClinic"
          v-for="item in clinicItems" :key="item.to"
          :to="item.to"
          class="flex items-center gap-2 px-3 py-1 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          active-class="bg-indigo-50 text-indigo-700 font-medium"
        >
          <span class="text-sm">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <!-- 分隔線 -->
      <div class="border-t border-slate-100 mx-3" />

      <!-- 🔍 門診大門：任意病患查詢（身分證/病歷號） -->
      <div class="px-3 pt-2 pb-1 shrink-0">
        <div class="flex gap-1">
          <input
            v-model="searchQ"
            @keyup.enter="searchPatient"
            type="text"
            placeholder="🔍 身分證 / 病歷號"
            class="flex-1 min-w-0 text-xs px-2 py-1 rounded-md border border-slate-200 focus:border-indigo-300 focus:outline-none"
          />
          <button
            @click="searchPatient"
            :disabled="searching || !searchQ.trim()"
            class="text-xs px-2 py-1 rounded-md bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 shrink-0"
          >{{ searching ? '…' : '鎖定' }}</button>
        </div>
        <p v-if="searchError" class="mt-1 text-[10px] text-red-500">{{ searchError }}</p>
      </div>

      <!-- 今日名單區塊（可折疊） -->
      <div class="flex flex-col flex-1 min-h-0 px-3 pt-1 pb-1">

        <!-- 標頭 + 折疊按鈕 -->
        <div class="flex items-center justify-between px-1 mb-1.5">
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide">📋 今日名單</p>
          <button @click="listCollapsed = !listCollapsed" class="text-xs text-slate-400 hover:text-slate-600">
            {{ listCollapsed ? '展開' : '收合' }}
          </button>
        </div>

        <template v-if="!listCollapsed">
          <!-- 診別選擇 -->
          <div class="flex gap-1 mb-2">
            <button
              v-for="s in ['早診','午診','晚診']" :key="s"
              @click="selectedSession = s; fetchPatients()"
              :class="selectedSession === s
                ? 'bg-indigo-100 text-indigo-700 font-medium'
                : 'bg-slate-100 text-slate-500 hover:bg-slate-200'"
              class="flex-1 text-xs py-1 rounded-md transition-colors"
            >{{ s }}</button>
          </div>

          <!-- 載入中 -->
          <div v-if="listLoading" class="text-xs text-center text-slate-400 py-4">載入中…</div>

          <!-- 病患列表 -->
          <div v-else class="flex-1 overflow-y-auto space-y-0.5 min-h-0">
            <div v-if="patients.length === 0" class="text-xs text-center text-slate-400 py-4">
              今日無病患
            </div>
            <button
              v-for="(p, idx) in patients" :key="`${p.病歷號}_${idx}`"
              @click="selectPatient(p)"
              :class="patientStore.pid === p.病歷號
                ? 'bg-indigo-50 border-indigo-300 text-indigo-800'
                : 'bg-white border-slate-100 text-slate-700 hover:bg-slate-50'"
              class="w-full text-left px-2 py-1.5 rounded-lg border text-xs transition-colors"
            >
              <div class="flex items-center gap-1.5">
                <span>{{ riskIcon(p) }}</span>
                <span class="font-medium truncate">{{ p.姓名 }}</span>
                <span class="ml-auto text-slate-400 text-[10px]">{{ p.病歷號 !== '無紀錄' ? p.病歷號 : '—' }}</span>
              </div>
              <div v-if="p.標籤" class="mt-0.5 text-[10px] text-slate-400 truncate">{{ shortTags(p.標籤) }}</div>
            </button>
          </div>

          <!-- 已鎖定病患 -->
          <div v-if="patientStore.locked" class="mt-2 p-2 bg-green-50 border border-green-200 rounded-lg">
            <div class="text-xs text-green-700 font-semibold truncate">✅ {{ patientStore.name }}</div>
            <div class="text-[10px] text-green-500">{{ patientStore.pid }}</div>
            <button @click="patientStore.unlock()" class="mt-1 text-[10px] text-red-400 hover:text-red-600 w-full text-center">
              🔄 解除鎖定
            </button>
          </div>
        </template>
      </div>

      <!-- 版本 -->
      <div class="px-4 py-2 border-t border-slate-100 text-xs text-slate-400 shrink-0">
        Vue 3 + FastAPI v2.0
      </div>
    </aside>

    <!-- ====== 主內容區 ====== -->
    <div class="flex-1 flex flex-col min-w-0">

      <!-- 病患鎖定列（全域置頂） -->
      <div
        v-if="patientStore.locked"
        class="shrink-0 bg-indigo-700 text-white px-5 py-2 flex flex-wrap items-center gap-x-4 gap-y-1 shadow-sm"
      >
        <span class="text-lg">{{ patientStore.riskBadge.split(' ')[0] }}</span>
        <div class="shrink-0">
          <span class="font-bold text-base">{{ patientStore.name }}</span>
          <span class="ml-3 text-indigo-200 text-sm">{{ patientStore.pid }}</span>
        </div>
        <div v-if="patientStore.tags" class="text-indigo-200 text-xs truncate max-w-xs">
          {{ shortTags(patientStore.tags) }}
        </div>

        <!-- 病人基本資料 / 生命徵象速覽 -->
        <div v-if="vChips.length" class="flex flex-wrap items-center gap-1.5">
          <span
            v-for="c in vChips" :key="c.k"
            class="px-1.5 py-0.5 rounded bg-indigo-600/70 text-[11px] text-indigo-50 whitespace-nowrap"
          >
            <span v-if="c.label" class="text-indigo-300">{{ c.label }}</span> {{ c.val }}
          </span>
          <span v-if="summaryLoading" class="text-[11px] text-indigo-300">…</span>
        </div>

        <button
          @click="patientStore.unlock()"
          class="ml-auto shrink-0 text-indigo-200 hover:text-white text-xs border border-indigo-400 rounded px-2 py-0.5 transition-colors"
        >
          🔄 換人
        </button>
      </div>

      <!-- 無病患時的提示列 -->
      <div
        v-else
        class="shrink-0 bg-slate-100 text-slate-400 text-xs px-5 py-1.5 border-b border-slate-200"
      >
        👈 請從左側名單點選病患，或由各頁面選擇對象
      </div>

      <!-- 主要路由視圖 -->
      <main class="flex-1 overflow-y-auto">
        <RouterView />
      </main>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { usePatientStore } from '@/stores/patient'

const patientStore = usePatientStore()

// ── 鎖定病患速覽（性別/年齡 + 生命徵象）────────────────────
const summary        = ref(null)
const summaryLoading = ref(false)

async function loadSummary(pid) {
  summary.value = null
  if (!pid || pid === '無紀錄') return
  summaryLoading.value = true
  try {
    const res = await fetch(`/api/schedule/summary/${pid}`)
    const j   = await res.json()
    if (!j.error) summary.value = j
  } catch {
    /* 速覽失敗不影響主流程 */
  } finally {
    summaryLoading.value = false
  }
}

watch(() => patientStore.pid, (v) => loadSummary(v), { immediate: true })

const vChips = computed(() => {
  const s = summary.value
  const p = patientStore.currentPatient || {}
  const d = s?.demographics || {}, v = s?.vitals || {}

  // 優先用 BQ summary，缺值時回退「今日名單帶的 dashboard 欄位」（身高/BMI 等 BQ vitals 常缺）
  const coalesce = (a, b) => (a !== null && a !== undefined && a !== '' ? a : b)
  const age    = coalesce(d.age,    p.年齡)
  const sex    = coalesce(d.sex,    p.性別)
  const height = coalesce(v.height, p.身高)
  const weight = coalesce(v.weight, p.體重)
  const bmi    = coalesce(v.bmi,    p.BMI)
  const waist  = v.waist

  const out = []
  if (age    != null && age    !== '') out.push({ k: 'age',   label: '',     val: `${age}歲` })
  if (sex)                             out.push({ k: 'sex',   label: '',     val: sex })
  if (height != null && height !== '') out.push({ k: 'h',     label: '身高', val: height })
  if (weight != null && weight !== '') out.push({ k: 'w',     label: '體重', val: weight })
  if (bmi    != null && bmi    !== '') out.push({ k: 'bmi',   label: 'BMI',  val: bmi })
  if (waist  != null)                  out.push({ k: 'waist', label: '腰圍', val: waist })
  if (v.sbp  != null)                  out.push({ k: 'bp',    label: '血壓', val: `${v.sbp}/${v.dbp ?? '-'}` })
  return out
})

const coreItems = [
  { to: '/family-med',        icon: '🏠', label: '家醫個管總指揮' },
  { to: '/plan-888',          icon: '🎯', label: '888 戰略中心' },
  { to: '/metabolic-recall',  icon: '🏃', label: '代謝症候群防治' },
  { to: '/insulin-tracking',  icon: '💉', label: '胰島素追蹤滴定' },
  { to: '/dm-care',           icon: '🩺', label: '病患工作站 DM' },
  { to: '/educator',          icon: '🍎', label: '衛教師工作站' },
]
const clinicItems = [
  { to: '/vaccine',      icon: '💉', label: '疫苗提醒' },
  { to: '/consultation', icon: '🩺', label: '虛擬會診室' },
  { to: '/data-mining',  icon: '🔬', label: '雲端大數據' },
  { to: '/marketing',    icon: '📢', label: '營運發想與群發' },
  { to: '/nhi-audit',    icon: '📋', label: '健保抽審 SOAP' },
]

// 導覽群組折疊（預設收起，讓出空間給看診名單；點大標題展開/收合）
const openCore   = ref(false)
const openClinic = ref(false)

const listCollapsed = ref(false)
const listLoading   = ref(false)
const patients      = ref([])

// 預設診別：依時間自動選
const hour = new Date().getHours()
const selectedSession = ref(hour < 13 ? '早診' : hour < 18 ? '午診' : '晚診')

async function fetchPatients() {
  listLoading.value = true
  try {
    const res = await fetch(
      `/api/schedule/patients?session=${encodeURIComponent(selectedSession.value)}&date=${new Date().toISOString().slice(0,10)}`
    )
    const data = await res.json()
    patients.value = data.patients ?? []
  } catch {
    patients.value = []
  } finally {
    listLoading.value = false
  }
}

function selectPatient(p) {
  if (p.病歷號 === '無紀錄') return   // 無病歷號的跳過
  patientStore.lockPatient(p)
}

// 🔍 門診大門：任意病患查詢
const searchQ     = ref('')
const searching   = ref(false)
const searchError = ref('')

async function searchPatient() {
  const q = searchQ.value.trim()
  if (!q) return
  searching.value = true
  searchError.value = ''
  try {
    const res  = await fetch(`/api/schedule/search?q=${encodeURIComponent(q)}`)
    const data = await res.json()
    if (data.patient) {
      patientStore.lockPatient(data.patient)
      searchQ.value = ''
    } else {
      searchError.value = data.error || '查無此病患'
    }
  } catch (e) {
    searchError.value = String(e)
  } finally {
    searching.value = false
  }
}

function riskIcon(p) {
  const badge = p.風險燈號 ?? ''
  return badge.split(' ')[0] || '⚪'
}

function shortTags(tags) {
  if (!tags) return ''
  const arr = tags.split(',').map(t => t.trim()).filter(Boolean)
  const chronic = arr.filter(t => !['抽血','回診','抽血檢查','健康資料','空腹超音波檢查'].includes(t))
  return chronic.slice(0, 4).join('・') || arr.slice(0, 3).join('・')
}

onMounted(() => fetchPatients())
</script>
