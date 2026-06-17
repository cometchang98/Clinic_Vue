<template>
  <div class="p-5 max-w-5xl mx-auto">

    <!-- 頁首 -->
    <div class="mb-4">
      <h1 class="text-xl font-bold text-slate-800">🩺 病患工作站 · DM Care</h1>
      <p class="text-sm text-slate-400 mt-0.5">數值概覽 · 用藥分析 · 達標與健保防呆（依當前鎖定病患動態組裝）</p>
    </div>

    <!-- 未鎖定病患 -->
    <div v-if="!patientStore.locked" class="mt-20 text-center">
      <div class="text-5xl mb-3">👈</div>
      <p class="text-slate-400">請從左側名單點選病患，或用搜尋框鎖定病患</p>
    </div>

    <!-- 已鎖定 → 組裝卡片 -->
    <div v-else class="space-y-4">

      <!-- 病患標頭 -->
      <div class="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-4">
        <div class="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center text-xl">
          {{ patientStore.riskBadge.split(' ')[0] }}
        </div>
        <div>
          <div class="text-lg font-bold text-slate-800">
            {{ patientStore.name }}
            <span class="ml-2 text-sm text-slate-400 font-normal">{{ patientStore.pid }}</span>
          </div>
          <div v-if="patientStore.tags" class="text-xs text-slate-400 mt-0.5">{{ patientStore.tags }}</div>
        </div>
      </div>

      <!-- DM Care 三卡（M1 / M2 / M3）-->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <DM_M1_Overview :pid="patientStore.pid" />
        <DM_M3_Targets  :pid="patientStore.pid" />
        <div class="lg:col-span-2">
          <DM_M2_Meds :pid="patientStore.pid" />
        </div>
        <div class="lg:col-span-2">
          <DM_M5_Followup :pid="patientStore.pid" />
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { usePatientStore } from '@/stores/patient'
import DM_M1_Overview from '@/components/dm_care/DM_M1_Overview.vue'
import DM_M2_Meds     from '@/components/dm_care/DM_M2_Meds.vue'
import DM_M3_Targets  from '@/components/dm_care/DM_M3_Targets.vue'
import DM_M5_Followup from '@/components/dm_care/DM_M5_Followup.vue'

const patientStore = usePatientStore()
</script>
