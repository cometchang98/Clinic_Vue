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

      <!-- HbA1c 區塊 -->
      <div class="rounded-lg p-3 border"
        :class="{
          'bg-green-50 border-green-200':  data.hba1c?.status?.color === 'green',
          'bg-yellow-50 border-yellow-200': data.hba1c?.status?.color === 'yellow',
          'bg-red-50 border-red-200':      data.hba1c?.status?.color === 'red',
          'bg-slate-50 border-slate-200':  !data.hba1c?.status,
        }"
      >
        <div class="flex items-center justify-between mb-1.5">
          <span class="text-xs font-semibold text-slate-600">HbA1c</span>
          <span class="text-xs"
            :class="{
              'text-green-600':  data.hba1c?.status?.color === 'green',
              'text-yellow-600': data.hba1c?.status?.color === 'yellow',
              'text-red-600':    data.hba1c?.status?.color === 'red',
            }"
          >
            {{ data.hba1c?.status?.icon }} {{ data.hba1c?.status?.label }}
          </span>
        </div>

        <!-- 最新值 + 趨勢 -->
        <div class="flex items-baseline gap-2">
          <span class="text-2xl font-bold text-slate-800">
            {{ data.hba1c?.latest?.toFixed(1) ?? '—' }}%
          </span>
          <span class="text-lg" :class="trendColor(data.hba1c?.trend)">
            {{ data.hba1c?.trend }}
          </span>
          <span class="text-xs text-slate-400 ml-auto">
            {{ data.hba1c?.days_since != null ? `${data.hba1c.days_since} 天前` : '' }}
          </span>
        </div>

        <!-- 歷史趨勢條 -->
        <div v-if="data.hba1c?.records?.length" class="mt-2 flex gap-2">
          <div
            v-for="r in data.hba1c.records" :key="r.date"
            class="flex-1 text-center"
          >
            <div class="text-[10px] font-semibold"
              :class="hba1cColor(r.value)"
            >{{ r.value.toFixed(1) }}</div>
            <div class="text-[10px] text-slate-400">{{ r.date.slice(5) }}</div>
          </div>
        </div>
      </div>

      <!-- 空腹血糖區塊 -->
      <div class="rounded-lg p-3 bg-slate-50 border border-slate-200">
        <div class="flex items-center justify-between mb-1.5">
          <span class="text-xs font-semibold text-slate-600">空腹血糖 AC-Sugar（近 90 天）</span>
          <span class="text-xs"
            :class="{
              'text-red-600':    data.fasting_bg?.pattern?.color === 'red',
              'text-orange-600': data.fasting_bg?.pattern?.color === 'orange',
              'text-yellow-600': data.fasting_bg?.pattern?.color === 'yellow',
              'text-green-600':  data.fasting_bg?.pattern?.color === 'green',
              'text-slate-400':  data.fasting_bg?.pattern?.color === 'gray',
            }"
          >
            {{ data.fasting_bg?.pattern?.icon }} {{ data.fasting_bg?.pattern?.label }}
          </span>
        </div>

        <div v-if="data.fasting_bg?.records?.length" class="space-y-1">
          <!-- 統計列 -->
          <div class="flex gap-4 text-xs text-slate-600">
            <span>均值 <strong>{{ data.fasting_bg.avg_30d }}</strong></span>
            <span>最低 <strong :class="data.fasting_bg.min < 70 ? 'text-red-600' : ''">{{ data.fasting_bg.min }}</strong></span>
            <span>最高 <strong :class="data.fasting_bg.max > 180 ? 'text-orange-600' : ''">{{ data.fasting_bg.max }}</strong></span>
            <span class="ml-auto text-slate-400">共 {{ data.fasting_bg.records.length }} 筆</span>
          </div>

          <!-- 最近 8 筆血糖條形 -->
          <div class="flex items-end gap-1 h-10 mt-1">
            <div
              v-for="r in data.fasting_bg.records.slice(0,8).reverse()" :key="r.date"
              class="flex-1 rounded-t-sm"
              :style="{ height: barHeight(r.value) + 'px' }"
              :class="barColor(r.value)"
              :title="`${r.date} ${r.value}`"
            />
          </div>
          <div class="flex gap-1">
            <div
              v-for="r in data.fasting_bg.records.slice(0,8).reverse()" :key="r.date+'l'"
              class="flex-1 text-center text-[9px] text-slate-400"
            >{{ r.date.slice(8) }}/{{ r.date.slice(5,7) }}</div>
          </div>
        </div>

        <div v-else class="text-xs text-slate-400 text-center py-2">近 90 天無空腹血糖記錄</div>
      </div>

      <!-- 關鍵檢驗（腎/脂/肝）區塊 -->
      <div v-if="data.labs?.length" class="rounded-lg p-3 bg-slate-50 border border-slate-200">
        <div class="text-xs font-semibold text-slate-600 mb-2">🧪 關鍵檢驗（最近值）</div>
        <div class="grid grid-cols-3 gap-1.5">
          <div
            v-for="l in data.labs" :key="l.key"
            class="rounded-md border p-1.5 text-center"
            :class="labBox(l.status)"
            :title="`${l.name}　${fmt(l.value)} ${l.unit}　${l.date}`"
          >
            <div class="text-[10px] text-slate-500 truncate">{{ l.name }}</div>
            <div class="flex items-baseline justify-center gap-0.5 leading-tight">
              <span class="text-base font-bold" :class="labText(l.status)">{{ fmt(l.value) }}</span>
              <span v-if="l.unit" class="text-[9px] text-slate-400">{{ l.unit }}</span>
              <span v-if="l.trend && l.trend !== '→'" class="text-[10px]" :class="labTrend(l)">{{ l.trend }}</span>
            </div>
            <div class="text-[9px] text-slate-400">{{ l.date?.slice(5) }}</div>
          </div>
        </div>
      </div>

    </template>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'

const props = defineProps({ pid: { type: String, default: '' } })

const data    = ref(null)
const loading = ref(false)
const error   = ref('')

async function load() {
  if (!props.pid) return
  loading.value = true
  error.value   = ''
  try {
    const res = await fetch(`/api/dm-care/m1/${props.pid}`)
    const json = await res.json()
    if (json.error) { error.value = json.error; data.value = null }
    else            { data.value = json }
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

// pid 變化時自動重載
watch(() => props.pid, (v) => { if (v) load() }, { immediate: true })

// ── helpers ──────────────────────────────────────────────
function trendColor(t) {
  if (t === '↑') return 'text-red-500'
  if (t === '↓') return 'text-green-500'
  return 'text-slate-400'
}

function hba1cColor(v) {
  if (v < 7.0) return 'text-green-600'
  if (v < 9.0) return 'text-yellow-600'
  return 'text-red-600'
}

function barHeight(v) {
  // 正常 80-130，最高 300+；映射到 4~40px
  const clamp = Math.min(Math.max(v, 60), 350)
  return Math.round(4 + ((clamp - 60) / 290) * 36)
}

function barColor(v) {
  if (v < 70)  return 'bg-red-400'
  if (v > 180) return 'bg-orange-400'
  if (v > 140) return 'bg-yellow-300'
  return 'bg-green-400'
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
</script>
