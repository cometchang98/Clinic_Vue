<template>
  <span :class="badgeClass">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, required: true },  // '🟢 綠燈 (3項)' 等
})

const badgeClass = computed(() => {
  if (props.status.includes('🟢')) return 'badge-green'
  if (props.status.includes('🟡')) return 'badge-yellow'
  if (props.status.includes('🟠')) return 'badge-orange'
  if (props.status.includes('🔴')) return 'badge-red'
  return 'badge-gray'
})

const label = computed(() => props.status)
</script>
