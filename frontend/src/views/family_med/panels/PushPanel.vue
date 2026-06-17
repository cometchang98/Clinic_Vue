<template>
  <div class="fixed inset-0 bg-black/30 z-40" @click="$emit('close')" />

  <div class="fixed right-0 top-0 h-full w-[480px] bg-white shadow-2xl z-50 flex flex-col">
    <div class="flex items-center justify-between px-5 py-4 border-b border-slate-200">
      <div>
        <h3 class="font-bold text-slate-800">📱 {{ member.姓名 }} 專屬推播</h3>
        <LightBadge :status="member.品質燈號 ?? '⚪ 未計算'" />
      </div>
      <button @click="$emit('close')" class="text-slate-400 hover:text-slate-600 text-xl">✕</button>
    </div>

    <div class="flex-1 overflow-y-auto p-5 space-y-4">
      <!-- 最新指標快覽 -->
      <div class="grid grid-cols-3 gap-2">
        <div class="text-center p-2 bg-pink-50 rounded-lg">
          <p class="text-xs text-slate-500">HbA1c</p>
          <p class="font-bold text-pink-700">{{ member.HbA1c ?? '-' }}</p>
        </div>
        <div class="text-center p-2 bg-purple-50 rounded-lg">
          <p class="text-xs text-slate-500">LDL</p>
          <p class="font-bold text-purple-700">{{ member.LDL ?? '-' }}</p>
        </div>
        <div class="text-center p-2 bg-blue-50 rounded-lg">
          <p class="text-xs text-slate-500">UACR</p>
          <p class="font-bold text-blue-700">{{ member.UACR ?? '-' }}</p>
        </div>
      </div>

      <!-- AI 生成草稿 -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="text-sm font-semibold text-slate-700">推播文案</label>
          <button
            @click="generateDraft"
            :disabled="generating"
            class="px-3 py-1 text-xs bg-indigo-100 text-indigo-700 rounded-full hover:bg-indigo-200 disabled:opacity-50 transition-colors"
          >
            {{ generating ? '✨ 生成中...' : '✨ 讓貝蒂撰寫' }}
          </button>
        </div>
        <textarea
          v-model="draft"
          rows="7"
          placeholder="點擊「讓貝蒂撰寫」自動生成，或直接手動輸入..."
          class="w-full text-sm border border-slate-200 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
        />
        <p class="text-xs text-slate-400 mt-1 text-right">{{ draft.length }} 字</p>
      </div>

      <!-- 豁免備註 -->
      <details class="text-sm">
        <summary class="cursor-pointer text-slate-500 hover:text-slate-700">🛡️ 臨床豁免（不推播）</summary>
        <textarea
          v-model="skipNote"
          rows="3"
          placeholder="記錄豁免原因..."
          class="mt-2 w-full text-sm border border-slate-200 rounded-lg p-3 focus:outline-none resize-none"
        />
        <button
          @click="sendSkip"
          :disabled="sending"
          class="mt-2 px-4 py-1.5 text-sm bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 disabled:opacity-50"
        >
          🚫 寫入豁免紀錄
        </button>
      </details>
    </div>

    <!-- 底部發送 -->
    <div class="px-5 py-4 border-t border-slate-200 space-y-2">
      <p class="text-xs text-slate-400">將同時發送 LINE 官方訊息 + APP 推播（雙軌）</p>
      <div class="flex gap-2">
        <button @click="$emit('close')" class="flex-1 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50">
          取消
        </button>
        <button
          @click="sendPush"
          :disabled="sending || !draft.trim()"
          class="flex-2 px-6 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 font-medium"
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
import { ref, onMounted } from 'vue'
import { familyMedApi } from '@/api'
import { useFamilyMedStore } from '@/stores/familyMed'
import LightBadge from '@/components/common/LightBadge.vue'

const props = defineProps({ member: Object })
const emit  = defineEmits(['close'])
const store = useFamilyMedStore()

const draft      = ref(store.getDraft(props.member.病歷號))
const skipNote   = ref('')
const generating = ref(false)
const sending    = ref(false)
const resultMsg  = ref('')
const resultOk   = ref(true)

async function generateDraft() {
  generating.value = true
  try {
    const { data } = await familyMedApi.generateDraft(props.member.病歷號, {
      HbA1c: props.member.HbA1c,
      LDL:   props.member.LDL,
      UACR:  props.member.UACR,
    })
    draft.value = data.draft
    store.setDraft(props.member.病歷號, draft.value)
  } finally {
    generating.value = false
  }
}

async function sendPush() {
  sending.value = true
  resultMsg.value = ''
  try {
    const { data } = await familyMedApi.sendPush(
      props.member.病歷號,
      draft.value,
      '家醫計畫日常關懷'
    )
    resultOk.value  = true
    resultMsg.value = `✅ 發送完成 LINE: ${data.line_status} | APP: ${data.fcm_status}`
    store.setDraft(props.member.病歷號, draft.value)
  } catch (e) {
    resultOk.value  = false
    resultMsg.value = `❌ 發送失敗：${e.message}`
  } finally {
    sending.value = false
  }
}

async function sendSkip() {
  sending.value = true
  try {
    await familyMedApi.sendPush(
      props.member.病歷號,
      `【臨床豁免】${skipNote.value}`,
      '臨床豁免'
    )
    resultOk.value  = true
    resultMsg.value = '✅ 豁免紀錄已寫入'
  } finally {
    sending.value = false
  }
}
</script>
