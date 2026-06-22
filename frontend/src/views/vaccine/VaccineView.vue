<template>
  <div class="p-5 max-w-5xl mx-auto">

    <!-- 標頭 -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-xl font-bold text-slate-800">💉 帶狀皰疹疫苗 (Shingrix) 提醒</h1>
        <p class="text-xs text-slate-400 mt-0.5">
          看診時依名單提醒 · 資料更新：{{ report.generated_at || '—' }}
        </p>
      </div>
      <button
        @click="load"
        class="text-xs px-3 py-1.5 rounded-md bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40"
        :disabled="loading"
      >{{ loading ? '載入中…' : '🔄 重新整理' }}</button>
    </div>

    <!-- 尚未產生報告 -->
    <div v-if="report.available === false && !loading"
         class="p-4 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
      ⚠️ 尚未產生疫苗報告。請確認 <code>vaccine_recall_engine.py</code> 排程已執行。
    </div>

    <template v-else>
      <!-- 統計卡 -->
      <div class="grid grid-cols-4 gap-3 mb-4">
        <button
          v-for="t in tabs" :key="t.key"
          @click="activeTab = t.key"
          :class="activeTab === t.key ? 'ring-2 ring-indigo-400 bg-white' : 'bg-white hover:bg-slate-50'"
          class="p-3 rounded-xl border border-slate-200 text-left transition-all"
        >
          <div class="text-2xl font-bold" :class="t.color">{{ counts[t.key] }}</div>
          <div class="text-xs text-slate-500 mt-0.5">{{ t.label }}</div>
        </button>
      </div>

      <!-- 載入中 -->
      <div v-if="loading" class="text-center text-slate-400 py-10 text-sm">載入中…</div>

      <!-- 名單表格 -->
      <div v-else class="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div v-if="currentList.length === 0" class="text-center text-slate-400 py-10 text-sm">
          此分類目前沒有名單 🎉
        </div>
        <table v-else class="w-full text-sm">
          <thead class="bg-slate-50 text-slate-500 text-xs">
            <tr>
              <th class="text-left px-4 py-2 font-medium">病歷號</th>
              <th class="text-left px-4 py-2 font-medium">姓名</th>
              <th class="text-left px-4 py-2 font-medium">年齡</th>
              <th v-if="activeTab === 'dose2_urgent' || activeTab === 'dose2_normal'" class="text-left px-4 py-2 font-medium">第一劑日期</th>
              <th v-if="activeTab === 'dose2_urgent' || activeTab === 'dose2_normal'" class="text-left px-4 py-2 font-medium">經過天數</th>
              <th class="text-left px-4 py-2 font-medium">電話</th>
              <th class="text-right px-4 py-2 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in currentList" :key="p.病歷號"
                class="border-t border-slate-100 hover:bg-slate-50">
              <td class="px-4 py-2 text-slate-400">{{ p.病歷號 }}</td>
              <td class="px-4 py-2 font-medium text-slate-700">{{ p.姓名 }}</td>
              <td class="px-4 py-2 text-slate-600">{{ p.年齡 ?? '—' }}</td>
              <td v-if="activeTab === 'dose2_urgent' || activeTab === 'dose2_normal'" class="px-4 py-2 text-slate-600">{{ p.第一劑日期 }}</td>
              <td v-if="activeTab === 'dose2_urgent' || activeTab === 'dose2_normal'" class="px-4 py-2">
                <span :class="activeTab === 'dose2_urgent' ? 'text-red-600 font-semibold' : 'text-slate-600'">
                  {{ p.經過天數 }} 天
                </span>
              </td>
              <td class="px-4 py-2 text-slate-500">{{ p.電話 }}</td>
              <td class="px-4 py-2 text-right">
                <div class="flex items-center justify-end gap-1">
                  <button @click="lock(p)"
                    class="text-xs px-2 py-1 rounded-md bg-indigo-50 text-indigo-600 hover:bg-indigo-100 whitespace-nowrap">
                    鎖定
                  </button>
                  <button @click="dismiss(p, 'vaccinated')"
                    class="text-xs px-2 py-1 rounded-md bg-green-50 text-green-700 hover:bg-green-100 whitespace-nowrap"
                    title="已在他院施打，永久略過">
                    ✓ 已施打
                  </button>
                  <button @click="dismiss(p, 'explained')"
                    class="text-xs px-2 py-1 rounded-md bg-amber-50 text-amber-700 hover:bg-amber-100 whitespace-nowrap"
                    title="今日已說明，6個月內不再提醒">
                    💬 已說明
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { vaccineApi } from '@/api'
import { usePatientStore } from '@/stores/patient'

const patientStore = usePatientStore()

const loading = ref(false)
const report  = ref({ available: null })

const tabs = [
  { key: 'dose2_urgent', label: '第二劑最後通牒 (181~365天)',        color: 'text-red-600' },
  { key: 'dose2_normal', label: '第二劑催種 (60~180天)',             color: 'text-amber-600' },
  { key: 'dose1_remind', label: 'Shingrix 第一劑 (65歲↑DM+已打PCV)', color: 'text-indigo-600' },
  { key: 'pcv_remind',   label: 'PCV 肺炎鏈球菌 (65歲↑未打)',        color: 'text-teal-600' },
]
const activeTab = ref('dose2_urgent')

const counts = computed(() => ({
  dose2_urgent: (report.value.dose2_urgent || []).length,
  dose2_normal: (report.value.dose2_normal || []).length,
  dose1_remind: (report.value.dose1_remind || []).length,
  pcv_remind:   (report.value.pcv_remind   || []).length,
}))

const currentList = computed(() => report.value[activeTab.value] || [])

async function load() {
  loading.value = true
  try {
    const { data } = await vaccineApi.getReport()
    report.value = data
    // 預設停在有資料的第一個分類
    const firstWithData = tabs.find(t => (data[t.key] || []).length > 0)
    if (firstWithData) activeTab.value = firstWithData.key
  } catch (e) {
    report.value = { available: false }
  } finally {
    loading.value = false
  }
}

function lock(p) {
  patientStore.lockPatient({ 病歷號: p.病歷號, 姓名: p.姓名 })
}

async function dismiss(p, action) {
  // 從目前 tab 推算疫苗類型
  const vaccine = activeTab.value === 'pcv_remind' ? 'PCV' : 'Shingrix'
  try {
    await vaccineApi.dismiss(p.病歷號, vaccine, action)
    await load()   // 重整整份報告（backend 已過濾駁回）
  } catch { /* 靜默失敗 */ }
}

onMounted(load)
</script>
