import { ref, computed } from 'vue'

export function useSortable(sourceRef) {
  const sortKey = ref('')
  const sortDir = ref(1)   // 1 = 升冪 ↑, -1 = 降冪 ↓

  function toggleSort(key) {
    if (sortKey.value === key) {
      sortDir.value *= -1
    } else {
      sortKey.value = key
      sortDir.value = 1
    }
  }

  function sortIcon(key) {
    if (sortKey.value !== key) return '⇅'
    return sortDir.value === 1 ? '↑' : '↓'
  }

  const sorted = computed(() => {
    if (!sortKey.value) return sourceRef.value
    const key = sortKey.value
    const dir = sortDir.value
    return [...sourceRef.value].sort((a, b) => {
      let va = a[key], vb = b[key]
      // null / undefined 永遠排最後
      if (va == null && vb == null) return 0
      if (va == null) return 1
      if (vb == null) return -1
      // 數字比較
      const na = parseFloat(va), nb = parseFloat(vb)
      if (!isNaN(na) && !isNaN(nb)) return (na - nb) * dir
      // 字串比較
      return String(va).localeCompare(String(vb), 'zh-TW') * dir
    })
  })

  return { sortKey, sortDir, toggleSort, sortIcon, sorted }
}
