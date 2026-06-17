<template>
  <div class="space-y-4">
    <!-- 說明列 -->
    <div class="flex items-center gap-2 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-700">
      💡 點擊病人姓名，可直接跳轉到名冊分頁查看詳細資料與推播
    </div>

    <!-- 三欄警報 -->
    <div class="grid grid-cols-3 gap-4">
      <div v-for="group in alertGroups" :key="group.key"
        class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">

        <!-- 群組標題 -->
        <div class="px-4 py-3 border-b border-slate-100" :class="group.headerBg">
          <h3 class="font-bold text-slate-800">{{ group.title }}</h3>
          <p class="text-xs text-slate-500 mt-0.5">{{ group.desc }}</p>
        </div>

        <!-- 計數 -->
        <div class="px-4 py-3 flex items-end gap-1 border-b border-slate-100">
          <span class="text-4xl font-black" :class="group.countClass">{{ group.alerts.length }}</span>
          <span class="text-sm text-slate-400 mb-1">人未達標</span>
        </div>

        <!-- 清單 -->
        <div class="divide-y divide-slate-50 max-h-[480px] overflow-y-auto">
          <button
            v-for="item in group.alerts" :key="item.pid"
            @click="store.jumpToMember(item.pid)"
            class="w-full text-left px-4 py-2.5 hover:bg-indigo-50 transition-colors group"
          >
            <div class="flex items-center justify-between gap-2">
              <!-- 姓名 + 病歷號 -->
              <div>
                <span class="font-semibold text-slate-800 group-hover:text-indigo-700 transition-colors text-sm">
                  {{ item.name }}
                </span>
                <span class="ml-1.5 text-xs text-slate-400 font-mono">{{ item.pid }}</span>
              </div>
              <!-- 跳轉提示 -->
              <span class="text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity text-xs">
                查看 →
              </span>
            </div>
            <!-- 未達標項目 -->
            <div class="flex flex-wrap gap-1 mt-1">
              <span
                v-for="r in item.reasons" :key="r"
                class="px-1.5 py-0.5 text-xs rounded-full bg-red-50 text-red-600 font-medium"
              >{{ r }}</span>
            </div>
          </button>

          <!-- 無資料 -->
          <div v-if="!group.alerts.length"
            class="px-4 py-8 text-center text-sm text-green-600">
            🎉 全部達標！
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useFamilyMedStore } from '@/stores/familyMed'

const store = useFamilyMedStore()

function buildAlerts(filterTag, checks, excludeTag) {
  return store.members
    .filter(m => {
      if (!m.計畫類別?.includes(filterTag)) return false
      if (excludeTag && m.計畫類別?.includes(excludeTag)) return false
      return true
    })
    .map(m => {
      const reasons = checks
        .filter(c => {
          const v = m[c.key]
          return v == null || v === '未測' || parseFloat(v) >= c.target
        })
        .map(c => m[c.key] == null ? `缺 ${c.key}` : `${c.key}: ${m[c.key]}`)
      return { pid: m.病歷號, name: m.姓名, reasons }
    })
    .filter(item => item.reasons.length)
}

const alertGroups = computed(() => [
  {
    key: 'dm',
    title: '🟡 DM 警報',
    desc: '目標：HbA1c < 7.0 且 LDL < 100',
    headerBg: 'bg-amber-50',
    countClass: 'text-amber-600',
    alerts: buildAlerts('糖尿病 (DM)',
      [{ key: 'HbA1c', target: 7.0 }, { key: 'LDL', target: 100 }],
      '糖尿病合併腎病變 (DKD)'
    ),
  },
  {
    key: 'ckd',
    title: '🔵 CKD 警報',
    desc: '目標：LDL < 130 且 UACR < 30',
    headerBg: 'bg-sky-50',
    countClass: 'text-sky-600',
    alerts: buildAlerts('初期慢性腎病 (CKD)',
      [{ key: 'LDL', target: 130 }, { key: 'UACR', target: 30 }],
      '糖尿病合併腎病變 (DKD)'
    ),
  },
  {
    key: 'dkd',
    title: '🔴 DKD 警報（大魔王）',
    desc: '目標：HbA1c < 7.0, LDL < 100, UACR < 30',
    headerBg: 'bg-red-50',
    countClass: 'text-red-600',
    alerts: buildAlerts('糖尿病合併腎病變 (DKD)',
      [{ key: 'HbA1c', target: 7.0 }, { key: 'LDL', target: 100 }, { key: 'UACR', target: 30 }]
    ),
  },
])
</script>
