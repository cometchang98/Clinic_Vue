<template>
  <div class="fixed inset-0 bg-black/30 z-40" @click="$emit('close')" />

  <div class="fixed right-0 top-0 h-full w-[480px] bg-white shadow-2xl z-50 flex flex-col">
    <!-- 標題 -->
    <div class="px-5 py-4 border-b border-slate-200">
      <h3 class="font-bold text-slate-800">📱 {{ pt.姓名 }} 推播</h3>
      <p class="text-xs text-slate-400 mt-0.5">病歷號：{{ pt.病歷號 }}</p>
    </div>

    <!-- 時間錨點 -->
    <div
      class="mx-5 mt-4 px-4 py-2.5 rounded-xl text-xs font-medium"
      :class="anchorBg"
    >
      ⏰ {{ pt.時間錨點 || '無時間錨點資料' }}
    </div>

    <!-- 指標快覽 -->
    <div class="grid grid-cols-3 gap-2 px-5 mt-3">
      <div class="text-center p-2 bg-pink-50 rounded-lg">
        <p class="text-xs text-slate-500">HbA1c</p>
        <p class="font-bold text-pink-700">{{ pt.HbA1c ?? '-' }}</p>
        <p class="text-xs" :class="trendColor(pt.HbA1c_趨勢)">{{ trendArrow(pt.HbA1c_趨勢) }}</p>
      </div>
      <div class="text-center p-2 bg-purple-50 rounded-lg">
        <p class="text-xs text-slate-500">LDL</p>
        <p class="font-bold text-purple-700">{{ pt.LDL ?? '-' }}</p>
        <p class="text-xs" :class="trendColor(pt.LDL_趨勢)">{{ trendArrow(pt.LDL_趨勢) }}</p>
      </div>
      <div class="text-center p-2 bg-sky-50 rounded-lg">
        <p class="text-xs text-slate-500">UACR</p>
        <p class="font-bold text-sky-700">{{ pt.UACR ?? '-' }}</p>
        <p class="text-xs" :class="trendColor(pt.UACR_趨勢)">{{ trendArrow(pt.UACR_趨勢) }}</p>
      </div>
    </div>

    <!-- 草稿 -->
    <div class="flex-1 px-5 mt-4">
      <div class="flex justify-between items-center mb-2">
        <label class="text-sm font-semibold text-slate-700">推播文案</label>
        <span class="text-xs text-slate-400">{{ localDraft.length }} 字</span>
      </div>
      <textarea
        v-model="localDraft"
        rows="8"
        class="w-full text-sm border border-slate-200 rounded-xl p-3 focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none bg-slate-50"
        placeholder="雙擊表格草稿欄輸入，或先執行貝蒂分析..."
      />
    </div>

    <!-- 底部 -->
    <div class="px-5 py-4 border-t border-slate-200 space-y-2">
      <p class="text-xs text-slate-400">同時發送 LINE 官方訊息 + APP 推播（雙軌）</p>
      <div class="flex gap-2">
        <button @click="$emit('close')"
          class="flex-1 py-2 text-sm text-slate-600 border border-slate-200 rounded-xl hover:bg-slate-50">
          取消
        </button>
        <button
          @click="send"
          :disabled="sending || !localDraft.trim()"
          class="flex-[2] py-2 text-sm font-medium bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 disabled:opacity-50"
        >
          {{ sending ? '🚀 發送中...' : '🚀 一鍵雙軌發送' }}
        </button>
      </div>
      <p v-if="resultMsg" class="text-xs text-center" :class="resultOk ? 'text-green-600' : 'text-red-500'">
        {{ resultMsg }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { plan888Api } from '@/api'

const props = defineProps({
  pt:    { type: Object, required: true },
  draft: { type: String, default: '' },
})
const emit = defineEmits(['close', 'update:draft'])

const localDraft = ref(props.draft)
const sending    = ref(false)
const resultMsg  = ref('')
const resultOk   = ref(true)

watch(localDraft, v => emit('update:draft', v))
watch(() => props.draft, v => { if (v !== localDraft.value) localDraft.value = v })

const anchorBg = computed(() => {
  const d = props.pt.剩餘天數
  if (d === null || d === undefined) return 'bg-slate-100 text-slate-600'
  if (d < 0)  return 'bg-red-100 text-red-700'
  if (d < 14) return 'bg-amber-100 text-amber-700'
  return 'bg-green-50 text-green-700'
})

function trendArrow(t = '') {
  if (t?.includes('🔺')) return '↑'
  if (t?.includes('🟢')) return '↓'
  return '─'
}
function trendColor(t = '') {
  if (t?.includes('🔺')) return 'text-red-400'
  if (t?.includes('🟢')) return 'text-green-500'
  return 'text-slate-300'
}

async function send() {
  sending.value    = true
  resultMsg.value  = ''
  try {
    const { data } = await plan888Api.push(props.pt.病歷號, localDraft.value, '888專案 H2S 推播')
    resultOk.value  = true
    resultMsg.value = `✅ LINE: ${data.line_status} | APP: ${data.fcm_status}`
  } catch (e) {
    resultOk.value  = false
    resultMsg.value = `❌ 發送失敗：${e.message}`
  } finally {
    sending.value = false
  }
}
</script>
