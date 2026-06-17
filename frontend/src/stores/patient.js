import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const usePatientStore = defineStore('patient', () => {
  // 當前鎖定的病患（完整物件，來自 dashboard_data.json）
  const currentPatient = ref(null)

  const pid     = computed(() => currentPatient.value?.病歷號 ?? null)
  const name    = computed(() => currentPatient.value?.姓名 ?? null)
  const locked  = computed(() => !!currentPatient.value && !!pid.value && pid.value !== '無紀錄')
  const tags    = computed(() => currentPatient.value?.標籤 ?? '')
  const riskBadge = computed(() => currentPatient.value?.風險燈號 ?? '⚪')

  function lockPatient(patient) {
    // Zero-residue: 清空再設新病患
    currentPatient.value = null
    if (patient) {
      currentPatient.value = { ...patient }
    }
  }

  function unlock() {
    currentPatient.value = null
  }

  return { currentPatient, pid, name, locked, tags, riskBadge, lockPatient, unlock }
})
