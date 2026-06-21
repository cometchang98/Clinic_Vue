import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/family-med',
  },
  {
    path: '/family-med',
    name: 'FamilyMed',
    component: () => import('@/views/family_med/FamilyMedView.vue'),
    meta: { title: '115年家醫個管總指揮中心' },
  },
  {
    path: '/plan-888',
    name: 'Plan888',
    component: () => import('@/views/Plan888View.vue'),
    meta: { title: '888 戰略指揮中心' },
  },
  {
    path: '/metabolic-recall',
    name: 'MetabolicRecall',
    component: () => import('@/views/metabolic_recall/MetabolicRecallView.vue'),
    meta: { title: '代謝症候群防治計畫' },
  },
  {
    path: '/consultation',
    name: 'Consultation',
    component: () => import('@/views/ConsultationView.vue'),
    meta: { title: '虛擬會診室' },
  },
  {
    path: '/data-mining',
    name: 'DataMining',
    component: () => import('@/views/DataMiningView.vue'),
    meta: { title: '雲端大數據探勘' },
  },
  {
    path: '/marketing',
    name: 'Marketing',
    component: () => import('@/views/MarketingView.vue'),
    meta: { title: '營運發想與群發' },
  },
  {
    path: '/nhi-audit',
    name: 'NhiAudit',
    component: () => import('@/views/NhiAuditView.vue'),
    meta: { title: '健保抽審與SOAP' },
  },
  {
    path: '/insulin-tracking',
    name: 'InsulinTracking',
    component: () => import('@/views/insulin_tracking/InsulinTrackingView.vue'),
    meta: { title: '胰島素追蹤滴定' },
  },
  {
    path: '/dm-care',
    name: 'DmCare',
    component: () => import('@/views/dm_care/PatientWorkspaceView.vue'),
    meta: { title: '病患工作站 DM Care' },
  },
  {
    path: '/educator',
    name: 'Educator',
    component: () => import('@/views/educator/EducatorView.vue'),
    meta: { title: '衛教師工作站' },
  },
  {
    path: '/vaccine',
    name: 'Vaccine',
    component: () => import('@/views/vaccine/VaccineView.vue'),
    meta: { title: '疫苗提醒（帶狀皰疹）' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(to => {
  document.title = `${to.meta.title ?? '凱程診所'} ｜ 凱程戰情室`
})

export default router
