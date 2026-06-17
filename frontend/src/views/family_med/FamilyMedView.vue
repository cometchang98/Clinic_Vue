<template>
  <div class="p-6 space-y-6">
    <!-- 頁首 -->
    <div>
      <h2 class="text-xl font-bold text-slate-800">🏥 115年家醫個管總指揮中心</h2>
      <p class="text-sm text-slate-400 mt-0.5">品質獎勵金監控 · 推播管理 · 戰情分析</p>
    </div>

    <!-- 名單同步狀態 banner -->
    <div v-if="store.syncInfo" class="rounded-lg px-4 py-2 text-sm flex items-center gap-3"
         :class="store.syncInfo.syncing
           ? 'bg-amber-50 border border-amber-200 text-amber-800'
           : store.syncInfo.days_old >= 7
             ? 'bg-red-50 border border-red-200 text-red-700'
             : 'bg-green-50 border border-green-200 text-green-700'">
      <span v-if="store.syncInfo.syncing" class="animate-spin">⏳</span>
      <span v-else-if="store.syncInfo.days_old >= 7">⚠️</span>
      <span v-else>✅</span>
      <span v-if="store.syncInfo.syncing">
        名單正在背景更新中（上次更新：{{ store.syncInfo.last_sync }}，已 {{ store.syncInfo.days_old }} 天）⋯完成後將自動重新整理
      </span>
      <span v-else-if="store.syncInfo.days_old >= 7">
        名單距上次更新已 {{ store.syncInfo.days_old }} 天（{{ store.syncInfo.last_sync }}），建議手動刷新頁面觸發更新
      </span>
      <span v-else>
        名單同步正常，上次更新：{{ store.syncInfo.last_sync }}（{{ store.syncInfo.days_old }} 天前）
      </span>
    </div>

    <!-- 頂部統計卡 -->
    <div class="grid grid-cols-5 gap-4">
      <StatCard title="總收案會員"  :value="store.members.length"  color="indigo" />
      <StatCard title="糖尿病 DM"   :value="countByTag('糖尿病 (DM)')"   color="yellow" />
      <StatCard title="腎病 CKD"    :value="countByTag('初期慢性腎病 (CKD)')" color="sky" />
      <StatCard title="糖腎 DKD"    :value="countByTag('糖尿病合併腎病變 (DKD)')" color="red" />
      <StatCard
        title="當前名單預估獎金"
        :value="`$${store.totalBonus.toLocaleString()}`"
        color="green"
        sub="元"
      />
    </div>

    <!-- 分頁 -->
    <div class="border-b border-slate-200">
      <nav class="flex gap-1">
        <button
          v-for="tab in tabs" :key="tab.key"
          @click="activeTab = tab.key"
          class="px-4 py-2 text-sm font-medium rounded-t-lg transition-colors"
          :class="activeTab === tab.key
            ? 'bg-white border border-b-white border-slate-200 text-indigo-600 -mb-px'
            : 'text-slate-500 hover:text-slate-700'"
        >
          {{ tab.label }}
        </button>
      </nav>
    </div>

    <!-- 分頁內容 -->
    <MemberListTab  v-if="activeTab === 'list'"    />
    <AnalyticsTab   v-if="activeTab === 'charts'"  />
    <AlertsTab      v-if="activeTab === 'alerts'"  />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useFamilyMedStore } from '@/stores/familyMed'
import StatCard    from '@/components/common/StatCard.vue'
import MemberListTab from './tabs/MemberListTab.vue'
import AnalyticsTab  from './tabs/AnalyticsTab.vue'
import AlertsTab     from './tabs/AlertsTab.vue'

const store     = useFamilyMedStore()
const activeTab = computed({ get: () => store.activeTab, set: v => { store.activeTab = v } })

const tabs = [
  { key: 'list',   label: '📋 品質獎勵金監控與推播名冊' },
  { key: 'charts', label: '📊 全院戰情視覺分析' },
  { key: 'alerts', label: '🚨 貝蒂警報追殺清單' },
]

function countByTag(tag) {
  return store.members.filter(m => m.計畫類別?.includes(tag)).length
}

onMounted(() => store.fetchMembers())
</script>
