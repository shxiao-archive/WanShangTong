<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElNotification } from 'element-plus'
import {
  Bell, DataAnalysis, Fold, Goods, Histogram, House, Key, List, Menu as MenuIcon,
  Promotion, Shop, SwitchButton, Ticket, UserFilled,
} from '@element-plus/icons-vue'
import api from '@/services/api'
import { logoutSession, session } from '@/stores/session'
import type { Merchant } from '@/types'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const merchants = ref<Merchant[]>([])
const mobileNav = ref<HTMLElement | null>(null)
const pendingCount = ref(0)
const onboardingPendingCount = ref(0)
const inviteDialog = ref(false)
const inviteLoading = ref(false)
const invitationCode = ref('')
const invitationExpiresAt = ref('')
let summaryTimer: number | undefined
const baseDocumentTitle = document.title
const isOperator = computed(() => session.user?.role === 'operator')
const showMerchantSwitch = computed(
  () => isOperator.value && ['/store', '/analytics', '/portrait'].includes(route.path),
)
const nav = computed(() => [
  { path: '/overview', label: '工作台', icon: House },
  ...(isOperator.value ? [{ path: '/merchants', label: '商户管理', icon: List, badge: onboardingPendingCount.value }] : []),
  { path: '/store', label: isOperator.value ? '商户档案' : '我的店铺', icon: Shop },
  { path: '/analytics', label: '经营分析', icon: Histogram },
  { path: '/portrait', label: '商户画像', icon: UserFilled },
  ...(!isOperator.value ? [{ path: '/recommendations', label: '资源推荐', icon: Promotion }] : []),
  { path: '/applications', label: isOperator.value ? '服务跟进' : '我的申请', icon: Bell, badge: pendingCount.value },
  ...(isOperator.value ? [{ path: '/resources', label: '资源管理', icon: Goods }] : []),
])

async function loadApplicationSummary() {
  const result = await api.get('/service-applications/summary')
  pendingCount.value = isOperator.value ? result.pending_count : result.active_count
}

function onboardingSeenKey() {
  return `wst_onboarding_seen_${session.user?.id || 'operator'}`
}

function loadSeenOnboardingSignatures(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(onboardingSeenKey()) || '[]')
    return Array.isArray(value) ? value.filter(item => typeof item === 'string') : []
  } catch {
    return []
  }
}

async function loadOnboardingSummary() {
  if (!isOperator.value) return
  const result = await api.get('/merchant-onboarding/summary')
  const previousCount = onboardingPendingCount.value
  onboardingPendingCount.value = result.pending_count
  document.title = result.pending_count
    ? `(${result.pending_count}) ${baseDocumentTitle}`
    : baseDocumentTitle

  const seen = new Set(loadSeenOnboardingSignatures())
  const current = result.latest.map((item: any) => ({
    ...item,
    signature: `${item.id}:${item.submitted_at || ''}`,
  }))
  const newItems = current.filter((item: any) => !seen.has(item.signature))
  if (newItems.length) {
    const first = newItems[0]
    ElNotification({
      title: '新的商户入驻申请',
      message: newItems.length === 1
        ? `“${first.merchant_name}”已提交入驻资料，点击前往审核`
        : `有 ${newItems.length} 份新的入驻申请，点击前往审核`,
      type: 'warning',
      duration: 10_000,
      onClick: () => router.push('/merchants'),
    })
  }
  const signatures = Array.from(new Set([
    ...current.map((item: any) => item.signature),
    ...seen,
  ])).slice(0, 100)
  localStorage.setItem(onboardingSeenKey(), JSON.stringify(signatures))
  if (previousCount !== result.pending_count || newItems.length) {
    window.dispatchEvent(new CustomEvent('wst:onboarding-changed'))
  }
}

async function refreshSummaries() {
  await Promise.allSettled([
    loadApplicationSummary(),
    loadOnboardingSummary(),
  ])
}

function requestOnboardingSummaryRefresh() {
  void loadOnboardingSummary().catch(() => undefined)
}

onMounted(async () => {
  window.addEventListener('wst:onboarding-refresh', requestOnboardingSummaryRefresh)
  if (isOperator.value) {
    const result = await api.get('/merchants', { params: { page_size: 100, status: 'enabled' } })
    merchants.value = result.items
    if (!session.selectedMerchantId && merchants.value[0]) session.selectedMerchantId = merchants.value[0].id
  }
  await refreshSummaries()
  summaryTimer = window.setInterval(refreshSummaries, 30_000)
})
onBeforeUnmount(() => {
  window.clearInterval(summaryTimer)
  window.removeEventListener('wst:onboarding-refresh', requestOnboardingSummaryRefresh)
  document.title = baseDocumentTitle
})

watch(() => route.path, async () => {
  await nextTick()
  mobileNav.value?.querySelector<HTMLElement>('.active')?.scrollIntoView({
    behavior: 'smooth',
    block: 'nearest',
    inline: 'center',
  })
}, { immediate: true })

async function logout() {
  await logoutSession()
  router.push('/login')
}
async function createOperatorInvite() {
  if (inviteLoading.value) return
  inviteLoading.value = true
  try {
    const result = await api.post('/auth/operator-invites')
    invitationCode.value = result.invitation_code
    invitationExpiresAt.value = result.expires_at
    inviteDialog.value = true
  } finally {
    inviteLoading.value = false
  }
}
async function copyInvitationCode() {
  await navigator.clipboard.writeText(invitationCode.value)
  ElMessage.success('邀请码已复制')
}
function userCommand(command: string) {
  if (command === 'password') router.push('/change-password')
  if (command === 'invite') createOperatorInvite()
  if (command === 'logout') logout()
}
</script>

<template>
  <div class="shell">
    <aside class="side" :class="{ collapsed }">
      <div class="brand">
        <div class="brand-mark"><DataAnalysis /></div>
        <div v-if="!collapsed" class="brand-copy"><strong>万州商户通</strong><span>数字化经营助手</span></div>
      </div>
      <nav class="nav">
        <router-link v-for="item in nav" :key="item.path" :to="item.path" class="nav-item" :class="{ active: route.path === item.path }">
          <el-icon><component :is="item.icon" /></el-icon>
          <span v-if="!collapsed">{{ item.label }}</span>
          <span v-if="item.badge" class="nav-badge">{{ item.badge > 99 ? '99+' : item.badge }}</span>
        </router-link>
      </nav>
      <button class="collapse" @click="collapsed = !collapsed">
        <el-icon><Fold v-if="!collapsed" /><MenuIcon v-else /></el-icon>
        <span v-if="!collapsed">收起菜单</span>
      </button>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="crumb">
          <span>万州商户数字化服务平台</span>
          <span class="env">试运营</span>
        </div>
        <div class="top-actions">
          <el-select
            v-if="showMerchantSwitch"
            v-model="session.selectedMerchantId"
            class="merchant-switch"
            placeholder="选择当前商户"
            filterable
          >
            <el-option v-for="merchant in merchants" :key="merchant.id" :label="merchant.name" :value="merchant.id" />
          </el-select>
          <el-dropdown trigger="click" @command="userCommand">
            <button class="user-menu">
              <span class="avatar">{{ session.user?.display_name.slice(0, 1) }}</span>
              <span class="user-copy"><strong>{{ session.user?.display_name }}</strong><small>{{ isOperator ? '运营人员' : '商户用户' }}</small></span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="password" :icon="Key">修改密码</el-dropdown-item>
                <el-dropdown-item v-if="isOperator" command="invite" :icon="Ticket">生成管理邀请码</el-dropdown-item>
                <el-dropdown-item command="logout" :icon="SwitchButton" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      <router-view :key="`${route.path}-${session.selectedMerchantId}`" />
    </main>

    <nav ref="mobileNav" class="mobile-nav" aria-label="移动端主导航">
      <router-link v-for="item in nav" :key="item.path" :to="item.path" :class="{ active: route.path === item.path }">
        <span class="mobile-icon"><el-icon><component :is="item.icon" /></el-icon><i v-if="item.badge" class="mobile-badge">{{ item.badge > 99 ? '99+' : item.badge }}</i></span><span>{{ item.label.slice(0, 4) }}</span>
      </router-link>
    </nav>

    <el-dialog v-model="inviteDialog" title="管理人员邀请码" width="460px" :close-on-click-modal="false">
      <el-alert type="warning" :closable="false" title="邀请码仅在本次显示，24 小时内有效，成功注册一次后立即失效。" />
      <div class="invitation-code">
        <code>{{ invitationCode }}</code>
        <el-button type="primary" plain @click="copyInvitationCode">复制</el-button>
      </div>
      <p class="invitation-expiry">有效期至：{{ invitationExpiresAt ? new Date(invitationExpiresAt).toLocaleString('zh-CN', { hour12: false }) : '' }}</p>
    </el-dialog>
  </div>
</template>

<style scoped>
.shell { min-height: 100vh; }
.side { width: 232px; position: fixed; z-index: 30; inset: 0 auto 0 0; background: #0b302f; color: #fff; transition: width .2s; display: flex; flex-direction: column; }
.side.collapsed { width: 76px; }
.brand { height: 76px; padding: 0 20px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid rgba(255,255,255,.08); overflow: hidden; }
.brand-mark { width: 36px; height: 36px; flex: 0 0 36px; display: grid; place-items: center; border-radius: 10px; background: #1e968b; color: #fff; }
.brand-mark :deep(svg) { width: 21px; }
.brand-copy { white-space: nowrap; display: flex; flex-direction: column; gap: 3px; }
.brand-copy strong { font-size: 17px; letter-spacing: .5px; }
.brand-copy span { font-size: 10px; color: rgba(255,255,255,.55); letter-spacing: 2px; }
.nav { padding: 18px 12px; flex: 1; }
.nav-item { height: 46px; margin-bottom: 6px; border-radius: 10px; color: rgba(255,255,255,.68); display: flex; align-items: center; gap: 13px; padding: 0 16px; text-decoration: none; font-size: 14px; white-space: nowrap; overflow: hidden; }
.nav-item:hover { background: rgba(255,255,255,.06); color: #fff; }
.nav-item.active { color: #fff; background: linear-gradient(100deg,#14867d,#16776f); box-shadow: 0 8px 20px rgba(0,0,0,.16); }
.nav-item .el-icon { font-size: 18px; flex: 0 0 auto; }
.nav-badge{margin-left:auto;min-width:19px;height:19px;padding:0 5px;border-radius:10px;display:grid;place-items:center;background:#e77c45;color:#fff;font-size:10px}
.collapse { margin: 12px; height: 42px; border: 0; border-top: 1px solid rgba(255,255,255,.08); background: transparent; color: rgba(255,255,255,.55); display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; white-space: nowrap; }
.main { margin-left: 232px; min-height: 100vh; transition: margin .2s; }
.collapsed + .main { margin-left: 76px; }
.topbar { height: 76px; position: sticky; z-index: 20; top: 0; padding: 0 30px; display: flex; align-items: center; justify-content: space-between; background: rgba(255,255,255,.9); border-bottom: 1px solid #e9eeee; backdrop-filter: blur(16px); }
.crumb { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 10px; }
.env { font-size: 10px; font-weight: 500; border: 1px solid #bcded9; background: #edf8f6; color: #16766e; padding: 3px 7px; border-radius: 5px; }
.top-actions { display: flex; align-items: center; gap: 10px; }
.merchant-switch { width: 210px; margin-right: 10px; }
.avatar { width: 36px; height: 36px; border-radius: 11px; background: #d8efe9; color: #0b766f; display: grid; place-items: center; font-weight: 700; }
.user-menu{border:0;background:transparent;padding:0;display:flex;align-items:center;gap:10px;cursor:pointer;text-align:left;color:inherit}.user-copy { display: flex; flex-direction: column; min-width: 65px; }
.user-copy strong { font-size: 13px; }
.user-copy small { font-size: 10px; color: #8b9796; margin-top: 3px; }
.invitation-code{margin-top:20px;display:flex;align-items:center;gap:10px}.invitation-code code{min-width:0;flex:1;padding:14px;border-radius:10px;background:#f3f6f5;overflow-wrap:anywhere;font-size:13px}.invitation-expiry{margin:10px 0 0;color:var(--muted);font-size:12px}
.mobile-nav { display: none; }
@media (max-width: 900px) {
  .side { display: none; }
  .main, .collapsed + .main { margin-left: 0; }
  .topbar { height: 64px; padding: 0 16px; }
  .crumb span:first-child, .user-copy, .top-actions > .el-button span { display: none; }
  .merchant-switch { width: 160px; margin-right: 0; }
  .mobile-nav { display: flex; position: fixed; z-index: 40; inset: auto 0 0; height: 72px; padding: 0 6px env(safe-area-inset-bottom); background: rgba(255,255,255,.96); border-top: 1px solid #e5ecea; justify-content: flex-start; align-items: center; overflow-x: auto; overflow-y: hidden; scroll-snap-type: x proximity; scroll-padding-inline: 8px; overscroll-behavior-x: contain; touch-action: pan-x; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
  .mobile-nav::-webkit-scrollbar { display: none; }
  .mobile-nav a { color: #81908f; display: flex; flex: 0 0 22%; min-width: 72px; scroll-snap-align: center; flex-direction: column; align-items: center; gap: 4px; text-decoration: none; font-size: 10px; }
  .mobile-nav a .el-icon { font-size: 26px; }
  .mobile-nav a.active { color: var(--brand); font-weight: 700; }
  .mobile-icon{position:relative;width:34px;height:28px;display:grid;place-items:center;color:var(--brand)}
  .mobile-icon .el-icon{color:var(--brand)}
  .mobile-icon .mobile-badge{position:absolute;z-index:2;right:-2px;top:-4px;min-width:14px;height:14px;box-sizing:border-box;padding:0 3px;border:1.5px solid #fff;border-radius:8px;background:#e77c45;color:#fff;font-size:7px;line-height:1;font-style:normal;font-weight:600;display:grid;place-items:center}
}
@media (max-width: 420px) {
  .merchant-switch { width: 135px; }
  .top-actions { gap: 6px; }
}
</style>
