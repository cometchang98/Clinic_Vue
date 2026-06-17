<template>
  <div class="p-6 space-y-5">

    <!-- 頁首 -->
    <div>
      <h2 class="text-xl font-bold text-slate-800">🎯 888 戰略指揮中心</h2>
      <p class="text-sm text-slate-400 mt-0.5">0轉1 淘金計畫 · 時間錨點分析 · 貝蒂雙軌推播</p>
    </div>

    <!-- Triage 同步狀態 banner -->
    <div v-if="syncInfo" class="rounded-lg px-4 py-2 text-sm flex items-center gap-3"
         :class="syncInfo.syncing
           ? 'bg-amber-50 border border-amber-200 text-amber-800'
           : syncInfo.days_old >= 7
             ? 'bg-red-50 border border-red-200 text-red-700'
             : 'bg-green-50 border border-green-200 text-green-700'">
      <span v-if="syncInfo.syncing" class="animate-spin">⏳</span>
      <span v-else-if="syncInfo.days_old >= 7">⚠️</span>
      <span v-else>✅</span>
      <span v-if="syncInfo.syncing">攻略名單正在背景重算中（上次：{{ syncInfo.last_sync }}，已 {{ syncInfo.days_old }} 天）⋯完成後將自動重新整理</span>
      <span v-else-if="syncInfo.days_old >= 7">攻略名單距上次重算已 {{ syncInfo.days_old }} 天，請刷新頁面觸發更新</span>
      <span v-else>攻略名單正常，上次重算：{{ syncInfo.last_sync }}（{{ syncInfo.days_old }} 天前）</span>
    </div>

    <!-- 模式選擇 -->
    <div class="flex gap-2 flex-wrap">
      <button
        v-for="m in modes" :key="m.key"
        @click="switchMode(m.key)"
        class="px-4 py-2 text-sm font-semibold rounded-xl border transition-all"
        :class="mode === m.key
          ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
          : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300'"
      >
        {{ m.label }}
        <span v-if="mode === m.key && list.length" class="ml-1 px-1.5 py-0.5 text-xs bg-white/20 rounded-full">
          {{ list.length }}
        </span>
      </button>
    </div>

    <!-- 載入中 -->
    <div v-if="loading" class="flex items-center gap-3 text-slate-400 py-8">
      <span class="text-2xl animate-spin">⏳</span> 載入名單中...
    </div>

    <template v-else>
      <!-- 統計列 -->
      <div class="grid grid-cols-4 gap-3">
        <div class="bg-white rounded-xl border border-slate-200 p-3 text-center shadow-sm">
          <p class="text-xs text-slate-400">名單人數</p>
          <p class="text-2xl font-black text-indigo-600">{{ list.length }}</p>
        </div>
        <div class="bg-white rounded-xl border border-slate-200 p-3 text-center shadow-sm">
          <p class="text-xs text-slate-400">已逾期斷藥</p>
          <p class="text-2xl font-black text-red-500">{{ overdueCount }}</p>
        </div>
        <div class="bg-white rounded-xl border border-slate-200 p-3 text-center shadow-sm">
          <p class="text-xs text-slate-400">14天內耗盡</p>
          <p class="text-2xl font-black text-amber-500">{{ urgentCount }}</p>
        </div>
        <div class="bg-white rounded-xl border border-slate-200 p-3 text-center shadow-sm">
          <p class="text-xs text-slate-400">已有日誌</p>
          <p class="text-2xl font-black text-green-600">{{ withDiaryCount }}</p>
        </div>
      </div>

      <!-- 批次操作列 -->
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-sm text-slate-500">
          {{ checked.length ? `已選 ${checked.length} 人` : '勾選病患後可批次操作' }}
        </span>
        <button
          @click="batchAnalyze"
          :disabled="!checked.length || analyzing"
          class="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-40 transition-colors shadow-sm"
        >
          {{ analyzing ? `⏳ 分析中 ${analyzeProgress}/${checked.length}...` : '🤖 批次貝蒂分析' }}
        </button>
        <button
          @click="batchPushModal = true"
          :disabled="!checkedWithDraft.length"
          class="px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 disabled:opacity-40 transition-colors shadow-sm"
        >
          🚀 批次雙軌推播（{{ checkedWithDraft.length }} 人有草稿）
        </button>
        <button v-if="checked.length" @click="checked = []"
          class="text-sm text-slate-400 hover:text-slate-600">✕ 取消選取</button>
        <span v-if="analyzeResult" class="text-xs text-green-700 ml-auto">{{ analyzeResult }}</span>
      </div>

      <!-- 表格 -->
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-slate-50 border-b border-slate-200">
                <th class="px-3 py-3 w-8">
                  <input type="checkbox" @change="toggleAll" class="rounded accent-indigo-600" />
                </th>
                <th v-for="col in sortCols888" :key="col.key"
                  @click="col.sortable ? toggleSort(col.key) : null"
                  class="px-3 py-3 text-xs font-semibold tracking-wide select-none"
                  :class="[col.align, col.color,
                    col.sortable ? 'cursor-pointer hover:bg-slate-100 transition-colors' : 'cursor-default']"
                >
                  {{ col.label }}
                  <span v-if="col.sortable" class="ml-0.5 opacity-50 text-[10px]">{{ sortIcon(col.key) }}</span>
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-if="!sortedList.length">
                <td colspan="10" class="py-12 text-center text-slate-400 text-sm">此模式尚無名單資料</td>
              </tr>
              <tr
                v-for="pt in sortedList" :key="pt.病歷號"
                class="hover:bg-slate-50 transition-colors"
                :class="checkedSet.has(pt.病歷號) ? 'bg-indigo-50' : ''"
              >
                <td class="px-3 py-3">
                  <input type="checkbox" :value="pt.病歷號" v-model="checked" class="rounded accent-indigo-600" />
                </td>
                <!-- 姓名 -->
                <td class="px-3 py-3 font-semibold text-slate-800">
                  {{ pt.姓名 }}
                  <span v-if="pt.有日誌" class="ml-1 text-xs" title="有日誌">📖</span>
                </td>
                <!-- 病歷號 -->
                <td class="px-3 py-3 font-mono text-xs text-slate-400">{{ pt.病歷號 }}</td>
                <!-- 攻略難度 -->
                <td class="px-3 py-3">
                  <span class="text-sm" :title="pt['🎯 攻略難度']">
                    {{ difficultyStars(pt['🎯 攻略難度']) }}
                  </span>
                  <div class="text-xs text-slate-400 leading-tight">{{ difficultyLabel(pt['🎯 攻略難度']) }}</div>
                </td>
                <!-- 時間錨點 -->
                <td class="px-3 py-3">
                  <span
                    class="text-xs font-medium px-2 py-1 rounded-lg"
                    :class="anchorClass(pt.剩餘天數)"
                  >{{ pt.時間錨點 }}</span>
                </td>
                <!-- HbA1c -->
                <td class="px-3 py-3 text-center">
                  <LabCell :val="pt.HbA1c" :trend="pt.HbA1c_趨勢" :target="7.0" :higher-bad="true" color="pink" />
                </td>
                <!-- LDL -->
                <td class="px-3 py-3 text-center">
                  <LabCell :val="pt.LDL" :trend="pt.LDL_趨勢" :target="100" :higher-bad="true" color="purple" />
                </td>
                <!-- UACR -->
                <td class="px-3 py-3 text-center">
                  <LabCell :val="pt.UACR" :trend="pt.UACR_趨勢" :target="30" :higher-bad="true" color="sky" />
                </td>
                <!-- 推播草稿（inline 可編輯） -->
                <td class="px-3 py-3 max-w-xs">
                  <div v-if="editingDraft === pt.病歷號">
                    <textarea
                      v-model="draftMap[pt.病歷號]"
                      rows="3"
                      class="w-full text-xs border border-indigo-300 rounded-lg p-1.5 focus:outline-none resize-none"
                      @blur="editingDraft = ''"
                    />
                  </div>
                  <div
                    v-else
                    @dblclick="editingDraft = pt.病歷號"
                    class="text-xs text-slate-600 line-clamp-2 cursor-text hover:text-indigo-700"
                    :title="draftMap[pt.病歷號] || '尚無草稿，雙擊輸入或執行分析'"
                  >
                    {{ draftMap[pt.病歷號] || '─ 雙擊輸入或執行分析 ─' }}
                  </div>
                </td>
                <!-- 操作 -->
                <td class="px-3 py-3 text-center">
                  <div class="flex gap-1 justify-center">
                    <button @click="openDiary(pt)"
                      class="px-2 py-1.5 text-xs bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-600 transition-colors">
                      📖 日誌
                    </button>
                    <button @click="openPush(pt)"
                      :disabled="!draftMap[pt.病歷號]"
                      class="px-2 py-1.5 text-xs bg-indigo-100 hover:bg-indigo-200 rounded-lg text-indigo-700 transition-colors disabled:opacity-40">
                      📱 推播
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- 批次推播確認 Modal -->
    <Teleport to="body">
      <div v-if="batchPushModal" class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center">
        <div class="bg-white rounded-2xl shadow-2xl w-[480px] p-6 space-y-4">
          <h3 class="font-bold text-slate-800 text-lg">🚀 確認批次雙軌推播</h3>
          <p class="text-sm text-slate-600">即將對以下 <strong>{{ checkedWithDraft.length }}</strong> 位病患發送 LINE + APP 推播：</p>
          <div class="max-h-48 overflow-y-auto space-y-1">
            <div v-for="pt in checkedWithDraft" :key="pt.病歷號"
              class="flex justify-between text-xs px-3 py-2 bg-slate-50 rounded-lg">
              <span class="font-medium">{{ pt.姓名 }} <span class="text-slate-400">{{ pt.病歷號 }}</span></span>
              <span class="text-slate-500 max-w-[200px] truncate">{{ draftMap[pt.病歷號] }}</span>
            </div>
          </div>
          <div class="flex gap-2 justify-end pt-2">
            <button @click="batchPushModal = false"
              class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">取消</button>
            <button @click="executeBatchPush" :disabled="pushing"
              class="px-5 py-2 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50">
              {{ pushing ? '發送中...' : '🚀 確認發送' }}
            </button>
          </div>
          <p v-if="pushResult" class="text-xs text-center" :class="pushOk ? 'text-green-600' : 'text-red-500'">
            {{ pushResult }}
          </p>
        </div>
      </div>
    </Teleport>

    <!-- 日誌抽屜（複用）-->
    <DiaryDrawer
      v-if="diaryTarget"
      :member="{ ...diaryTarget, 計畫類別: diaryTarget.計畫類別 ?? [] }"
      @close="diaryTarget = null"
    />

    <!-- 推播面板（複用）-->
    <PushPanel888
      v-if="pushTarget"
      :pt="pushTarget"
      :draft="draftMap[pushTarget.病歷號]"
      @update:draft="v => draftMap[pushTarget.病歷號] = v"
      @close="pushTarget = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { plan888Api } from '@/api'
import { useSortable } from '@/composables/useSortable'
import LabCell     from '@/components/common/LabCell.vue'
import DiaryDrawer from './family_med/panels/DiaryDrawer.vue'
import PushPanel888 from './plan888/PushPanel888.vue'

// ── 模式 ──
const modes = [
  { key: 'DM',     label: '🟡 DM 0轉1' },
  { key: 'CKD',    label: '🔵 CKD 0轉1' },
  { key: 'DKD',    label: '🔴 DKD 0轉1' },
  { key: 'DKD2to3',label: '🏆 DKD 最後一哩路' },
]

const mode    = ref('DM')
const list    = ref([])
const loading = ref(false)
const syncInfo = ref(null)
const draftMap = ref({})   // pid → 草稿文字

// ── 排序 ──
const { sortKey, toggleSort, sortIcon, sorted: sortedList } = useSortable(list)

const checked     = ref([])
const checkedSet  = computed(() => new Set(checked.value))
const checkedPts  = computed(() => list.value.filter(pt => checkedSet.value.has(pt.病歷號)))
const checkedWithDraft = computed(() => checkedPts.value.filter(pt => draftMap.value[pt.病歷號]))

// ── 統計 ──
const overdueCount   = computed(() => list.value.filter(pt => (pt.剩餘天數 ?? 999) < 0).length)
const urgentCount    = computed(() => list.value.filter(pt => { const d = pt.剩餘天數; return d !== null && d >= 0 && d < 14 }).length)
const withDiaryCount = computed(() => list.value.filter(pt => pt.有日誌).length)

// ── 欄位定義 ──
const sortCols888 = [
  { key: '姓名',       label: '姓名',       align: 'text-left',   color: 'text-slate-500', sortable: true  },
  { key: '病歷號',     label: '病歷號',     align: 'text-left',   color: 'text-slate-500', sortable: true  },
  { key: '🎯 攻略難度', label: '攻略難度',  align: 'text-left',   color: 'text-slate-500', sortable: true  },
  { key: '剩餘天數',   label: '⏰ 時間錨點', align: 'text-left',  color: 'text-red-500',   sortable: true  },
  { key: 'HbA1c',     label: 'HbA1c',     align: 'text-center', color: 'text-pink-500',  sortable: true  },
  { key: 'LDL',       label: 'LDL',       align: 'text-center', color: 'text-purple-500',sortable: true  },
  { key: 'UACR',      label: 'UACR',      align: 'text-center', color: 'text-sky-500',   sortable: true  },
  { key: '_draft',    label: '推播草稿',   align: 'text-left',   color: 'text-slate-500', sortable: false },
  { key: '_ops',      label: '操作',      align: 'text-center', color: 'text-slate-500', sortable: false },
]

// ── 載入名單 ──
async function loadList() {
  loading.value = true
  checked.value = []
  try {
    const { data } = await plan888Api.getTriage(mode.value)
    // 後端現在回傳 { patients: [...], sync: {...} }
    const patients = data?.patients ?? data
    syncInfo.value = data?.sync ?? null
    list.value = patients
    patients.forEach(pt => {
      if (!draftMap.value[pt.病歷號]) {
        draftMap.value[pt.病歷號] = pt.推播草稿 || ''
      }
    })
    // 若正在背景重算，60 秒後自動重拉
    if (data?.sync?.syncing) {
      setTimeout(() => loadList(), 60_000)
    }
  } finally {
    loading.value = false
  }
}

function switchMode(m) {
  mode.value = m
  loadList()
}

onMounted(() => loadList())

// ── 攻略難度 ──
function difficultyStars(s = '') {
  if (s.includes('⭐⭐⭐')) return '⭐⭐⭐'
  if (s.includes('⭐⭐'))  return '⭐⭐'
  if (s.includes('⭐'))    return '⭐'
  if (s.includes('差'))    return '🏁'
  return '─'
}
function difficultyLabel(s = '') {
  if (s.includes('極易')) return '極易達標'
  if (s.includes('中等')) return '中等'
  if (s.includes('困難')) return '困難'
  if (s.includes('差'))   return s
  return s.replace(/⭐/g, '').trim()
}

// ── 時間錨點顏色 ──
function anchorClass(days) {
  if (days === null || days === undefined) return 'bg-slate-100 text-slate-500'
  if (days < 0)  return 'bg-red-100 text-red-700'
  if (days < 14) return 'bg-amber-100 text-amber-700'
  return 'bg-green-50 text-green-700'
}

// ── 全選 ──
function toggleAll(e) {
  checked.value = e.target.checked ? list.value.map(pt => pt.病歷號) : []
}

// ── 批次分析 ──
const analyzing       = ref(false)
const analyzeProgress = ref(0)
const analyzeResult   = ref('')

async function batchAnalyze() {
  analyzing.value    = true
  analyzeProgress.value = 0
  analyzeResult.value   = ''
  const targets = checkedPts.value
  let done = 0, failed = 0
  for (const pt of targets) {
    try {
      const { data } = await plan888Api.analyze(pt.病歷號, pt)
      if (data.ok) {
        if (data.draft) draftMap.value[pt.病歷號] = data.draft
        // 更新日誌狀態
        const idx = list.value.findIndex(p => p.病歷號 === pt.病歷號)
        if (idx >= 0) list.value[idx].有日誌 = true
        done++
      } else { failed++ }
    } catch { failed++ }
    analyzeProgress.value++
  }
  analyzing.value = false
  analyzeResult.value = `✅ 完成 ${done} 人${failed ? `，${failed} 人失敗` : ''}`
}

// ── 批次推播 ──
const batchPushModal = ref(false)
const pushing        = ref(false)
const pushResult     = ref('')
const pushOk         = ref(true)
const editingDraft   = ref('')

async function executeBatchPush() {
  pushing.value    = true
  pushResult.value = ''
  let ok = 0, fail = 0
  for (const pt of checkedWithDraft.value) {
    try {
      const { data } = await plan888Api.push(pt.病歷號, draftMap.value[pt.病歷號], '888專案 H2S 群發')
      data.ok ? ok++ : fail++
    } catch { fail++ }
  }
  pushing.value = false
  pushOk.value  = fail === 0
  pushResult.value = `🎉 完成！成功 ${ok} 人${fail ? `，失敗 ${fail} 人` : ''}`
}

// ── 日誌 & 推播 ──
const diaryTarget = ref(null)
const pushTarget  = ref(null)
function openDiary(pt) { diaryTarget.value = pt }
function openPush(pt)  { pushTarget.value  = pt }
</script>
