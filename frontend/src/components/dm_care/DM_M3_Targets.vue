<template>
  <div class="bg-white rounded-xl border border-slate-200 p-4 space-y-3">

    <!-- 標頭 -->
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold text-slate-700">🎯 M3 達標 + 888 獎金</h3>
      <button
        @click="load"
        :disabled="loading"
        class="text-xs text-indigo-500 hover:text-indigo-700 disabled:opacity-40"
      >{{ loading ? '載入中…' : '🔄 重整' }}</button>
    </div>

    <div v-if="error" class="text-xs text-red-500 bg-red-50 rounded p-2">{{ error }}</div>

    <div v-else-if="!data && !loading" class="text-xs text-slate-400 text-center py-4">
      點擊重整載入
    </div>

    <div v-else-if="loading" class="space-y-2 animate-pulse">
      <div class="h-12 bg-slate-100 rounded" />
      <div class="h-16 bg-slate-100 rounded" />
    </div>

    <template v-else-if="data">

      <!-- 區塊 1：HbA1c 達標判定 -->
      <div
        v-if="data.hba1c"
        class="rounded-lg p-3 border"
        :class="statusBg(data.hba1c.status.color)"
      >
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs font-semibold text-slate-600">HbA1c 達標判定</span>
          <span class="text-xs" :class="statusText(data.hba1c.status.color)">
            {{ data.hba1c.status.icon }} {{ data.hba1c.status.label }}
          </span>
        </div>
        <div class="flex items-baseline gap-2">
          <span class="text-2xl font-bold text-slate-800">{{ data.hba1c.value.toFixed(1) }}%</span>
          <span class="text-xs text-slate-400">目標 &lt; {{ data.hba1c.target }}%</span>
          <span
            class="ml-auto text-xs font-medium"
            :class="data.hba1c.gap > 0 ? 'text-amber-600' : 'text-green-600'"
          >
            {{ data.hba1c.gap > 0 ? `距達標還差 ${data.hba1c.gap}%` : '已達標 ✓' }}
          </span>
        </div>
      </div>
      <div v-else class="text-xs text-slate-400 text-center py-2 bg-slate-50 rounded-lg">無 HbA1c 資料</div>

      <!-- 區塊 3：888 0轉1 獎金狀態 -->
      <div class="rounded-lg p-3 bg-slate-50 border border-slate-200">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-semibold text-slate-600">888 獎金狀態 · {{ data.plan888.pattern }}</span>
          <span
            class="text-xs font-semibold px-1.5 py-0.5 rounded"
            :class="summaryBadge(data.plan888.summary.color)"
          >
            {{ data.plan888.summary.icon }} {{ data.plan888.summary.label }}
          </span>
        </div>

        <!-- 三關指標 -->
        <div class="space-y-1.5">
          <div
            v-for="c in data.plan888.checks" :key="c.indicator"
            class="flex items-center gap-2 text-xs"
            :class="data.plan888.priority === c.indicator ? 'font-semibold' : ''"
          >
            <span :class="c.met ? 'text-green-600' : 'text-slate-600'">
              {{ c.met ? '✅' : (c.met === null ? '⚪' : '🎯') }}
            </span>
            <span class="text-slate-700">{{ c.name }}</span>
            <span v-if="data.plan888.priority === c.indicator"
              class="text-[10px] px-1 rounded bg-amber-100 text-amber-700">優先攻略</span>
            <span class="ml-auto text-slate-500">
              <template v-if="c.value !== null">
                {{ c.value }} <span class="text-slate-300">/ &lt;{{ c.target }}</span>
              </template>
              <template v-else>無資料</template>
            </span>
            <span class="w-16 text-right text-[10px]"
              :class="c.met ? 'text-green-500' : 'text-amber-500'">{{ c.star_label }}</span>
          </div>
        </div>

        <!-- 達陣進度條 -->
        <div class="mt-2 pt-2 border-t border-slate-200 flex items-center gap-2">
          <div class="flex-1 h-1.5 bg-slate-200 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all"
              :class="data.plan888.met_count > 0 ? 'bg-green-500' : 'bg-amber-400'"
              :style="{ width: progressPct + '%' }"
            />
          </div>
          <span class="text-[10px] text-slate-400">達陣 {{ data.plan888.met_count }}/{{ data.plan888.total }}</span>
        </div>

        <p class="mt-1.5 text-[10px] text-slate-400 leading-relaxed">
          💡 未來糖尿病新碼須「當次有開 DM 藥」才可申報，達標後即落入 888 獎金。
        </p>
      </div>

      <!-- 區塊 2：可申報項目 -->
      <div v-if="data.claims" class="rounded-lg p-3 bg-slate-50 border border-slate-200">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-semibold text-slate-600">📋 可申報項目（{{ data.claims.track }} 照護）</span>
          <span class="text-[10px] text-slate-400">
            收案{{ data.claims.enrolled ? '✓' : '—' }} · 追蹤{{ data.claims.followup_count }}次 · 年評{{ data.claims.annual_done ? '✓' : '—' }}
          </span>
        </div>

        <div class="space-y-1">
          <div
            v-for="(s, i) in data.claims.suggestions" :key="i"
            class="flex items-start gap-1.5 text-xs"
            :class="suggColor(s.color)"
          >
            <span>{{ s.icon }}</span><span>{{ s.text }}</span>
          </div>
        </div>

        <!-- 定期檢驗加成 -->
        <div class="mt-2 pt-2 border-t border-slate-200 flex items-center gap-3 text-[11px]">
          <span class="text-slate-500">定期檢驗加成</span>
          <span :class="data.claims.lab_bonus.hba1c.ok ? 'text-green-600' : 'text-amber-600'">
            HbA1c {{ data.claims.lab_bonus.hba1c.count }}/2
          </span>
          <span :class="data.claims.lab_bonus.ldl.ok ? 'text-green-600' : 'text-amber-600'">
            LDL {{ data.claims.lab_bonus.ldl.count }}/2
          </span>
          <span class="ml-auto font-medium"
            :class="data.claims.lab_bonus.achieved ? 'text-green-600' : 'text-slate-400'">
            {{ data.claims.lab_bonus.achieved ? '✅ 達成 (+100元/年)' : '未達成' }}
          </span>
        </div>
      </div>

      <!-- 區塊 4：健保用藥防呆 -->
      <div
        v-if="data.drug_safety"
        class="rounded-lg p-3 border"
        :class="data.drug_safety.checks?.length
          ? (hasDanger ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200')
          : 'bg-green-50 border-green-200'"
      >
        <div class="flex items-center justify-between mb-1.5">
          <span class="text-xs font-semibold text-slate-600">🛡️ 健保用藥防呆</span>
          <span class="text-xs" :class="data.drug_safety.checks?.length ? (hasDanger ? 'text-red-600' : 'text-amber-600') : 'text-green-600'">
            {{ data.drug_safety.checks?.length ? `${data.drug_safety.checks.length} 項提醒` : '✅ 無異常' }}
          </span>
        </div>

        <!-- 當次降糖藥類別 -->
        <div v-if="data.drug_safety.current_meds?.length" class="flex flex-wrap gap-1 mb-1.5">
          <span v-if="data.drug_safety.classes.sglt2" class="px-1.5 py-0.5 rounded text-[10px] bg-blue-100 text-blue-700">SGLT2i</span>
          <span v-if="data.drug_safety.classes.dpp4"  class="px-1.5 py-0.5 rounded text-[10px] bg-purple-100 text-purple-700">DPP4i</span>
          <span v-if="data.drug_safety.classes.glp1"  class="px-1.5 py-0.5 rounded text-[10px] bg-pink-100 text-pink-700">GLP-1</span>
          <span v-if="data.drug_safety.classes.metformin_ever" class="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600">Metformin史</span>
        </div>

        <div v-if="data.drug_safety.checks?.length" class="space-y-1">
          <div
            v-for="(ck, i) in data.drug_safety.checks" :key="i"
            class="flex items-start gap-1.5 text-xs"
            :class="ck.level === 'danger' ? 'text-red-700' : 'text-amber-700'"
          >
            <span>{{ ck.icon }}</span><span>{{ ck.text }}</span>
          </div>
        </div>
        <p v-else-if="data.drug_safety.current_meds?.length" class="text-xs text-green-700">
          當次降糖用藥符合健保給付規則
        </p>
        <p v-else class="text-xs text-slate-400">近期無降糖藥處方</p>
      </div>

    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({ pid: { type: String, default: '' } })

const data    = ref(null)
const loading = ref(false)
const error   = ref('')

async function load() {
  if (!props.pid) return
  loading.value = true
  error.value   = ''
  try {
    const res  = await fetch(`/api/dm-care/m3/${props.pid}`)
    const json = await res.json()
    if (json.error) { error.value = json.error; data.value = null }
    else            { data.value = json }
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

watch(() => props.pid, (v) => { if (v) load() }, { immediate: true })

const progressPct = computed(() => {
  const p = data.value?.plan888
  if (!p || !p.total) return 0
  return Math.round((p.met_count / p.total) * 100)
})

const hasDanger = computed(() =>
  (data.value?.drug_safety?.checks ?? []).some(c => c.level === 'danger')
)

function suggColor(c) {
  return {
    red:   'text-red-700',
    amber: 'text-amber-700',
    green: 'text-green-700',
    gray:  'text-slate-500',
  }[c] || 'text-slate-600'
}

function statusBg(c) {
  return {
    green:  'bg-green-50 border-green-200',
    yellow: 'bg-yellow-50 border-yellow-200',
    red:    'bg-red-50 border-red-200',
  }[c] || 'bg-slate-50 border-slate-200'
}
function statusText(c) {
  return { green: 'text-green-600', yellow: 'text-yellow-600', red: 'text-red-600' }[c] || 'text-slate-500'
}
function summaryBadge(c) {
  return {
    green: 'bg-green-100 text-green-700',
    amber: 'bg-amber-100 text-amber-700',
    gray:  'bg-slate-100 text-slate-500',
  }[c] || 'bg-slate-100 text-slate-500'
}
</script>
