<template>
  <div class="space-y-4">

    <!-- 搜尋列 -->
    <div class="flex gap-3 items-center">
      <div class="relative flex-1">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">🔍</span>
        <input
          v-model="store.searchKw"
          placeholder="搜尋姓名或身分證..."
          class="w-full pl-9 pr-4 py-2.5 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white shadow-sm"
        />
      </div>
      <button
        v-if="store.searchKw || store.selectedTags.length"
        @click="clearFilter"
        class="px-3 py-2.5 text-xs text-slate-500 hover:text-red-500 border border-slate-200 rounded-xl bg-white shadow-sm transition-colors"
      >
        ✕ 清除
      </button>
    </div>

    <!-- 計畫類別標籤篩選 -->
    <div class="flex flex-wrap gap-2">
      <button
        v-for="tag in store.allTags" :key="tag"
        @click="toggleTag(tag)"
        class="px-3 py-1.5 text-xs font-medium rounded-full border transition-all duration-150"
        :class="store.selectedTags.includes(tag)
          ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
          : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:text-indigo-600'"
      >
        {{ tagIcon(tag) }} {{ tag }}
      </button>
    </div>

    <!-- 統計列 -->
    <div class="flex items-center justify-between px-4 py-2.5 bg-green-50 rounded-xl border-l-4 border-green-500">
      <span class="text-sm font-semibold text-green-800">
        篩選結果：共 <strong>{{ store.filteredMembers.length }}</strong> 筆
      </span>
      <span class="text-base font-black text-green-700">
        💰 品質獎勵金小計：{{ store.totalBonus.toLocaleString() }} 元
      </span>
    </div>

    <!-- 會員表格 -->
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200">
              <th class="px-3 py-3 text-left w-8">
                <input type="checkbox" @change="toggleAll" class="rounded accent-indigo-600" />
              </th>
              <th v-for="col in sortCols" :key="col.key"
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
            <!-- 載入中 -->
            <tr v-if="store.loading">
              <td colspan="10" class="py-16 text-center text-slate-400">
                <div class="flex flex-col items-center gap-2">
                  <span class="text-2xl animate-spin">⏳</span>
                  <span class="text-sm">載入中...</span>
                </div>
              </td>
            </tr>
            <!-- 無資料 -->
            <tr v-else-if="!store.filteredMembers.length">
              <td colspan="10" class="py-16 text-center text-slate-400 text-sm">
                找不到符合條件的會員
              </td>
            </tr>
            <!-- 資料列 -->
            <tr
              v-for="m in pagedMembers" :key="m.病歷號"
              :id="`row-${m.病歷號}`"
              class="hover:bg-slate-50 transition-colors cursor-default"
              :class="[
                selected.has(m.病歷號) ? 'bg-indigo-50' : '',
                store.highlightPid === m.病歷號 ? 'ring-2 ring-inset ring-indigo-400 bg-indigo-50 animate-pulse' : ''
              ]"
            >
              <td class="px-3 py-3">
                <input type="checkbox" :value="m.病歷號" v-model="checkedPids" class="rounded accent-indigo-600" />
              </td>
              <!-- 姓名 + 有無日誌 -->
              <td class="px-3 py-3">
                <div class="flex items-center gap-1.5">
                  <span class="font-semibold text-slate-800">{{ m.姓名 }}</span>
                  <span v-if="m.有日誌" title="有病歷日誌" class="text-xs">📖</span>
                </div>
              </td>
              <!-- 病歷號 -->
              <td class="px-3 py-3 text-slate-400 font-mono text-xs">{{ m.病歷號 }}</td>
              <!-- 計畫類別 pills -->
              <td class="px-3 py-3">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="tag in (m.計畫類別 ?? [])" :key="tag"
                    class="px-1.5 py-0.5 text-xs rounded-full"
                    :class="tagColor(tag)"
                  >{{ tagShort(tag) }}</span>
                </div>
              </td>
              <!-- 品質燈號 -->
              <td class="px-3 py-3 text-center">
                <span class="text-sm">{{ lightEmoji(m.品質燈號) }}</span>
                <div class="text-xs text-slate-400 leading-tight mt-0.5">{{ lightLabel(m.品質燈號) }}</div>
              </td>
              <!-- 預估獎金 -->
              <td class="px-3 py-3 text-right">
                <span
                  class="font-bold text-sm"
                  :class="m.預估獎金 >= 600 ? 'text-green-600' : m.預估獎金 > 0 ? 'text-amber-500' : 'text-slate-300'"
                >
                  {{ m.預估獎金 ? `$${m.預估獎金}` : '-' }}
                </span>
              </td>
              <!-- HbA1c -->
              <td class="px-3 py-3 text-center">
                <LabCell :val="m.HbA1c" :trend="m['HbA1c趨勢']" :target="7.0" :higher-bad="true" color="pink" />
              </td>
              <!-- LDL -->
              <td class="px-3 py-3 text-center">
                <LabCell :val="m.LDL" :trend="m['LDL趨勢']" :target="100" :higher-bad="true" color="purple" />
              </td>
              <!-- UACR -->
              <td class="px-3 py-3 text-center">
                <LabCell :val="m.UACR" :trend="m['UACR趨勢']" :target="30" :higher-bad="true" color="sky" />
              </td>
              <!-- 操作 -->
              <td class="px-3 py-3 text-center">
                <div class="flex gap-1 justify-center">
                  <button
                    @click="openDiary(m)"
                    title="查看病歷日誌"
                    class="px-2.5 py-1.5 text-xs bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-600 transition-colors font-medium"
                  >📖 日誌</button>
                  <button
                    @click="openPush(m)"
                    title="發送推播"
                    class="px-2.5 py-1.5 text-xs bg-indigo-100 hover:bg-indigo-200 rounded-lg text-indigo-700 transition-colors font-medium"
                  >📱 推播</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分頁條 -->
      <div class="flex items-center justify-between px-4 py-3 border-t border-slate-100 bg-slate-50">
        <span class="text-xs text-slate-400">
          第 {{ page }} / {{ totalPages }} 頁，每頁 {{ pageSize }} 筆
        </span>
        <div class="flex gap-1">
          <button
            v-for="p in pageButtons" :key="p"
            @click="page = p"
            class="w-7 h-7 text-xs rounded-lg transition-colors"
            :class="p === page ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:bg-slate-200'"
          >{{ p }}</button>
        </div>
        <div class="flex gap-1 items-center text-xs text-slate-400">
          <button @click="page = Math.max(1, page-1)" :disabled="page === 1"
            class="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-30">◀</button>
          <button @click="page = Math.min(totalPages, page+1)" :disabled="page === totalPages"
            class="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-30">▶</button>
        </div>
      </div>
    </div>

    <!-- 批次操作列 -->
    <Transition name="slide-up">
      <div v-if="checkedPids.length"
        class="flex items-center gap-3 p-3 bg-indigo-50 rounded-xl border border-indigo-200 shadow-sm">
        <span class="text-sm text-indigo-700 font-semibold">✅ 已選 {{ checkedPids.length }} 人</span>
        <button
          @click="batchAnalyze"
          :disabled="analyzing"
          class="px-4 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors font-medium"
        >{{ analyzing ? '⏳ AI 分析中...' : '🤖 批次貝蒂分析' }}</button>
        <button
          @click="checkedPids = []"
          class="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700 transition-colors"
        >取消選取</button>
        <span v-if="analyzeResult" class="text-xs text-green-700 ml-auto">{{ analyzeResult }}</span>
      </div>
    </Transition>

    <!-- 病歷日誌抽屜 -->
    <DiaryDrawer v-if="diaryTarget" :member="diaryTarget" @close="diaryTarget = null" />
    <!-- 推播面板 -->
    <PushPanel v-if="pushTarget" :member="pushTarget" @close="pushTarget = null" />
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useSortable } from '@/composables/useSortable'
import { useFamilyMedStore } from '@/stores/familyMed'
import { familyMedApi } from '@/api'
import DiaryDrawer from '../panels/DiaryDrawer.vue'
import PushPanel   from '../panels/PushPanel.vue'
import LabCell     from '@/components/common/LabCell.vue'

const store         = useFamilyMedStore()
const checkedPids   = ref([])
const analyzing     = ref(false)
const analyzeResult = ref('')
const diaryTarget   = ref(null)
const pushTarget    = ref(null)

// ── 排序 ──
const { sortKey, toggleSort, sortIcon, sorted: sortedMembers } = useSortable(
  computed(() => store.filteredMembers)
)

// ── 分頁 ──
const pageSize = 20
const page     = ref(1)

watch(() => store.filteredMembers.length, () => { page.value = 1 })
watch(sortKey, () => { page.value = 1 })

// 警報超連結：自動捲動到高亮列
watch(() => store.highlightPid, async (pid) => {
  if (!pid) return
  await nextTick()
  const el = document.getElementById(`row-${pid}`)
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
})

const totalPages = computed(() => Math.max(1, Math.ceil(sortedMembers.value.length / pageSize)))
const pagedMembers = computed(() => {
  const start = (page.value - 1) * pageSize
  return sortedMembers.value.slice(start, start + pageSize)
})
const pageButtons = computed(() => {
  const total = totalPages.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const p = page.value
  const set = new Set([1, total, p, p-1, p+1].filter(x => x >= 1 && x <= total))
  return [...set].sort((a, b) => a - b)
})

const selected = computed(() => new Set(checkedPids.value))

// ── 欄位定義 ──
const sortCols = [
  { key: '姓名',   label: '姓名',   align: 'text-left',   color: 'text-slate-500', sortable: true  },
  { key: '病歷號', label: '病歷號', align: 'text-left',   color: 'text-slate-500', sortable: true  },
  { key: '計畫類別',label:'計畫類別',align:'text-left',   color: 'text-slate-500', sortable: false },
  { key: '品質燈號',label:'品質燈號',align:'text-center', color: 'text-slate-500', sortable: true  },
  { key: '預估獎金',label:'預估獎金',align:'text-right',  color: 'text-slate-500', sortable: true  },
  { key: 'HbA1c', label: 'HbA1c', align: 'text-center', color: 'text-pink-500',  sortable: true  },
  { key: 'LDL',   label: 'LDL',   align: 'text-center', color: 'text-purple-500',sortable: true  },
  { key: 'UACR',  label: 'UACR',  align: 'text-center', color: 'text-sky-500',   sortable: true  },
  { key: '_ops',  label: '操作',  align: 'text-center', color: 'text-slate-500', sortable: false },
]

// ── 篩選 ──
function toggleTag(tag) {
  const idx = store.selectedTags.indexOf(tag)
  if (idx === -1) store.selectedTags.push(tag)
  else            store.selectedTags.splice(idx, 1)
}

function clearFilter() {
  store.searchKw = ''
  store.selectedTags = []
}

function tagIcon(tag) {
  if (tag.includes('DKD') || tag.includes('腎病變')) return '🔴'
  if (tag.includes('DM') || tag.includes('糖尿病')) return '🟡'
  if (tag.includes('CKD') || tag.includes('腎病')) return '🔵'
  if (tag.includes('三高')) return '🟠'
  return '⚪'
}

// ── 計畫類別 pill 樣式 ──
function tagShort(tag) {
  if (tag.includes('DKD') || tag.includes('腎病變')) return 'DKD'
  if (tag.includes('DM') || tag.includes('糖尿病')) return 'DM'
  if (tag.includes('CKD') || tag.includes('腎病')) return 'CKD'
  if (tag.includes('三高')) return '三高'
  if (tag.includes('一般慢性')) return '慢性'
  if (tag.includes('家醫')) return '家醫'
  return tag.slice(0, 3)
}
function tagColor(tag) {
  if (tag.includes('DKD') || tag.includes('腎病變')) return 'bg-red-100 text-red-700'
  if (tag.includes('DM') || tag.includes('糖尿病')) return 'bg-amber-100 text-amber-700'
  if (tag.includes('CKD') || tag.includes('腎病')) return 'bg-sky-100 text-sky-700'
  if (tag.includes('三高')) return 'bg-orange-100 text-orange-700'
  return 'bg-slate-100 text-slate-600'
}

// ── 燈號 ──
function lightEmoji(s) {
  if (!s) return '⚪'
  if (s.startsWith('🟢')) return '🟢'
  if (s.startsWith('🟡')) return '🟡'
  if (s.startsWith('🟠')) return '🟠'
  if (s.startsWith('🔴')) return '🔴'
  return '⚪'
}
function lightLabel(s) {
  if (!s) return '-'
  const m = s.match(/\((.+?)\)/)
  return m ? m[1] : ''
}

// ── 全選 ──
function toggleAll(e) {
  checkedPids.value = e.target.checked
    ? store.filteredMembers.map(m => m.病歷號)
    : []
}

// ── 操作 ──
function openDiary(m) { diaryTarget.value = m }
function openPush(m)  { pushTarget.value  = m }

async function batchAnalyze() {
  analyzing.value = true
  analyzeResult.value = ''
  try {
    const { data } = await familyMedApi.batchAnalyze(checkedPids.value)
    analyzeResult.value = `✅ 完成 ${data.done} 人，失敗 ${data.failed.length} 人`
    await store.fetchMembers()
  } finally {
    analyzing.value = false
  }
}
</script>

<!-- 子元件：單格檢驗值 + 趨勢 -->
<script>
// LabCell — inline sub-component (Vue 3 允許多 script block 用 defineOptions)
</script>

<style scoped>
.slide-up-enter-active, .slide-up-leave-active { transition: all 0.2s ease; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(8px); }
</style>
