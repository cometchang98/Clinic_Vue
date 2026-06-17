<template>
  <!-- 遮罩 -->
  <div class="fixed inset-0 bg-black/30 z-40" @click="$emit('close')" />

  <!-- 抽屜 -->
  <div class="fixed right-0 top-0 h-full w-[640px] bg-white shadow-2xl z-50 flex flex-col">
    <!-- 標題列 -->
    <div class="flex items-center justify-between px-5 py-4 border-b border-slate-200">
      <div>
        <h3 class="font-bold text-slate-800">📖 {{ member.姓名 }} 的病歷日誌</h3>
        <p class="text-xs text-slate-400 mt-0.5">
          病歷號：{{ member.病歷號 }}
          <span v-if="lastAnalyzed" class="ml-3 text-indigo-400">🤖 最後分析：{{ lastAnalyzed }}</span>
        </p>
      </div>
      <button @click="$emit('close')" class="text-slate-400 hover:text-slate-600 text-xl leading-none">✕</button>
    </div>

    <!-- 分頁列 -->
    <div class="flex items-center justify-between border-b border-slate-200 px-5">
      <div class="flex">
        <button
          v-for="t in ['閱讀', '編輯']" :key="t"
          @click="tab = t"
          class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors"
          :class="tab === t ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700'"
        >{{ t }}</button>
      </div>

      <!-- 貝蒂分析按鈕 -->
      <button
        @click="runAnalysis"
        :disabled="analyzing"
        class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all"
        :class="analyzing
          ? 'bg-indigo-50 text-indigo-400 cursor-not-allowed'
          : 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm'"
      >
        <span :class="analyzing ? 'animate-spin' : ''">✨</span>
        {{ analyzing ? '貝蒂分析中...' : (hasContent ? '重新滾動分析' : '貝蒂起草') }}
      </button>
    </div>

    <!-- 分析提示橫幅 -->
    <Transition name="fade">
      <div v-if="analyzeMsg"
        class="px-5 py-2.5 text-xs flex items-center gap-2"
        :class="analyzeOk ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'"
      >
        <span>{{ analyzeMsg }}</span>
        <span v-if="analyzeOk" class="ml-auto text-slate-400">草稿已填入編輯框，請確認後儲存</span>
      </div>
    </Transition>

    <!-- 內容區 -->
    <div class="flex-1 overflow-y-auto p-5">
      <div v-if="loading" class="text-slate-400 text-center py-16 text-sm">⏳ 載入中...</div>

      <!-- 閱讀模式（Markdown 簡易渲染） -->
      <div
        v-else-if="tab === '閱讀'"
        class="prose prose-sm max-w-none text-slate-700"
        v-html="displayContent"
      />

      <!-- 編輯模式 -->
      <textarea
        v-else
        v-model="editContent"
        class="w-full h-full min-h-[500px] text-sm font-mono border border-slate-200 rounded-xl p-4 focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none bg-slate-50"
        placeholder="點擊「貝蒂起草」讓 AI 生成初稿，或直接手動輸入..."
      />
    </div>

    <!-- 底部操作 -->
    <div class="px-5 py-4 border-t border-slate-200 flex gap-2 justify-end items-center">
      <span v-if="tab === '編輯'" class="text-xs text-slate-400 flex-1">{{ editContent.length }} 字</span>
      <button @click="$emit('close')" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
        關閉
      </button>
      <button
        v-if="tab === '編輯'"
        @click="save"
        :disabled="saving"
        class="px-5 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 font-medium transition-colors"
      >
        {{ saving ? '儲存中...' : '💾 儲存' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { familyMedApi } from '@/api'

const props = defineProps({ member: Object })
const emit  = defineEmits(['close'])

const tab          = ref('閱讀')
const loading      = ref(true)
const saving       = ref(false)
const analyzing    = ref(false)
const analyzeMsg   = ref('')
const analyzeOk    = ref(true)
const rawContent   = ref('')
const editContent  = ref('')
const lastAnalyzed = ref('')   // 從日誌內容解析最後一次分析時間

const hasContent = computed(() => rawContent.value.trim().length > 0)

const displayContent = computed(() =>
  renderedContent.value || '<p class="text-slate-400">尚無日誌記錄。點擊右上角「貝蒂起草」讓 AI 生成初稿。</p>'
)

// 從日誌內容解析最後一次分析時間
function parseLastAnalyzed(content) {
  const matches = [...content.matchAll(/\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\].*🤖/g)]
  return matches.length ? matches[matches.length - 1][1] : ''
}

// 簡易 Markdown → HTML
const renderedContent = computed(() =>
  rawContent.value
    .replace(/^## (.+)/gm,  '<h2 class="text-base font-bold mt-5 mb-2 text-slate-800">$1</h2>')
    .replace(/^### (.+)/gm, '<h3 class="text-sm font-semibold mt-3 mb-1 text-slate-700">$1</h3>')
    .replace(/^\- (.+)/gm,  '<li class="ml-5 text-sm list-disc">$1</li>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/---/g, '<hr class="my-4 border-slate-200">')
    .replace(/\n/g, '<br>')
)

onMounted(async () => {
  try {
    const { data } = await familyMedApi.getDiary(props.member.病歷號)
    rawContent.value   = data.content ?? ''
    editContent.value  = rawContent.value
    lastAnalyzed.value = parseLastAnalyzed(rawContent.value)
  } catch {
    rawContent.value  = ''
    editContent.value = ''
  } finally {
    loading.value = false
  }
})

// 貝蒂滾動分析
async function runAnalysis() {
  analyzing.value = true
  analyzeMsg.value = ''
  try {
    const { data } = await familyMedApi.generateDraft(props.member.病歷號, {
      姓名:      props.member.姓名,
      HbA1c:    props.member.HbA1c,
      LDL:      props.member.LDL,
      UACR:     props.member.UACR,
      HbA1c趨勢: props.member['HbA1c趨勢'],
      LDL趨勢:   props.member['LDL趨勢'],
      UACR趨勢:  props.member['UACR趨勢'],
      計畫類別:   props.member.計畫類別 ?? [],
      品質燈號:   props.member.品質燈號,
      預估獎金:   props.member.預估獎金,
    })

    const now       = data.analyzed_at ?? new Date().toLocaleString('zh-TW')
    const separator = '\n\n---\n\n'
    const newEntry  = `## 🗓️ [${now}] 🤖 貝蒂滾動式分析\n${data.draft}\n`

    // 草稿寫入編輯框（不自動儲存，讓醫師審閱）
    editContent.value  = (rawContent.value ? rawContent.value + separator : '') + newEntry
    lastAnalyzed.value = now
    tab.value          = '編輯'   // 自動切到編輯分頁

    analyzeOk.value  = true
    analyzeMsg.value = `✅ 分析完成（${now}）${data.has_prior_diary ? '，已納入歷史日誌作為背景' : '，首次建立'}`
  } catch (e) {
    analyzeOk.value  = false
    analyzeMsg.value = `❌ 分析失敗：${e.message}`
  } finally {
    analyzing.value = false
  }
}

// 儲存
async function save() {
  saving.value = true
  try {
    await familyMedApi.saveDiary(props.member.病歷號, editContent.value)
    rawContent.value   = editContent.value
    lastAnalyzed.value = parseLastAnalyzed(rawContent.value)
    tab.value          = '閱讀'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
