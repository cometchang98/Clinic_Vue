<template>
  <div class="card text-center" :class="`border-t-4 border-${color}-400`">
    <p class="text-xs text-slate-500 font-semibold mb-2">{{ title }}</p>
    <p class="text-3xl font-black" :class="`text-${color}-600`">{{ value }}</p>
    <p v-if="sub" class="text-xs text-slate-400 mt-1">{{ sub }}</p>
  </div>
</template>

<script setup>
defineProps({
  title: String,
  value: [String, Number],
  sub:   String,
  color: { type: String, default: 'indigo' },
})
</script>
