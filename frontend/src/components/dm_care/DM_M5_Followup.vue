<template>
  <div class="bg-white rounded-xl border border-slate-200 p-4 space-y-3">

    <!-- 標頭 + 角色切換 -->
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold text-slate-700">📋 M5 追蹤 SOP · 衛教協作板</h3>
      <div class="flex items-center gap-2">
        <div class="flex rounded-md overflow-hidden border border-slate-200 text-[11px]">
          <button @click="role='doctor'"   :class="role==='doctor'   ? 'bg-indigo-600 text-white' : 'bg-white text-slate-500'" class="px-2 py-0.5">👨‍⚕️醫師</button>
          <button @click="role='educator'" :class="role==='educator' ? 'bg-emerald-600 text-white' : 'bg-white text-slate-500'" class="px-2 py-0.5">👩‍🏫衛教師</button>
        </div>
        <button @click="load" :disabled="loading" class="text-xs text-indigo-500 hover:text-indigo-700 disabled:opacity-40">{{ loading ? '…' : '🔄' }}</button>
      </div>
    </div>

    <div v-if="error" class="text-xs text-red-500 bg-red-50 rounded p-2">{{ error }}</div>
    <div v-else-if="loading && !data" class="text-xs text-slate-400 text-center py-4">載入中…</div>

    <template v-else-if="data">

      <!-- 檢查完成度 -->
      <div v-if="data.exams?.length" class="flex flex-wrap gap-1.5">
        <span
          v-for="e in data.exams" :key="e.key"
          class="px-2 py-0.5 rounded-full text-[11px] font-medium"
          :class="e.done ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
          :title="e.date"
        >{{ e.done ? '✅' : '⭕' }} {{ e.name }}{{ e.done && e.date ? ` (${shortDate(e.date)})` : '' }}</span>
      </div>
      <div v-else class="text-[11px] text-slate-400">（{{ data.exam_year }}年度檢查清單尚未建立）</div>

      <!-- 待衛教 checklist -->
      <div class="space-y-2">
        <div v-if="data.pending.length === 0" class="text-xs text-slate-400 text-center py-1">目前無待辦衛教項目</div>
        <div
          v-for="it in data.pending" :key="it.id"
          class="rounded-lg border border-slate-200 p-2.5"
        >
          <div class="flex items-center gap-2">
            <input type="checkbox" @change="complete(it)" class="w-4 h-4 accent-emerald-600 cursor-pointer" />
            <span class="text-sm font-medium text-slate-700">{{ it.topic }}</span>
            <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold"
              :class="it.requested_by==='doctor' ? 'bg-indigo-100 text-indigo-700' : 'bg-emerald-100 text-emerald-700'">
              {{ it.requested_by==='doctor' ? '醫師指派' : '衛教師' }}
            </span>
            <button @click="remove(it)" class="ml-auto text-slate-300 hover:text-red-500 text-xs">✕</button>
          </div>

          <!-- 雙人筆記（左醫師 / 右衛教師，條列式 4 行）-->
          <div class="mt-2 grid grid-cols-2 gap-2">
            <!-- 醫師欄 -->
            <div>
              <div class="flex items-center mb-0.5">
                <span class="text-[10px] font-semibold text-indigo-500">👨‍⚕️ 醫師筆記</span>
                <span v-if="it._saved==='doctor_note'" class="ml-1.5 text-[10px] text-green-500">✓ 已儲存</span>
              </div>
              <textarea
                v-model="it.doctor_note" @blur="saveNote(it,'doctor_note')"
                rows="4" placeholder="條列式，Enter 換行…"
                class="w-full text-xs px-2 py-1 rounded border border-slate-100 bg-slate-50 focus:bg-white focus:border-indigo-200 focus:outline-none resize-none leading-relaxed"
              />
            </div>
            <!-- 衛教師欄 -->
            <div>
              <div class="flex items-center mb-0.5">
                <span class="text-[10px] font-semibold text-emerald-500">👩‍🏫 衛教師筆記</span>
                <span v-if="it._saved==='educator_note'" class="ml-1.5 text-[10px] text-green-500">✓ 已儲存</span>
                <button @click="aiDraft(it)" :disabled="it._ai"
                  class="ml-auto text-[10px] text-purple-500 hover:text-purple-700 disabled:opacity-40 whitespace-nowrap">
                  {{ it._ai ? '生成中…' : '✨AI代寫' }}
                </button>
              </div>
              <textarea
                v-model="it.educator_note" @blur="saveNote(it,'educator_note')"
                rows="4" placeholder="條列式，Enter 換行…"
                class="w-full text-xs px-2 py-1 rounded border border-slate-100 bg-slate-50 focus:bg-white focus:border-emerald-200 focus:outline-none resize-none leading-relaxed"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 新增項目 -->
      <div class="rounded-lg bg-slate-50 border border-slate-200 p-2.5">
        <div class="flex flex-wrap gap-1 mb-1.5">
          <button
            v-for="t in data.suggested_topics" :key="t"
            @click="addItem(t)"
            class="px-2 py-0.5 rounded-full text-[11px] bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:text-indigo-600"
          >+ {{ t }}</button>
        </div>
        <div class="flex gap-1">
          <input v-model="customTopic" @keyup.enter="addItem(customTopic)" placeholder="自訂衛教主題…"
            class="flex-1 text-xs px-2 py-1 rounded border border-slate-200 focus:outline-none focus:border-indigo-300" />
          <button @click="addItem(customTopic)" :disabled="!customTopic.trim()"
            class="text-xs px-2 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40">新增</button>
        </div>
      </div>

      <!-- 下次回診 -->
      <div class="flex items-center gap-2 rounded-lg bg-slate-50 border border-slate-200 p-2.5">
        <span class="text-xs text-slate-600">🗓️ 下次回診</span>
        <input type="date" v-model="nextDate" class="text-xs px-2 py-1 rounded border border-slate-200 focus:outline-none" />
        <button @click="saveNextVisit" class="text-xs px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700">約定</button>
        <span v-if="data.next_visit" class="ml-auto text-[11px] text-slate-400">
          現約 {{ data.next_visit.visit_date }}（{{ data.next_visit.set_by==='doctor' ? '醫師' : '衛教師' }}定）
        </span>
      </div>

      <!-- 歷史（可折疊）-->
      <div v-if="data.history.length">
        <button @click="showHistory=!showHistory" class="text-xs text-slate-500 hover:text-slate-700">
          {{ showHistory ? '▼' : '▶' }} 衛教歷史（{{ data.history.length }}）
        </button>
        <div v-if="showHistory" class="mt-1.5 space-y-1">
          <div v-for="h in data.history" :key="h.id"
            class="flex items-center gap-2 text-[11px] text-slate-500 px-2 py-1 rounded bg-slate-50">
            <span>✅ {{ h.topic }}</span>
            <span class="text-slate-400">{{ h.completed_at }} · {{ h.completed_by==='doctor'?'醫師':'衛教師' }}</span>
            <span v-if="h.educator_note" class="truncate text-slate-400 max-w-[10rem]" :title="h.educator_note">「{{ h.educator_note }}」</span>
            <button @click="review(h)" class="ml-auto text-indigo-400 hover:text-indigo-600">↻複習</button>
          </div>
        </div>
      </div>

    </template>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({ pid: { type: String, default: '' } })

const data    = ref(null)
const loading = ref(false)
const error   = ref('')
const role    = ref('doctor')
const customTopic = ref('')
const nextDate    = ref('')
const showHistory = ref(false)

const API = '/api/dm-care/m5'

async function load() {
  if (!props.pid) return
  loading.value = true; error.value = ''
  try {
    const res = await fetch(`${API}/${props.pid}`)
    data.value = await res.json()
    if (data.value.next_visit) nextDate.value = data.value.next_visit.visit_date
  } catch (e) { error.value = String(e) }
  finally { loading.value = false }
}

watch(() => props.pid, (v) => { if (v) load() }, { immediate: true })

async function addItem(topic) {
  topic = (topic || '').trim()
  if (!topic) return
  await fetch(`${API}/${props.pid}/item`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, requested_by: role.value }),
  })
  customTopic.value = ''
  await load()
}

async function complete(it) {
  await fetch(`${API}/item/${it.id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'done', completed_by: role.value }),
  })
  await load()
}

async function saveNote(it, field) {
  await fetch(`${API}/item/${it.id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ [field]: it[field] }),
  })
  // 閃示「✓ 已儲存」約 2 秒
  it._saved = field
  setTimeout(() => { if (it._saved === field) it._saved = null }, 2000)
}

async function aiDraft(it) {
  it._ai = true
  try {
    const ctx = data.value?._ctx || ''
    const res = await fetch(`${API}/ai-note`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: it.topic, patient_context: ctx }),
    })
    const j = await res.json()
    if (j.ok) {
      it.educator_note = (it.educator_note ? it.educator_note + '\n' : '') + j.note
      await saveNote(it, 'educator_note')
    }
  } finally { it._ai = false }
}

async function review(h) {
  await fetch(`${API}/item/${h.id}/review`, { method: 'POST' })
  await load()
}

async function remove(it) {
  await fetch(`${API}/item/${it.id}`, { method: 'DELETE' })
  await load()
}

async function saveNextVisit() {
  if (!nextDate.value) return
  await fetch(`${API}/${props.pid}/next-visit`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ visit_date: nextDate.value, set_by: role.value }),
  })
  await load()
}

function shortDate(s) {
  return String(s).split(',')[0].trim().slice(0, 10)
}
</script>
