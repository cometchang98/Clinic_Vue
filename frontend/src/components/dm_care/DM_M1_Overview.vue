<template>
  <div class="bg-white rounded-xl border border-slate-200 p-4 space-y-3">

    <!-- 標頭 -->
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold text-slate-700">🩸 M1 數值概覽</h3>
      <button
        @click="load"
        :disabled="loading"
        class="text-xs text-indigo-500 hover:text-indigo-700 disabled:opacity-40"
      >{{ loading ? '載入中…' : '🔄 重整' }}</button>
    </div>

    <!-- 🚨 C8 週期補測 banner -->
    <div v-if="audit.need_any"
         class="flex flex-wrap items-center gap-2 px-3 py-2 rounded-lg bg-red-50 border border-red-200">
      <span class="text-xs font-bold text-red-700 shrink-0">🚨 補測提醒</span>
      <span
        v-for="item in audit.items" :key="item.key"
        class="text-[11px] px-2 py-0.5 rounded-full bg-red-100 text-red-800 font-medium whitespace-nowrap"
        :title="item.detail"
      >
        {{ item.label }}
        <span class="text-red-500 font-normal">{{ shortDetail(item.detail) }}</span>
      </span>
    </div>

    <!-- 錯誤 -->
    <div v-if="error" class="text-xs text-red-500 bg-red-50 rounded p-2">{{ error }}</div>

    <!-- 尚未載入 -->
    <div v-else-if="!data && !loading" class="text-xs text-slate-400 text-center py-4">
      點擊重整載入數值
    </div>

    <!-- 載入中骨架 -->
    <div v-else-if="loading" class="space-y-2 animate-pulse">
      <div class="h-4 bg-slate-100 rounded w-2/3" />
      <div class="h-4 bg-slate-100 rounded w-1/2" />
      <div class="h-4 bg-slate-100 rounded w-3/4" />
    </div>

    <!-- 資料顯示 -->
    <template v-else-if="data">

      <!-- HbA1c 區塊：最新值 + 近兩年折線圖 -->
      <div class="rounded-lg p-3 border"
        :class="{
          'bg-green-50 border-green-200':  data.hba1c?.status?.color === 'green',
          'bg-yellow-50 border-yellow-200': data.hba1c?.status?.color === 'yellow',
          'bg-red-50 border-red-200':      data.hba1c?.status?.color === 'red',
          'bg-slate-50 border-slate-200':  !data.hba1c?.status,
        }"
      >
        <!-- 標題列：HbA1c + 最新值 + 趨勢 + 達標燈號 + 距今天數（單行） -->
        <div class="flex items-baseline gap-2 mb-1">
          <span class="text-xs font-semibold text-slate-600">HbA1c</span>
          <span class="text-2xl font-bold text-slate-800">
            {{ data.hba1c?.latest?.toFixed(1) ?? '—' }}%
          </span>
          <span class="text-base" :class="trendColor(data.hba1c?.trend)">
            {{ data.hba1c?.trend }}
          </span>
          <span class="text-xs ml-1"
            :class="{
              'text-green-600':  data.hba1c?.status?.color === 'green',
              'text-yellow-600': data.hba1c?.status?.color === 'yellow',
              'text-red-600':    data.hba1c?.status?.color === 'red',
            }"
          >
            {{ data.hba1c?.status?.icon }} {{ data.hba1c?.status?.label }}
          </span>
          <span class="text-[10px] text-slate-400 ml-auto">
            {{ data.hba1c?.days_since != null ? `${data.hba1c.days_since} 天前` : '' }}
          </span>
        </div>

        <!-- 近兩年折線圖（仿 dashboard2） -->
        <VChart
          v-if="(data.hba1c?.records?.length ?? 0) >= 2"
          :option="a1cChartOption"
          autoresize
          style="height: 110px; width: 100%;"
        />
        <div v-else class="text-[10px] text-slate-400 text-center py-2">
          近兩年資料不足，無法繪製趨勢圖
        </div>
      </div>

      <!-- 腎功能 eGFR / UACR 區塊（DKD 近兩年雙 Y 軸趨勢，仿 dashboard2）-->
      <div class="rounded-lg p-3 bg-slate-50 border border-slate-200">
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs font-semibold text-slate-600">🫘 腎功能 eGFR / UACR（近兩年）</span>
          <span v-if="data.ckd?.stage" class="text-xs px-1.5 rounded font-bold"
            :class="labBox(data.ckd.color) + ' ' + labText(data.ckd.color)">
            {{ data.ckd.stage }}
          </span>
        </div>

        <VChart
          v-if="hasRenalTrend"
          :option="renalChartOption"
          autoresize
          style="height: 130px; width: 100%;"
        />
        <div v-else class="text-[10px] text-slate-400 text-center py-2">
          近兩年腎功能資料不足，無法繪製趨勢圖
        </div>
      </div>

      <!-- 關鍵檢驗（腎/脂/肝）區塊：四欄，第一列腎功能 Cre/eGFR/UACR + KDIGO 燈號 -->
      <div v-if="data.labs?.length" class="rounded-lg p-3 bg-slate-50 border border-slate-200">
        <div class="text-xs font-semibold text-slate-600 mb-2">🧪 關鍵檢驗（最近值）</div>
        <div class="grid grid-cols-4 gap-1.5">

          <!-- 腎功能：Cre → eGFR → UACR -->
          <div
            v-for="l in renalLabs" :key="l.key"
            class="rounded-md border p-1.5 text-center"
            :class="labBox(l.status)"
            :title="labTitle(l)"
          >
            <div class="text-[10px] text-slate-500 truncate">{{ l.name }}</div>
            <div class="flex items-baseline justify-center gap-0.5 leading-tight flex-wrap">
              <span class="text-base font-bold" :class="labText(l.status)">{{ fmt(l.value) }}</span>
              <span v-if="deltaText(l)" class="text-[10px] font-medium" :class="labTrend(l)">{{ deltaText(l) }}</span>
              <span class="text-[9px] text-slate-400">{{ l.date?.slice(5) }}</span>
            </div>
          </div>

          <!-- KDIGO 分期燈號（由 eGFR + UACR 推算） -->
          <div
            v-if="data.ckd?.stage"
            class="rounded-md border p-1.5 flex flex-col items-center justify-center"
            :class="labBox(data.ckd.color)"
            title="KDIGO CKD 分期（eGFR×UACR）"
          >
            <div class="text-[10px] text-slate-500">KDIGO</div>
            <div class="text-base font-bold" :class="labText(data.ckd.color)">{{ data.ckd.stage }}</div>
          </div>

          <!-- 其餘檢驗：LDL / TG / HDL / GPT（往上補滿，省一列） -->
          <div
            v-for="l in otherLabs" :key="l.key"
            class="rounded-md border p-1.5 text-center"
            :class="labBox(l.status)"
            :title="labTitle(l)"
          >
            <div class="text-[10px] text-slate-500 truncate">{{ l.name }}</div>
            <div class="flex items-baseline justify-center gap-0.5 leading-tight flex-wrap">
              <span class="text-base font-bold" :class="labText(l.status)">{{ fmt(l.value) }}</span>
              <span v-if="deltaText(l)" class="text-[10px] font-medium" :class="labTrend(l)">{{ deltaText(l) }}</span>
              <span class="text-[9px] text-slate-400">{{ l.date?.slice(5) }}</span>
            </div>
          </div>
        </div>
      </div>

    </template>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, MarkLineComponent, LegendComponent])

const props = defineProps({ pid: { type: String, default: '' } })

// 腎功能（Cre/eGFR/UACR）與其餘檢驗分組
const RENAL_KEYS = ['creatinine', 'egfr', 'uacr']
const renalLabs = computed(() =>
  RENAL_KEYS.map(k => data.value?.labs?.find(l => l.key === k)).filter(Boolean))
const otherLabs = computed(() =>
  (data.value?.labs ?? []).filter(l => !RENAL_KEYS.includes(l.key)))

const data    = ref(null)
const loading = ref(false)
const error   = ref('')
const audit   = ref({ need_any: false, items: [] })

async function load() {
  if (!props.pid) return
  loading.value = true
  error.value   = ''
  try {
    const [m1Res, auditRes] = await Promise.all([
      fetch(`/api/dm-care/m1/${props.pid}`),
      fetch(`/api/dm-care/audit/${props.pid}`),
    ])
    const json = await m1Res.json()
    if (json.error) { error.value = json.error; data.value = null }
    else            { data.value = json }
    audit.value = await auditRes.json()
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

// pid 變化時自動重載
watch(() => props.pid, (v) => { if (v) load() }, { immediate: true })

// ── HbA1c 近兩年折線圖（仿 dashboard2，含 7.0 達標參考線）──
const a1cChartOption = computed(() => {
  const recs = [...(data.value?.hba1c?.records ?? [])].reverse() // 由舊到新
  return {
    grid: { top: 16, right: 12, bottom: 22, left: 28 },
    tooltip: {
      trigger: 'axis',
      formatter: (p) => `${p[0].axisValue}<br/>HbA1c <b>${p[0].data}%</b>`,
    },
    xAxis: {
      type: 'category',
      data: recs.map(r => r.date),                  // 完整日期（含年份）
      axisLabel: { fontSize: 9, color: '#94a3b8', formatter: (v) => v.slice(2, 7) }, // YY/MM
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { fontSize: 9, color: '#94a3b8' },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    series: [{
      type: 'line',
      data: recs.map(r => r.value),
      smooth: true,
      symbolSize: 6,
      lineStyle: { color: '#d62728', width: 2 },
      itemStyle: { color: '#d62728' },
      label: { show: true, fontSize: 9, color: '#64748b', formatter: '{c}' },
      markLine: {
        silent: true,
        symbol: 'none',
        data: [{ yAxis: 7.0 }],
        lineStyle: { type: 'dashed', color: '#16a34a', opacity: 0.6 },
        label: { formatter: '達標 7.0', fontSize: 9, color: '#16a34a', position: 'insideEndTop' },
      },
    }],
  }
})

// ── eGFR / UACR 近兩年雙 Y 軸圖（DKD，仿 dashboard2）──
// 對齊技巧：eGFR 軸 [0,120·s]、UACR 軸 [0,60·s]，使 eGFR 60 與 UACR 30
// 落在同一條基準線（高度 = 0.5/s）；s 隨資料放大避免被裁切。
const hasRenalTrend = computed(() => {
  const rt = data.value?.renal_trend
  return !!rt && ((rt.egfr?.length ?? 0) + (rt.uacr?.length ?? 0)) >= 2
})

const renalChartOption = computed(() => {
  const rt   = data.value?.renal_trend ?? { egfr: [], uacr: [] }
  const egfr = rt.egfr ?? []
  const uacr = rt.uacr ?? []
  const dates = [...new Set([...egfr, ...uacr].map(r => r.date))].sort()
  const eMap  = Object.fromEntries(egfr.map(r => [r.date, r.value]))
  const uMap  = Object.fromEntries(uacr.map(r => [r.date, r.value]))
  const uMax  = Math.max(60,  ...uacr.map(r => r.value))
  const eMax  = Math.max(120, ...egfr.map(r => r.value))
  const scale = Math.max(1, uMax / 60, eMax / 120)
  return {
    grid: { top: 26, right: 34, bottom: 22, left: 32 },
    legend: { top: 0, right: 4, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 9, color: '#64748b' } },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { fontSize: 9, color: '#94a3b8', formatter: (v) => v.slice(2, 7) },
      axisTick: { show: false },
    },
    yAxis: [
      { type: 'value', name: 'eGFR', min: 0, max: Math.round(120 * scale), position: 'left',
        nameTextStyle: { fontSize: 9, color: '#16a34a' },
        axisLabel: { fontSize: 9, color: '#16a34a' },
        splitLine: { lineStyle: { color: '#f1f5f9' } } },
      { type: 'value', name: 'UACR', min: 0, max: Math.round(60 * scale), position: 'right',
        nameTextStyle: { fontSize: 9, color: '#f97316' },
        axisLabel: { fontSize: 9, color: '#f97316' },
        splitLine: { show: false } },
    ],
    series: [
      { name: 'eGFR', type: 'line', yAxisIndex: 0, connectNulls: true, smooth: true, symbolSize: 5,
        data: dates.map(d => eMap[d] ?? null),
        lineStyle: { color: '#16a34a', width: 2 }, itemStyle: { color: '#16a34a' },
        markLine: {
          silent: true, symbol: 'none',
          data: [{ yAxis: 60 }],            // eGFR 60＝UACR 30（同一基準線）
          lineStyle: { type: 'dashed', color: '#64748b', opacity: 0.7 },
          label: { formatter: 'eGFR 60 / UACR 30', fontSize: 9, color: '#64748b', position: 'insideStartTop' },
        },
      },
      { name: 'UACR', type: 'line', yAxisIndex: 1, connectNulls: true, smooth: true, symbolSize: 5,
        data: dates.map(d => uMap[d] ?? null),
        lineStyle: { color: '#f97316', width: 2 }, itemStyle: { color: '#f97316' } },
    ],
  }
})

// ── helpers ──────────────────────────────────────────────

// 把 "🚨 逾期365天 (上次 2025-06-21)" 縮成 "逾期365天"
function shortDetail(detail) {
  if (!detail) return ''
  const m = String(detail).match(/逾期(\d+)天/)
  if (m) return `逾期${m[1]}天`
  if (detail.includes('從未')) return '從未執行'
  return ''
}

function trendColor(t) {
  if (t === '↑') return 'text-red-500'
  if (t === '↓') return 'text-green-500'
  return 'text-slate-400'
}

// ── 關鍵檢驗 helpers ─────────────────────────────────────
function fmt(v) {
  if (v === null || v === undefined) return '—'
  return Number.isInteger(v) ? v : Math.round(v * 10) / 10
}

function labBox(s) {
  return {
    green: 'bg-green-50 border-green-200',
    amber: 'bg-yellow-50 border-yellow-200',
    red:   'bg-red-50 border-red-200',
  }[s] || 'bg-white border-slate-200'
}

function labText(s) {
  return {
    green: 'text-green-700',
    amber: 'text-yellow-700',
    red:   'text-red-600',
  }[s] || 'text-slate-700'
}

// 趨勢箭頭顏色：依「越高越差」決定 ↑ 是紅(壞)還是綠(好)
function labTrend(l) {
  if (l.trend === '↑') return l.higher_bad ? 'text-red-400' : 'text-green-500'
  if (l.trend === '↓') return l.higher_bad ? 'text-green-500' : 'text-red-400'
  return 'text-slate-300'
}

// 變化量：箭頭 + 絕對差值（例：↓0.2），讓使用者知道「升降多少」
function deltaText(l) {
  if (l.delta === null || l.delta === undefined || l.delta === 0) return ''
  const arrow = l.delta > 0 ? '↑' : '↓'
  return `${arrow}${Math.abs(l.delta)}`
}

// hover 顯示完整資訊（含前值與變化方向）
function labTitle(l) {
  const base = `${l.name}　${fmt(l.value)} ${l.unit}　${l.date}`
  if (l.delta === null || l.delta === undefined || l.delta === 0) return base
  const word = l.delta > 0 ? '上升' : '下降'
  return `${base}（較前值 ${fmt(l.prev)} ${word} ${Math.abs(l.delta)}）`
}
</script>
