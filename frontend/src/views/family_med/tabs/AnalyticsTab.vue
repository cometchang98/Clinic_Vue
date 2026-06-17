<template>
  <div class="space-y-6">
    <!-- 獎金趨勢 -->
    <div class="card">
      <h3 class="text-sm font-semibold text-slate-700 mb-4">💰 全院品質獎勵金成長趨勢</h3>
      <div v-if="store.bonusHistory.length" class="flex items-start gap-8">
        <div>
          <p class="text-3xl font-black text-amber-600">
            ${{ latestBonus.toLocaleString() }}
          </p>
          <p class="text-xs text-slate-400 mt-1">{{ deltaText }}</p>
        </div>
        <div class="flex-1 h-40">
          <VChart :option="bonusTrendOption" autoresize />
        </div>
      </div>
      <p v-else class="text-sm text-slate-400">⏳ 尚無歷史快照資料</p>
    </div>

    <!-- 燈號分布 & 達標率 -->
    <div class="grid grid-cols-2 gap-4">
      <div class="card">
        <h3 class="text-sm font-semibold text-slate-700 mb-4">🏆 品質燈號分佈</h3>
        <div class="h-52">
          <VChart :option="lightPieOption" autoresize />
        </div>
      </div>
      <div class="card">
        <h3 class="text-sm font-semibold text-slate-700 mb-4">🎯 三大指標達標率</h3>
        <div class="h-52">
          <VChart :option="targetBarOption" autoresize />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useFamilyMedStore } from '@/stores/familyMed'

use([CanvasRenderer, LineChart, PieChart, BarChart, GridComponent, TooltipComponent, LegendComponent])

const store = useFamilyMedStore()
onMounted(() => store.fetchBonusHistory())

const latestBonus = computed(() => {
  if (!store.bonusHistory.length) return 0
  return store.bonusHistory.at(-1)?.全院預估總獎金 ?? 0
})

const deltaText = computed(() => {
  const h = store.bonusHistory
  if (h.length < 2) return '尚無上週數據'
  const delta = h.at(-1).全院預估總獎金 - h.at(-2).全院預估總獎金
  return `較上次 ${delta >= 0 ? '+' : ''}${delta.toLocaleString()} 元`
})

const bonusTrendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis:   { type: 'category', data: store.bonusHistory.map(r => r.日期) },
  yAxis:   { type: 'value' },
  series:  [{ data: store.bonusHistory.map(r => r.全院預估總獎金), type: 'line', smooth: true,
              itemStyle: { color: '#f59e0b' }, areaStyle: { color: '#fef3c7' } }],
  grid:    { left: 40, right: 10, top: 10, bottom: 20 },
}))

// 燈號圓餅
const lightPieOption = computed(() => {
  const counts = {}
  store.filteredMembers.forEach(m => {
    const k = m.品質燈號 ?? '⚪ 未計算'
    counts[k] = (counts[k] ?? 0) + 1
  })
  const colorMap = {
    '🟢': '#22c55e', '🟡': '#eab308', '🟠': '#f97316', '🔴': '#ef4444', '⚪': '#cbd5e1',
  }
  return {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['45%', '70%'],
      data: Object.entries(counts).map(([name, value]) => ({
        name, value,
        itemStyle: { color: colorMap[name[0]] ?? '#94a3b8' }
      })),
      label: { fontSize: 11 },
    }],
  }
})

// 達標率長條
const targetBarOption = computed(() => {
  const ms = store.filteredMembers
  const rate = (key, target) => {
    const valid = ms.filter(m => m[key] != null && m[key] !== '未測')
    return valid.length ? (valid.filter(m => parseFloat(m[key]) < target).length / valid.length * 100).toFixed(1) : 0
  }
  return {
    tooltip: { trigger: 'axis', formatter: '{b}: {c}%' },
    xAxis: { type: 'category', data: ['HbA1c < 7.0', 'LDL < 100', 'UACR < 30'] },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    series: [{
      type: 'bar', barMaxWidth: 48,
      data: [
        { value: rate('HbA1c', 7.0),  itemStyle: { color: '#ec4899' } },
        { value: rate('LDL',   100),   itemStyle: { color: '#8b5cf6' } },
        { value: rate('UACR',  30),    itemStyle: { color: '#3b82f6' } },
      ],
      label: { show: true, position: 'top', formatter: '{c}%' },
    }],
    grid: { left: 40, right: 10, top: 30, bottom: 20 },
  }
})
</script>
