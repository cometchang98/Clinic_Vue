import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { familyMedApi } from '@/api'

export const useFamilyMedStore = defineStore('familyMed', () => {
  // ── 狀態 ──────────────────────────────────
  const members       = ref([])
  const loading       = ref(false)
  const searchKw      = ref('')
  const selectedTags  = ref([])
  const draftMessages = ref({})
  const bonusHistory  = ref([])
  const activeTab     = ref('list')   // 跨頁面控制用
  const highlightPid  = ref('')       // 警報超連結後要高亮的病歷號
  const syncInfo      = ref(null)     // { last_sync, days_old, syncing }

  // ── 計算屬性 ──────────────────────────────
  const filteredMembers = computed(() => {
    let list = members.value
    if (searchKw.value) {
      const kw = searchKw.value.toUpperCase()
      list = list.filter(m =>
        m.姓名?.includes(searchKw.value) ||
        m.身分證?.toUpperCase().includes(kw) ||
        m.病歷號?.toUpperCase().includes(kw)   // ← 加入病歷號搜尋
      )
    }
    if (selectedTags.value.length) {
      list = list.filter(m =>
        selectedTags.value.some(t => m.計畫類別?.includes(t))
      )
    }
    return list
  })

  const totalBonus = computed(() =>
    filteredMembers.value.reduce((sum, m) => {
      const b = parseInt(m.預估獎金 ?? 0)
      return sum + (isNaN(b) ? 0 : b)
    }, 0)
  )

  const allTags = computed(() => {
    const tagSet = new Set()
    members.value.forEach(m => m.計畫類別?.forEach(t => tagSet.add(t)))
    return [...tagSet].sort()
  })

  // ── 動作 ──────────────────────────────────
  async function fetchMembers(params) {
    loading.value = true
    try {
      const { data } = await familyMedApi.getMembers(params)
      // 後端現在回傳 { members: [...], sync: {...} }
      if (data?.members) {
        members.value = data.members
        syncInfo.value = data.sync
        // 若正在背景 sync，60 秒後自動重新拉取
        if (data.sync?.syncing) {
          setTimeout(() => fetchMembers(params), 60_000)
        }
      } else {
        // 相容舊格式（array）
        members.value = Array.isArray(data) ? data : []
      }
    } finally {
      loading.value = false
    }
  }

  async function fetchBonusHistory() {
    const { data } = await familyMedApi.getBonusHistory()
    bonusHistory.value = data
  }

  function setDraft(pid, text) { draftMessages.value[pid] = text }
  function getDraft(pid)        { return draftMessages.value[pid] ?? '' }

  // 警報超連結：切換到名冊分頁 + 搜尋該病歷號
  function jumpToMember(pid) {
    searchKw.value     = pid
    selectedTags.value = []
    highlightPid.value = pid
    activeTab.value    = 'list'
    // 3 秒後取消高亮
    setTimeout(() => { highlightPid.value = '' }, 3000)
  }

  return {
    members, loading, searchKw, selectedTags,
    draftMessages, bonusHistory, activeTab, highlightPid, syncInfo,
    filteredMembers, totalBonus, allTags,
    fetchMembers, fetchBonusHistory, setDraft, getDraft, jumpToMember,
  }
})
