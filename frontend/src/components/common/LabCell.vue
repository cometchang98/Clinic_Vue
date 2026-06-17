<template>
  <div class="flex flex-col items-center gap-0.5">
    <!-- 數值 -->
    <span
      class="font-semibold text-sm"
      :class="valColor"
    >{{ val !== null && val !== undefined ? val : '-' }}</span>
    <!-- 趨勢 -->
    <span v-if="trendIcon" class="text-xs leading-none" :class="trendColor">{{ trendIcon }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  val:       { default: null },
  trend:     { type: String, default: '' },
  target:    { type: Number, default: null },
  higherBad: { type: Boolean, default: true },
  color:     { type: String, default: 'slate' },
})

const valColor = computed(() => {
  if (props.val === null || props.val === undefined) return 'text-slate-300'
  if (props.target === null) return `text-${props.color}-600`
  const met = props.higherBad ? props.val < props.target : props.val >= props.target
  return met ? 'text-green-600' : 'text-red-500'
})

const trendIcon = computed(() => {
  const t = props.trend ?? ''
  if (t.startsWith('🔺')) return '↑'
  if (t.startsWith('🟢')) return '↓'
  if (t.startsWith('➖')) return '–'
  return ''
})

const trendColor = computed(() => {
  const t = props.trend ?? ''
  // 若 higherBad（數值越高越差），↑ 是壞的
  if (props.higherBad) {
    if (t.startsWith('🔺')) return 'text-red-400'
    if (t.startsWith('🟢')) return 'text-green-500'
  } else {
    if (t.startsWith('🔺')) return 'text-green-500'
    if (t.startsWith('🟢')) return 'text-red-400'
  }
  return 'text-slate-300'
})
</script>
