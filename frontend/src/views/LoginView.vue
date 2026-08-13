<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Lock, User } from '@element-plus/icons-vue'
import api from '@/services/api'
import { setSession } from '@/stores/session'
import { portalLabel, portalLoginUrl, portalRole } from '@/portal'

const router = useRouter()
const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const loading = ref(false)
const agreements = ref<any>(null)
const agreementDialog = ref<'platform_rules' | 'privacy_policy' | null>(null)
const currentPortalLabel = portalRole ? portalLabel(portalRole) : '数字化经营平台'
const otherPortalRole = portalRole === 'merchant' ? 'operator' : 'merchant'
const otherPortalUrl = portalRole ? portalLoginUrl(otherPortalRole) : null
const registerForm = reactive({
  account_type: (portalRole || 'merchant') as 'merchant' | 'operator',
  username: '',
  display_name: '',
  password: '',
  confirm_password: '',
  invitation_code: '',
  accepted_rules: false,
  accepted_privacy: false,
})

async function submitLogin() {
  loading.value = true
  try {
    const result = await api.post('/auth/login', { username: username.value, password: password.value })
    if (portalRole && result.user.role !== portalRole) {
      await api.post('/auth/logout', null, { silentAuth: true })
      return ElMessage.error(`该账号请前往${portalLabel(result.user.role)}登录`)
    }
    setSession(result.user)
    router.push(
      result.user.must_change_password
        ? '/change-password'
        : (result.user.role === 'merchant' && !result.user.merchant_id ? '/onboarding' : '/overview'),
    )
  } finally {
    loading.value = false
  }
}

async function submitRegister() {
  if (registerForm.password !== registerForm.confirm_password) {
    return ElMessage.warning('两次输入的密码不一致')
  }
  if (!registerForm.accepted_rules || !registerForm.accepted_privacy) {
    return ElMessage.warning('请分别阅读并同意平台服务规则和隐私政策')
  }
  if (!agreements.value) return ElMessage.warning('协议版本加载失败，请刷新页面重试')
  loading.value = true
  try {
    const result = await api.post('/auth/register', {
      account_type: registerForm.account_type,
      username: registerForm.username,
      password: registerForm.password,
      display_name: registerForm.display_name,
      invitation_code: registerForm.account_type === 'operator' ? registerForm.invitation_code : null,
      accepted_rules: registerForm.accepted_rules,
      rules_version: agreements.value.platform_rules.version,
      accepted_privacy: registerForm.accepted_privacy,
      privacy_version: agreements.value.privacy_policy.version,
    })
    setSession(result.user)
    ElMessage.success(registerForm.account_type === 'merchant' ? '账号创建成功，请提交店铺入驻申请' : '账号创建成功')
    router.push(registerForm.account_type === 'merchant' ? '/onboarding' : '/overview')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  agreements.value = await api.get('/legal/agreements/current')
})
</script>

<template>
  <div class="login-page">
    <section class="story">
      <div class="story-inner">
        <div class="story-brand"><span class="mark"><DataAnalysis /></span><strong>万州商户通</strong></div>
        <div class="eyebrow">WANZHOU · DIGITAL BUSINESS</div>
        <h1>让每一家小店，<br /><em>看得见增长。</em></h1>
        <p>从经营数据到数字画像，从真实需求到适配资源，用一套轻量工具陪伴万州商户稳步向前。</p>
        <div class="feature-row">
          <div><b>6</b><span>样例商户</span></div><i></i>
          <div><b>45</b><span>天经营数据</span></div><i></i>
          <div><b>3</b><span>项智能推荐</span></div>
        </div>
      </div>
      <div class="ridge ridge-one"></div><div class="ridge ridge-two"></div>
    </section>
    <section class="login-panel">
      <div class="login-box" :class="{ registering: mode === 'register' }">
        <div class="mobile-brand"><span class="mark"><DataAnalysis /></span><strong>万州商户通</strong></div>
        <el-segmented v-model="mode" class="mode-switch" :options="[{ label: '账号登录', value: 'login' }, { label: '创建账号', value: 'register' }]" />

        <template v-if="mode === 'login'">
          <span class="welcome">{{ portalRole ? `${currentPortalLabel} · 欢迎回来` : '欢迎回来' }}</span>
          <h2>{{ portalRole === 'operator' ? '登录运营管理平台' : '登录数字化经营平台' }}</h2>
          <p class="hint">请输入{{ portalRole === 'operator' ? '管理人员' : portalRole === 'merchant' ? '商户' : '' }}账号和密码进入平台</p>
          <el-form label-position="top" @submit.prevent="submitLogin">
            <el-form-item label="登录账号"><el-input v-model="username" size="large" :prefix-icon="User" autocomplete="username" /></el-form-item>
            <el-form-item label="登录密码"><el-input v-model="password" size="large" show-password type="password" :prefix-icon="Lock" autocomplete="current-password" @keyup.enter="submitLogin" /></el-form-item>
            <el-button class="submit" type="primary" size="large" :loading="loading" @click="submitLogin">进入平台</el-button>
          </el-form>
          <a v-if="otherPortalUrl" class="portal-link" :href="otherPortalUrl">前往{{ portalLabel(otherPortalRole) }}</a>
        </template>

        <template v-else>
          <span class="welcome">账号注册</span>
          <h2>创建试运营账号</h2>
          <p class="hint">{{ registerForm.account_type === 'merchant' ? '先创建账号，登录后再提交店铺入驻申请' : '请使用有效邀请码创建管理人员账号' }}</p>
          <el-form label-position="top" @submit.prevent="submitRegister">
            <el-form-item v-if="!portalRole" label="账号类型">
              <el-radio-group v-model="registerForm.account_type" class="account-type">
                <el-radio-button value="merchant">商户账号</el-radio-button>
                <el-radio-button value="operator">管理人员账号</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-alert v-else class="portal-account-type" :closable="false" type="info" :title="`正在创建${currentPortalLabel}账号`" />
            <div class="register-grid">
              <el-form-item label="登录账号"><el-input v-model="registerForm.username" maxlength="50" autocomplete="username" placeholder="字母、数字、点、横线或下划线" /></el-form-item>
              <el-form-item :label="registerForm.account_type === 'merchant' ? '联系人姓名' : '姓名'"><el-input v-model="registerForm.display_name" maxlength="80" /></el-form-item>
            </div>
            <el-form-item v-if="registerForm.account_type === 'operator'" label="管理人员邀请码">
              <el-input v-model="registerForm.invitation_code" maxlength="100" show-password placeholder="由现有管理人员生成，24 小时内有效" />
            </el-form-item>
            <div class="register-grid">
              <el-form-item label="设置密码"><el-input v-model="registerForm.password" show-password type="password" autocomplete="new-password" /></el-form-item>
              <el-form-item label="确认密码"><el-input v-model="registerForm.confirm_password" show-password type="password" autocomplete="new-password" @keyup.enter="submitRegister" /></el-form-item>
            </div>
            <p class="password-rule">密码由8-32位数字、字母或符号组成，至少含有2种及以上的字符</p>
            <div class="agreements">
              <el-checkbox v-model="registerForm.accepted_rules">
                我已阅读并同意
                <button type="button" @click.prevent="agreementDialog='platform_rules'">《平台服务规则》</button>
              </el-checkbox>
              <el-checkbox v-model="registerForm.accepted_privacy">
                我已阅读并同意
                <button type="button" @click.prevent="agreementDialog='privacy_policy'">《隐私政策》</button>
              </el-checkbox>
            </div>
            <el-button class="submit" type="primary" size="large" :loading="loading" @click="submitRegister">{{ registerForm.account_type === 'merchant' ? '创建账号，下一步' : '创建并进入平台' }}</el-button>
          </el-form>
        </template>
        <p class="safe">试运营平台 · 请妥善保管账号与密码</p>
      </div>
    </section>
    <el-dialog
      :model-value="!!agreementDialog"
      :title="agreementDialog && agreements?.[agreementDialog]?.title"
      width="min(560px, calc(100% - 32px))"
      @close="agreementDialog=null"
    >
      <p class="agreement-version">版本：{{ agreementDialog && agreements?.[agreementDialog]?.version }}</p>
      <p class="agreement-content">{{ agreementDialog && agreements?.[agreementDialog]?.content }}</p>
      <template #footer><el-button type="primary" @click="agreementDialog=null">我已阅读</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; grid-template-columns: 1.1fr .9fr; background: #fff; }
.story { position: relative; overflow: hidden; background: radial-gradient(circle at 80% 10%,rgba(47,158,147,.35),transparent 31%), linear-gradient(145deg,#082d2c,#0d5752); color: #fff; display: flex; align-items: center; }
.story-inner { position: relative; z-index: 3; max-width: 660px; padding: 70px 11%; }
.story-brand { display: flex; align-items: center; gap: 12px; font-size: 19px; }
.mark { display: grid; place-items: center; width: 40px; height: 40px; padding: 9px; border-radius: 11px; background: #1b9589; color: #fff; }
.eyebrow { margin-top: 90px; color: #8fd1ca; font-size: 11px; letter-spacing: 3px; }
h1 { margin: 24px 0 25px; font-size: clamp(42px,4vw,66px); line-height: 1.15; letter-spacing: -2px; }
h1 em { font-style: normal; color: #f5ae6c; }
.story p { color: rgba(255,255,255,.66); line-height: 1.9; max-width: 510px; }
.feature-row { margin-top: 56px; display: flex; align-items: center; gap: 25px; }
.feature-row div { display: flex; flex-direction: column; }
.feature-row b { font-size: 25px; }
.feature-row span { font-size: 11px; margin-top: 4px; color: rgba(255,255,255,.48); }
.feature-row i { width: 1px; height: 34px; background: rgba(255,255,255,.15); }
.ridge { position: absolute; width: 650px; height: 250px; border-radius: 50%; border: 1px solid rgba(255,255,255,.07); transform: rotate(-12deg); right: -180px; bottom: -120px; }
.ridge-two { width: 800px; height: 320px; right: -280px; bottom: -190px; }
.login-panel { display: grid; place-items: center; padding: 60px; }
.login-box { width: min(410px,100%); }
.login-box.registering { width: min(520px,100%); padding: 28px 0; }
.mobile-brand { display: none; }
.mode-switch { width: 100%; margin-bottom: 28px; }
.welcome { color: var(--brand); font-size: 13px; font-weight: 700; }
h2 { margin: 11px 0 8px; font-size: 27px; letter-spacing: -.5px; }
.hint { margin: 0 0 28px; color: var(--muted); font-size: 13px; }
.account-type { width: 100%; }
.account-type :deep(.el-radio-button) { flex: 1; }
.account-type :deep(.el-radio-button__inner) { width: 100%; }
.register-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.register-grid :deep(.el-select) { width: 100%; }
.password-rule { margin: -5px 0 13px; color: var(--muted); font-size: 11px; line-height: 1.6; }
.agreements{display:flex;flex-direction:column;align-items:flex-start;margin:0 0 12px}.agreements :deep(.el-checkbox){height:25px}.agreements button{padding:0;border:0;background:none;color:var(--brand);cursor:pointer}.agreement-version{color:var(--muted);font-size:12px}.agreement-content{white-space:pre-wrap;line-height:1.9;color:#435351}
.submit { width: 100%; height: 48px; margin-top: 4px; border-radius: 10px; }
.portal-link { display: block; margin-top: 18px; text-align: center; color: var(--brand); font-size: 12px; text-decoration: none; }
.portal-link:hover { text-decoration: underline; }
.portal-account-type { margin-bottom: 18px; }
.safe { text-align: center; margin: 25px 0 0; color: #a0aaa9; font-size: 11px; }
:deep(.el-form-item__label) { font-size: 12px; font-weight: 600; color: #465655; }
@media (max-width: 900px) {
  .login-page { display: block; background: linear-gradient(155deg,#f2faf8,#fff 35%); padding: 24px; }
  .story { display: none; }
  .login-panel { min-height: calc(100vh - 48px); padding: 25px 0; }
  .mobile-brand { display: flex; align-items: center; gap: 10px; font-size: 18px; margin-bottom: 50px; }
  .login-box.registering .mobile-brand { margin-bottom: 24px; }
  .register-grid { grid-template-columns: 1fr; gap: 0; }
}
</style>
