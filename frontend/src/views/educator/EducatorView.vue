<template>
  <div class="flex flex-col h-full overflow-y-auto">

    <!-- 頁首 + 鎖定病患 -->
    <div class="px-5 py-3 border-b border-slate-200 bg-white shrink-0 sticky top-0 z-10">
      <div class="flex items-center gap-3">
        <h1 class="text-lg font-bold text-slate-800">🍎 衛教師工作站</h1>
        <span v-if="patientStore.locked"
          class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-sm font-medium">
          {{ patientStore.name }} · {{ patientStore.pid }}
        </span>
        <span v-else class="text-sm text-slate-400">未鎖定病患（可在衛教大腦自行搜尋）</span>
        <span class="ml-auto text-xs text-slate-400">M1 數值 → M4 衛教大腦(educator_gas) → M5 追蹤SOP</span>
      </div>
    </div>

    <div class="p-4 space-y-4 max-w-5xl mx-auto w-full">

      <!-- M1：數值概覽（衛教師看診前快速掌握） -->
      <DM_M1_Overview v-if="patientStore.pid" :pid="patientStore.pid" />

      <!-- M4：衛教大腦 iframe（內含發送按鈕，直接走 GAS → 愛管家）-->
      <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div class="px-3 py-2 border-b border-slate-100 text-xs text-slate-500 flex items-center">
          <span class="font-semibold text-slate-600">🍎 M4 衛教大腦</span>
          <span class="ml-2 text-slate-400">產出 PDF 後可在分頁內直接「📲 一鍵發送 LINE/APP」</span>
        </div>
        <iframe
          v-if="iframeSrc"
          ref="iframeEl"
          :src="iframeSrc"
          class="w-full border-0"
          style="height: 75vh;"
          title="衛教師雲端大腦"
        />
        <div v-else class="h-40 flex items-center justify-center text-slate-400 text-sm">載入衛教大腦…</div>
      </div>

      <!-- M5：追蹤 SOP 衛教協作板 -->
      <DM_M5_Followup v-if="patientStore.pid" :pid="patientStore.pid" />

    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { usePatientStore } from '@/stores/patient'
import DM_M1_Overview  from '@/components/dm_care/DM_M1_Overview.vue'
import DM_M5_Followup  from '@/components/dm_care/DM_M5_Followup.vue'

const patientStore = usePatientStore()

const gasUrl    = ref('')
const iframeEl  = ref(null)

// GAS 內容實際運行在一個 Google 沙盒中間層之下（iframe.contentWindow 只抓到 wrapper，
// 猜測巢狀 frames 結構不可靠）。改用 event.source：GAS 載入完成主動喊話，
// Vue3 收到後用 e.source 直接回傳給「剛剛跟我說話的那個 window」，精確不靠猜測。
let gasWindow = null

function sendPatientTo(win) {
  if (!win) return
  const p = patientStore.currentPatient
  if (!p) return
  win.postMessage({ type: 'set-patient', pid: p.病歷號 || '', name: p.姓名 || '' }, '*')
}

function onWindowMessage(e) {
  if (e.data?.type === 'gas-ready') {
    gasWindow = e.source
    sendPatientTo(gasWindow)
  }
}
window.addEventListener('message', onWindowMessage)

// iframe src 只取基底網址（不靠網址參數傳病人 — 經 GAS 內部轉址會遺失，改用 postMessage）
const iframeSrc = computed(() => gasUrl.value || '')

// 病患切換時，若 GAS 已回報過 window reference，立即推送更新
watch(() => patientStore.pid, () => sendPatientTo(gasWindow))

onMounted(async () => {
  try {
    const r = await fetch('/api/educator/gas-url')
    gasUrl.value = (await r.json()).url
  } catch { /* ignore */ }
})
</script>
