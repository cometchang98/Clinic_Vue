<template>
  <div class="bg-white rounded-xl border border-slate-200 p-4 space-y-3">

    <!-- 標頭 -->
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold text-slate-700">💊 M2 用藥分析</h3>
      <button
        @click="load"
        :disabled="loading"
        class="text-xs text-indigo-500 hover:text-indigo-700 disabled:opacity-40"
      >{{ loading ? '載入中…' : '🔄 重整' }}</button>
    </div>

    <div v-if="error" class="text-xs text-red-500 bg-red-50 rounded p-2">{{ error }}</div>

    <div v-else-if="!data && !loading" class="text-xs text-slate-400 text-center py-4">
      點擊重整載入用藥
    </div>

    <div v-else-if="loading" class="space-y-2 animate-pulse">
      <div class="h-4 bg-slate-100 rounded w-2/3" />
      <div class="h-4 bg-slate-100 rounded w-1/2" />
      <div class="h-12 bg-slate-100 rounded" />
    </div>

    <template v-else-if="data">

      <!-- 目前 DM 用藥 + 耗盡日 -->
      <div class="rounded-lg p-3 bg-slate-50 border border-slate-200">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-semibold text-slate-600">目前 DM 用藥</span>
          <span v-if="data.expected_refill" class="text-xs"
            :class="refillColor"
          >
            {{ refillIcon }} 預計 {{ data.expected_refill }} 耗盡（{{ refillText }}）
          </span>
        </div>

        <div v-if="data.current_dm?.length" class="space-y-1">
          <div
            v-for="m in data.current_dm" :key="m.drug"
            class="flex items-center gap-2 text-xs"
          >
            <span class="font-medium text-slate-700">{{ m.drug }}</span>
            <span
              v-if="m.insulin"
              class="px-1.5 py-0.5 rounded text-[10px] font-semibold"
              :class="insulinBadge(m.insulin)"
            >{{ insulinLabel(m.insulin) }}</span>
            <!-- 慢箋 / 單次徽章 -->
            <span
              v-if="m.chronic"
              class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-100 text-indigo-700"
            >慢箋×{{ m.refills }}</span>
            <span
              v-else-if="m.chronic === false"
              class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-500"
            >單次</span>
            <span class="ml-auto text-slate-400">{{ m.atc }} · {{ m.days }}天</span>
          </div>
        </div>
        <div v-else class="text-xs text-slate-400 text-center py-1">最近無 DM 用藥處方</div>

        <div v-if="data.last_rx_date" class="mt-2 pt-2 border-t border-slate-200 text-[11px] text-slate-400">
          最後處方日：{{ data.last_rx_date }}
        </div>
      </div>

      <!-- 用藥連續性甘特圖 -->
      <div class="rounded-lg p-3 bg-slate-50 border border-slate-200">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-semibold text-slate-600">三高用藥連續性軌跡（慢箋合併）</span>
          <span class="text-[10px] text-slate-400">{{ axisStart }} ～ {{ axisEnd }}</span>
        </div>

        <div v-if="ganttRows.length" class="space-y-1.5">
          <!-- 一藥一列；同藥的多個區段畫在同一條軌道上 -->
          <div
            v-for="row in ganttRows" :key="row.cat + row.drug"
            class="flex items-center gap-2"
          >
            <!-- 藥名 -->
            <div class="w-32 shrink-0 text-[11px] text-slate-600 truncate" :title="row.drug">
              <span>{{ row.cat.split(' ')[0] }}</span>
              {{ row.drug }}
            </div>
            <!-- 條形軌道（同一列可有多段）-->
            <div class="flex-1 relative h-4 bg-slate-100 rounded">
              <div
                v-for="(seg, i) in row.segments" :key="i"
                class="absolute h-4 rounded"
                :class="catColor(row.cat)"
                :style="barStyle(seg)"
                :title="`${seg.start} → ${seg.end}`"
              />
            </div>
          </div>

          <!-- 今日線標記 -->
          <div class="flex items-center gap-2 mt-1">
            <div class="w-32 shrink-0" />
            <div class="flex-1 relative h-3">
              <div class="absolute w-px h-3 bg-red-400" :style="{ left: todayPct + '%' }" />
              <span class="absolute text-[9px] text-red-400" :style="{ left: todayPct + '%' }">今日</span>
            </div>
          </div>
        </div>

        <div v-else class="text-xs text-slate-400 text-center py-2">近 2 年無三高開藥紀錄</div>
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
    const res  = await fetch(`/api/dm-care/m2/${props.pid}`)
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

// ── 甘特圖時間軸 ─────────────────────────────────────────
const axisRange = computed(() => {
  const segs = data.value?.gantt ?? []
  if (!segs.length) return null
  let min = Infinity, max = -Infinity
  for (const g of segs) {
    min = Math.min(min, +new Date(g.start))
    max = Math.max(max, +new Date(g.end))
  }
  // 把今日也納入軸範圍
  max = Math.max(max, Date.now())
  return { min, max, span: Math.max(max - min, 1) }
})

const axisStart = computed(() => axisRange.value ? new Date(axisRange.value.min).toISOString().slice(0,7) : '')
const axisEnd   = computed(() => axisRange.value ? new Date(axisRange.value.max).toISOString().slice(0,7) : '')

// 一藥一列：以「健保代號」分組（同代號＝同一條線，換廠牌才另開列）
const ganttRows = computed(() => {
  const segs = data.value?.gantt ?? []
  const byCode = new Map()
  for (const g of segs) {
    const key = g.code || g.drug
    if (!byCode.has(key)) byCode.set(key, { drug: g.drug, cat: g.cat, segments: [] })
    byCode.get(key).segments.push({ start: g.start, end: g.end })
  }
  return Array.from(byCode.values()).sort((a, b) =>
    (a.cat + a.drug).localeCompare(b.cat + b.drug))
})

const todayPct = computed(() => {
  if (!axisRange.value) return 0
  const { min, span } = axisRange.value
  return Math.round(((Date.now() - min) / span) * 100)
})

function barStyle(g) {
  if (!axisRange.value) return {}
  const { min, span } = axisRange.value
  const left  = ((+new Date(g.start) - min) / span) * 100
  const width = ((+new Date(g.end) - +new Date(g.start)) / span) * 100
  return { left: left + '%', width: Math.max(width, 1) + '%' }
}

function catColor(cat) {
  if (cat.includes('血糖')) return 'bg-rose-400'
  if (cat.includes('血壓')) return 'bg-emerald-400'
  if (cat.includes('血脂')) return 'bg-blue-400'
  return 'bg-slate-400'
}

// ── 胰島素徽章 ───────────────────────────────────────────
function insulinLabel(kind) {
  return { 長效: '長', 速效: '速', 雙效: '雙', 複方: '複', 預混: '混' }[kind] ?? kind
}
function insulinBadge(kind) {
  return {
    長效: 'bg-blue-100 text-blue-700',
    速效: 'bg-orange-100 text-orange-700',
    雙效: 'bg-purple-100 text-purple-700',
    複方: 'bg-pink-100 text-pink-700',
    預混: 'bg-teal-100 text-teal-700',
  }[kind] ?? 'bg-slate-100 text-slate-600'
}

// ── 耗盡日提示 ───────────────────────────────────────────
const refillText = computed(() => {
  const d = data.value?.days_to_refill
  if (d == null) return ''
  return d >= 0 ? `還有 ${d} 天` : `已逾期 ${-d} 天`
})
const refillIcon = computed(() => {
  const d = data.value?.days_to_refill
  if (d == null) return ''
  if (d < 0)  return '🚨'
  if (d < 14) return '⚠️'
  return '🦋'
})
const refillColor = computed(() => {
  const d = data.value?.days_to_refill
  if (d == null) return 'text-slate-400'
  if (d < 0)  return 'text-red-600'
  if (d < 14) return 'text-orange-600'
  return 'text-slate-500'
})
</script>
