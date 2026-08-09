<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElLoading, ElMessage, ElMessageBox } from 'element-plus'
import { Clock, DataAnalysis, Document, Refresh, SwitchButton, UploadFilled } from '@element-plus/icons-vue'
import api from '@/services/api'
import { logoutSession, session, updateSessionUser } from '@/stores/session'

type DocumentItem = {
  id: number
  document_type: string
  document_number: string
  original_name: string
  mime_type: string
  file_size: number
}

const router = useRouter()
const loading = ref(true)
const saving = ref(false)
const submitting = ref(false)
const uploadingType = ref('')
const application = ref<any>(null)
const agreements = ref<any>(null)
const currentStep = ref(0)
const highestReachedStep = ref(0)
const completedSteps = ref<Set<number>>(new Set())
const truthfulnessConfirmed = ref(false)
const acceptedRules = ref(false)
const acceptedPrivacy = ref(false)
const agreementDialog = ref<'platform_rules' | 'privacy_policy' | null>(null)
const previewUrl = ref('')
const previewDocument = ref<DocumentItem | null>(null)
const previewLoading = ref(false)
let refreshTimer: number | undefined

const steps = ['主体资质', '店铺资料', '联系授权', '行业许可', '预览提交']
const USCC_CHARSET = '0123456789ABCDEFGHJKLMNPQRTUWXY'
const USCC_WEIGHTS = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]
const relationshipOptions = [
  ['legal_representative', '法定代表人'],
  ['business_operator', '个体经营者'],
  ['store_manager', '店长'],
  ['authorized_agent', '授权经办人'],
]
const emptyForm = () => ({
  subject_type: null as 'enterprise' | 'individual_business' | null,
  legal_name: '',
  unified_social_credit_code: '',
  legal_representative: '',
  registered_address: '',
  business_scope: '',
  merchant_name: '',
  industry: null as '餐饮' | '零售' | '生活服务' | '住宿' | null,
  phone: '',
  address: '',
  business_hours: '09:00-21:00',
  contact_name: session.user?.display_name || '',
  contact_relationship: null as string | null,
  authorization_confirmed: false,
  scale: '小微',
  employee_count: 3,
  store_area: 60,
  network_environment: '普通宽带',
  bandwidth_mbps: 100,
  needs: [] as string[],
  retail_food_related: false,
  retail_food_credential_type: null as string | null,
  other_permit_required: false,
  other_permit_name: '',
  other_permit_number: '',
  additional_permits: [] as Array<{ name: string; number: string; document_id: number }>,
  current_step: 0,
})
const form = reactive(emptyForm())
const documents = computed<DocumentItem[]>(() => application.value?.documents || [])
const isEditable = computed(() => !application.value || ['draft', 'needs_changes'].includes(application.value.status))

function fillForm(value: any) {
  if (!value) return
  for (const key of Object.keys(form) as Array<keyof typeof form>) {
    if (value[key] !== undefined && value[key] !== null) (form as any)[key] = value[key]
  }
  highestReachedStep.value = Math.min(4, Math.max(0, value.current_step || 0))
  currentStep.value = highestReachedStep.value
  completedSteps.value = new Set(
    Array.from({ length: highestReachedStep.value }, (_, index) => index),
  )
}

function documentsOf(type: string) {
  return documents.value.filter(item => item.document_type === type)
}

function documentLabel(type: string) {
  return ({
    business_license: '营业执照',
    authorization_letter: '授权书',
    food_business_license: '食品经营许可证',
    prepackaged_food_filing: '仅销售预包装食品备案',
    accommodation_permit: '住宿行业许可或备案',
    other_permit: '其他行政许可',
  } as Record<string, string>)[type] || '资质材料'
}

function relationLabel(value: string | null) {
  return relationshipOptions.find(item => item[0] === value)?.[1] || '未填写'
}

function normalizeUscc(value: string) {
  return value.replace(/\s+/g, '').toUpperCase()
}

function normalizeUsccField() {
  form.unified_social_credit_code = normalizeUscc(form.unified_social_credit_code).slice(0, 18)
}

function validateUscc(value: string, subjectType: string | null) {
  const code = normalizeUscc(value)
  if (code.length !== 18) return '统一社会信用代码必须为18位'
  if ([...code].some(char => !USCC_CHARSET.includes(char))) {
    return '统一社会信用代码含有无效字符，请核对营业执照'
  }
  const expectedPrefix = subjectType === 'enterprise'
    ? ['91', '企业']
    : subjectType === 'individual_business'
      ? ['92', '个体工商户']
      : null
  if (expectedPrefix && !code.startsWith(expectedPrefix[0])) {
    return `${expectedPrefix[1]}的统一社会信用代码应以${expectedPrefix[0]}开头`
  }
  const total = [...code.slice(0, 17)].reduce(
    (sum, char, index) => sum + USCC_CHARSET.indexOf(char) * USCC_WEIGHTS[index],
    0,
  )
  const expected = USCC_CHARSET[(31 - total % 31) % 31]
  return code[17] === expected ? '' : '统一社会信用代码校验位不正确，请核对最后一位'
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const [applicationResult, agreementResult] = await Promise.all([
      api.get('/merchant-onboarding/me'),
      agreements.value ? Promise.resolve(agreements.value) : api.get('/legal/agreements/current'),
    ])
    agreements.value = agreementResult
    application.value = applicationResult
    if (application.value?.status === 'approved') {
      const user = await api.get('/auth/me')
      updateSessionUser(user)
      ElMessage.success('店铺入驻申请已通过')
      await router.replace('/overview')
      return
    }
    fillForm(application.value)
  } finally {
    if (!silent) loading.value = false
  }
}

function validateStep(step: number) {
  const missing = (values: unknown[]) => values.some(value => value === null || String(value).trim() === '')
  if (step === 0) {
    if (missing([form.subject_type, form.legal_name, form.unified_social_credit_code, form.legal_representative, form.registered_address, form.business_scope])) {
      return '请完整填写主体资质信息'
    }
    const usccError = validateUscc(form.unified_social_credit_code, form.subject_type)
    if (usccError) return usccError
    if (!documentsOf('business_license').length) return '请上传营业执照'
  }
  if (step === 1 && missing([form.merchant_name, form.industry, form.address, form.business_hours])) return '请完整填写店铺资料'
  if (step === 2) {
    if (missing([form.contact_name, form.phone, form.contact_relationship])) return '请完整填写联系人信息'
    if (['store_manager', 'authorized_agent'].includes(form.contact_relationship || '') && !form.authorization_confirmed) return '请确认联系人已获得主体授权'
  }
  if (step === 3) {
    if (form.industry === '餐饮' && !documentsOf('food_business_license').length) return '请上传食品经营许可证'
    if (form.industry === '住宿' && !documentsOf('accommodation_permit').length) return '请上传住宿行业许可或备案材料'
    if (form.industry === '零售' && form.retail_food_related) {
      if (!form.retail_food_credential_type) return '请选择食品经营许可类型'
      if (!documentsOf(form.retail_food_credential_type).length) return '请上传对应的食品经营许可或备案材料'
    }
    if (form.other_permit_required && (!form.other_permit_name.trim() || !documentsOf('other_permit').length)) return '请填写并上传其他行政许可材料'
    if (form.additional_permits.some(item => !item.name.trim() || !item.document_id)) return '请补齐追加许可证名称和附件'
  }
  return ''
}

const allDataStepsCompleted = computed(
  () => [0, 1, 2, 3].every(step => completedSteps.value.has(step) && !validateStep(step)),
)

function isStepCompleted(step: number) {
  if (step < 4) return completedSteps.value.has(step) && !validateStep(step)
  return truthfulnessConfirmed.value && acceptedRules.value && acceptedPrivacy.value
}

function canNavigateStep(step: number) {
  return step === currentStep.value
    || step === highestReachedStep.value
    || completedSteps.value.has(step)
}

function stepStatus(step: number): 'success' | 'process' | 'wait' {
  if (step === currentStep.value) return 'process'
  return isStepCompleted(step) ? 'success' : 'wait'
}

async function saveDraft(step = highestReachedStep.value, showMessage = false) {
  saving.value = true
  try {
    highestReachedStep.value = Math.max(highestReachedStep.value, step)
    form.current_step = highestReachedStep.value
    application.value = await api.put('/merchant-onboarding/me/draft', form)
    if (showMessage) ElMessage.success('草稿已保存')
  } finally {
    saving.value = false
  }
}

async function nextStep() {
  if (currentStep.value === 4) {
    const firstIncomplete = [0, 1, 2, 3].find(
      step => !completedSteps.value.has(step) || !!validateStep(step),
    )
    if (firstIncomplete !== undefined) {
      currentStep.value = firstIncomplete
      return ElMessage.warning(`请先完善第 ${firstIncomplete + 1} 步`)
    }
    return
  }
  const message = validateStep(currentStep.value)
  if (message) return ElMessage.warning(message)
  completedSteps.value = new Set([...completedSteps.value, currentStep.value])
  const next = Math.min(4, currentStep.value + 1)
  await saveDraft(next)
  currentStep.value = next
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function goToStep(step: number) {
  if (!canNavigateStep(step) || step === currentStep.value || saving.value) return
  await saveDraft(highestReachedStep.value)
  currentStep.value = step
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function uploadDocument(type: string, event: Event, number = '', additionalIndex: number | null = null) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const extension = file.name.split('.').pop()?.toLowerCase() || ''
  if (!['jpg', 'jpeg', 'png', 'pdf'].includes(extension)) {
    input.value = ''
    return ElMessage.warning('仅支持 JPG、PNG 或 PDF 文件')
  }
  if (file.size > 10 * 1024 * 1024) {
    input.value = ''
    return ElMessage.warning('资质文件不能超过 10MB')
  }
  uploadingType.value = additionalIndex === null ? type : `${type}-${additionalIndex}`
  try {
    const data = new FormData()
    data.append('document_type', type)
    data.append('document_number', number)
    data.append('file', file, file.name)
    const document: DocumentItem = await api.post(
      '/merchant-onboarding/me/documents',
      data,
      { timeout: 120_000 },
    )
    if (!application.value) application.value = { status: 'draft', documents: [] }
    if (type === 'other_permit' && additionalIndex !== null) {
      const previousId = form.additional_permits[additionalIndex].document_id
      form.additional_permits[additionalIndex].document_id = document.id
      application.value.documents = [...documents.value, document]
      if (previousId) {
        await api.delete(`/credential-documents/${previousId}`)
        application.value.documents = documents.value.filter(item => item.id !== previousId)
      }
      await saveDraft(currentStep.value)
    } else {
      application.value.documents = type === 'other_permit'
        ? [...documents.value, document]
        : [...documents.value.filter(item => item.document_type !== type), document]
    }
    ElMessage.success(`${documentLabel(type)}上传成功`)
  } finally {
    uploadingType.value = ''
    input.value = ''
  }
}

async function removeDocument(document: DocumentItem) {
  await ElMessageBox.confirm(`确认删除“${document.original_name}”？`, '删除资质材料', { type: 'warning' })
  await api.delete(`/credential-documents/${document.id}`)
  if (application.value) application.value.documents = documents.value.filter(item => item.id !== document.id)
  for (const permit of form.additional_permits) if (permit.document_id === document.id) permit.document_id = 0
  ElMessage.success('资质材料已删除')
}

async function preview(document: DocumentItem) {
  if (previewLoading.value) return
  previewLoading.value = true
  const loading = ElLoading.service({ text: '正在安全加载资质材料…' })
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  try {
    const blob = await api.get(
      `/credential-documents/${document.id}/content`,
      { responseType: 'blob', timeout: 120_000 },
    )
    previewUrl.value = URL.createObjectURL(blob)
    previewDocument.value = document
  } finally {
    loading.close()
    previewLoading.value = false
  }
}

function closePreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  previewDocument.value = null
}

function addPermit() {
  form.additional_permits.push({ name: '', number: '', document_id: 0 })
}

async function removePermit(index: number) {
  const permit = form.additional_permits[index]
  if (permit.document_id) {
    const document = documents.value.find(item => item.id === permit.document_id)
    if (document) await removeDocument(document)
  }
  form.additional_permits.splice(index, 1)
}

async function submit() {
  for (let step = 0; step < 4; step += 1) {
    const message = validateStep(step)
    if (message) {
      currentStep.value = step
      return ElMessage.warning(message)
    }
  }
  if (!truthfulnessConfirmed.value || !acceptedRules.value || !acceptedPrivacy.value) {
    highestReachedStep.value = 4
    currentStep.value = 4
    return ElMessage.warning('请完成真实性承诺并同意两份协议')
  }
  submitting.value = true
  try {
    await saveDraft(4)
    application.value = await api.post('/merchant-onboarding/me/submit', {
      truthfulness_confirmed: truthfulnessConfirmed.value,
      accepted_rules: acceptedRules.value,
      rules_version: agreements.value.platform_rules.version,
      accepted_privacy: acceptedPrivacy.value,
      privacy_version: agreements.value.privacy_policy.version,
    })
    ElMessage.success('入驻申请已提交，请等待管理员审核')
  } catch (error: any) {
    const first = error.response?.data?.data?.errors?.[0]
    if (first?.step !== undefined) currentStep.value = first.step
  } finally {
    submitting.value = false
  }
}

async function logout() {
  await logoutSession()
  router.replace('/login')
}

onMounted(async () => {
  await load()
  refreshTimer = window.setInterval(() => {
    if (application.value?.status === 'pending') load(true)
  }, 15_000)
})
onBeforeUnmount(() => {
  window.clearInterval(refreshTimer)
  closePreview()
})
</script>

<template>
  <div class="onboarding-page" v-loading="loading">
    <header>
      <div class="brand"><span><DataAnalysis /></span><b>万州商户通</b></div>
      <div><span>{{ session.user?.display_name }}</span><el-button text :icon="SwitchButton" @click="logout">退出登录</el-button></div>
    </header>
    <main>
      <section v-if="application?.status === 'pending'" class="status-card">
        <span class="status-icon"><Clock /></span>
        <p class="eyebrow">店铺入驻申请</p>
        <h1>资料正在审核中</h1>
        <p>管理员审核通过后，系统会自动创建商户档案并开放对应工作台。页面每15秒检查一次审核结果。</p>
        <div class="submitted-store">
          <b>{{ application.merchant_name }}</b>
          <span>{{ application.legal_name }} · {{ application.industry }}</span>
          <small>{{ application.address }}</small>
        </div>
        <el-button :icon="Refresh" @click="load()">立即刷新状态</el-button>
      </section>

      <section v-else class="wizard-shell">
        <div class="intro">
          <div><p class="eyebrow">真实商户入驻</p><h1>{{ application?.status === 'needs_changes' ? '补充资料并重新提交' : '提交店铺入驻申请' }}</h1></div>
          <el-button plain :loading="saving" @click="saveDraft(currentStep,true)">保存草稿</el-button>
        </div>
        <el-alert v-if="application?.status === 'needs_changes'" class="review-alert" type="error" :closable="false" :title="`管理员补充说明：${application.review_note}`" />

        <el-steps :active="currentStep" finish-status="success" class="desktop-steps">
          <el-step
            v-for="(item,index) in steps"
            :key="item"
            :title="item"
            :status="stepStatus(index)"
            :class="{ clickable: canNavigateStep(index) }"
            @click="goToStep(index)"
          />
        </el-steps>
        <div class="mobile-progress">
          <div class="mobile-progress-head"><span>第 {{ currentStep + 1 }} / 5 步</span><b>{{ steps[currentStep] }}</b></div>
          <i><em :style="{width:`${(highestReachedStep+1)*20}%`}" /></i>
          <div class="mobile-step-links">
            <button
              v-for="(_,index) in steps"
              :key="index"
              type="button"
              :class="{ active: currentStep===index, completed: isStepCompleted(index) }"
              :disabled="!canNavigateStep(index)"
              @click="goToStep(index)"
            >第{{ index + 1 }}步</button>
          </div>
        </div>

        <el-form label-position="top" class="step-form">
          <div v-show="currentStep===0">
            <div class="step-heading"><span>01</span><div><h2>主体资质</h2><p>仅接受持有有效营业执照的企业和个体工商户，不收集身份证照片。</p></div></div>
            <div class="form-grid">
              <el-form-item class="wide" label="主体类型 *"><el-radio-group v-model="form.subject_type"><el-radio-button value="enterprise">企业</el-radio-button><el-radio-button value="individual_business">个体工商户</el-radio-button></el-radio-group></el-form-item>
              <el-form-item label="营业执照名称 *"><el-input v-model="form.legal_name" maxlength="160" placeholder="必须与营业执照完全一致" /></el-form-item>
              <el-form-item label="统一社会信用代码 *"><el-input v-model="form.unified_social_credit_code" maxlength="40" placeholder="18位代码，自动去空格并转为大写" @input="normalizeUsccField" @blur="normalizeUsccField" /></el-form-item>
              <el-form-item label="法定代表人 / 经营者 *"><el-input v-model="form.legal_representative" maxlength="80" /></el-form-item>
              <el-form-item label="营业执照注册地址 *"><el-input v-model="form.registered_address" maxlength="255" /></el-form-item>
              <el-form-item class="wide" label="营业执照经营范围 *"><el-input v-model="form.business_scope" type="textarea" :rows="3" maxlength="3000" show-word-limit /></el-form-item>
              <el-form-item class="wide" label="营业执照文件 *">
                <div class="upload-box">
                  <label><el-icon><UploadFilled /></el-icon><span>{{ uploadingType==='business_license' ? '正在安全上传…' : '上传或替换营业执照' }}</span><small>JPG、PNG或PDF，单文件不超过10MB</small><input type="file" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf" :disabled="!!uploadingType" @change="uploadDocument('business_license',$event)" /></label>
                  <div v-for="item in documentsOf('business_license')" :key="item.id" class="file-row"><Document /><span>{{ item.original_name }}</span><button type="button" @click="preview(item)">预览</button><button type="button" class="danger" @click="removeDocument(item)">删除</button></div>
                </div>
              </el-form-item>
            </div>
          </div>

          <div v-show="currentStep===1">
            <div class="step-heading"><span>02</span><div><h2>店铺资料</h2><p>店铺展示名称可以与营业执照名称不同，适用于品牌门店和连锁门店。</p></div></div>
            <div class="form-grid">
              <el-form-item label="店铺展示名称 *"><el-input v-model="form.merchant_name" maxlength="120" /></el-form-item>
              <el-form-item label="所属行业 *"><el-select v-model="form.industry"><el-option v-for="item in ['餐饮','零售','生活服务','住宿']" :key="item" :value="item" /></el-select></el-form-item>
              <el-form-item class="wide" label="实际经营地址 *"><el-input v-model="form.address" maxlength="255" /></el-form-item>
              <el-form-item label="营业时间 *"><el-input v-model="form.business_hours" maxlength="80" /></el-form-item>
              <el-form-item label="经营规模"><el-select v-model="form.scale"><el-option v-for="item in ['小微','中小','中型']" :key="item" :value="item" /></el-select></el-form-item>
              <el-form-item label="员工人数"><el-input-number v-model="form.employee_count" :min="0" /></el-form-item>
              <el-form-item label="店铺面积（㎡）"><el-input-number v-model="form.store_area" :min="0" /></el-form-item>
              <el-form-item label="当前网络"><el-select v-model="form.network_environment"><el-option v-for="item in ['无固定宽带','移动热点','共享网络','普通宽带','千兆宽带','企业专线']" :key="item" :value="item" /></el-select></el-form-item>
              <el-form-item label="当前带宽（Mbps）"><el-input-number v-model="form.bandwidth_mbps" :min="0" /></el-form-item>
              <el-form-item class="wide" label="数字化需求"><el-select v-model="form.needs" multiple filterable allow-create><el-option v-for="item in ['高速网络','稳定网络','扫码点餐','视频监控','线上营销','会员系统','短视频推广','直播带货','线上预约','全屋 Wi-Fi']" :key="item" :value="item" /></el-select></el-form-item>
            </div>
          </div>

          <div v-show="currentStep===2">
            <div class="step-heading"><span>03</span><div><h2>联系人与授权</h2><p>联系人用于补充资料和后续服务跟进，不要求上传身份证件。</p></div></div>
            <div class="form-grid">
              <el-form-item label="联系人姓名 *"><el-input v-model="form.contact_name" maxlength="50" /></el-form-item>
              <el-form-item label="联系电话 *"><el-input v-model="form.phone" maxlength="30" /></el-form-item>
              <el-form-item class="wide" label="联系人与主体关系 *"><el-radio-group v-model="form.contact_relationship"><el-radio v-for="item in relationshipOptions" :key="item[0]" :value="item[0]">{{ item[1] }}</el-radio></el-radio-group></el-form-item>
              <template v-if="['store_manager','authorized_agent'].includes(form.contact_relationship || '')">
                <el-form-item class="wide"><el-checkbox v-model="form.authorization_confirmed">本人确认已获得该企业或个体工商户授权提交本次入驻申请</el-checkbox></el-form-item>
                <el-form-item class="wide" label="授权书（选传）">
                  <div class="upload-box"><label><el-icon><UploadFilled /></el-icon><span>上传或替换授权书</span><small>不需要上传身份证照片</small><input type="file" accept=".jpg,.jpeg,.png,.pdf" :disabled="!!uploadingType" @change="uploadDocument('authorization_letter',$event)" /></label>
                    <div v-for="item in documentsOf('authorization_letter')" :key="item.id" class="file-row"><Document /><span>{{ item.original_name }}</span><button type="button" @click="preview(item)">预览</button><button type="button" class="danger" @click="removeDocument(item)">删除</button></div>
                  </div>
                </el-form-item>
              </template>
            </div>
          </div>

          <div v-show="currentStep===3">
            <div class="step-heading"><span>04</span><div><h2>行业许可</h2><p>系统根据所属行业显示必需材料，所有商户都可以追加其他许可证。</p></div></div>
            <el-alert v-if="!form.industry" type="warning" :closable="false" title="请先在上一步选择所属行业" />
            <div class="permit-section" v-if="form.industry==='餐饮'">
              <h3>食品经营许可证 *</h3><p>餐饮商户必须提交有效的食品经营许可证。</p>
              <div class="upload-box"><label><UploadFilled /><span>上传或替换食品经营许可证</span><input type="file" accept=".jpg,.jpeg,.png,.pdf" :disabled="!!uploadingType" @change="uploadDocument('food_business_license',$event)" /></label><div v-for="item in documentsOf('food_business_license')" :key="item.id" class="file-row"><Document /><span>{{ item.original_name }}</span><button type="button" @click="preview(item)">预览</button><button type="button" class="danger" @click="removeDocument(item)">删除</button></div></div>
            </div>
            <div class="permit-section" v-if="form.industry==='住宿'">
              <h3>住宿行业许可或备案 *</h3>
              <div class="upload-box"><label><UploadFilled /><span>上传或替换行业许可材料</span><input type="file" accept=".jpg,.jpeg,.png,.pdf" :disabled="!!uploadingType" @change="uploadDocument('accommodation_permit',$event)" /></label><div v-for="item in documentsOf('accommodation_permit')" :key="item.id" class="file-row"><Document /><span>{{ item.original_name }}</span><button type="button" @click="preview(item)">预览</button><button type="button" class="danger" @click="removeDocument(item)">删除</button></div></div>
            </div>
            <div class="permit-section" v-if="form.industry==='零售'">
              <h3>食品经营情况</h3><el-switch v-model="form.retail_food_related" active-text="涉及食品经营" inactive-text="不涉及" />
              <template v-if="form.retail_food_related">
                <el-radio-group v-model="form.retail_food_credential_type" class="permit-radio"><el-radio value="food_business_license">食品经营许可证</el-radio><el-radio value="prepackaged_food_filing">仅销售预包装食品备案</el-radio></el-radio-group>
                <div v-if="form.retail_food_credential_type" class="upload-box"><label><UploadFilled /><span>上传对应许可或备案材料</span><input type="file" accept=".jpg,.jpeg,.png,.pdf" :disabled="!!uploadingType" @change="uploadDocument(form.retail_food_credential_type || '',$event)" /></label><div v-for="item in documentsOf(form.retail_food_credential_type || '')" :key="item.id" class="file-row"><Document /><span>{{ item.original_name }}</span><button type="button" @click="preview(item)">预览</button><button type="button" class="danger" @click="removeDocument(item)">删除</button></div></div>
              </template>
            </div>
            <div class="permit-section">
              <h3>其他行政许可</h3><el-switch v-model="form.other_permit_required" active-text="涉及其他许可" inactive-text="不涉及" />
              <div v-if="form.other_permit_required" class="form-grid permit-fields"><el-form-item label="许可证名称 *"><el-input v-model="form.other_permit_name" maxlength="120" /></el-form-item><el-form-item label="证件编号"><el-input v-model="form.other_permit_number" maxlength="120" /></el-form-item><el-form-item class="wide"><div class="upload-box"><label><UploadFilled /><span>上传其他行政许可</span><input type="file" accept=".jpg,.jpeg,.png,.pdf" :disabled="!!uploadingType" @change="uploadDocument('other_permit',$event,form.other_permit_number)" /></label></div></el-form-item></div>
            </div>
            <div class="permit-section">
              <div class="permit-title"><div><h3>追加许可证</h3><p>可添加当前行业涉及的其他许可或备案材料。</p></div><el-button plain @click="addPermit">添加许可证</el-button></div>
              <div v-for="(permit,index) in form.additional_permits" :key="index" class="extra-permit">
                <el-input v-model="permit.name" maxlength="120" placeholder="许可证名称" /><el-input v-model="permit.number" maxlength="120" placeholder="证件编号（选填）" />
                <label class="small-upload"><span>{{ permit.document_id ? '替换附件' : '上传附件' }}</span><input type="file" accept=".jpg,.jpeg,.png,.pdf" :disabled="!!uploadingType" @change="uploadDocument('other_permit',$event,permit.number,index)" /></label>
                <el-button link type="danger" @click="removePermit(index)">删除</el-button>
              </div>
            </div>
          </div>

          <div v-show="currentStep===4">
            <div class="step-heading"><span>05</span><div><h2>预览并提交</h2><p>请核对资料。提交后将进入管理员审核，审核期间不能修改。</p></div></div>
            <div class="review-grid">
              <section><h3>主体信息</h3><p><span>主体名称</span><b>{{ form.legal_name || '未填写' }}</b></p><p><span>信用代码</span><b>{{ form.unified_social_credit_code || '未填写' }}</b></p><p><span>代表人/经营者</span><b>{{ form.legal_representative || '未填写' }}</b></p></section>
              <section><h3>店铺信息</h3><p><span>店铺名称</span><b>{{ form.merchant_name || '未填写' }}</b></p><p><span>行业</span><b>{{ form.industry || '未填写' }}</b></p><p><span>经营地址</span><b>{{ form.address || '未填写' }}</b></p></section>
              <section><h3>联系信息</h3><p><span>联系人</span><b>{{ form.contact_name || '未填写' }}</b></p><p><span>联系电话</span><b>{{ form.phone || '未填写' }}</b></p><p><span>与主体关系</span><b>{{ relationLabel(form.contact_relationship) }}</b></p></section>
              <section><h3>证件材料</h3><button v-for="item in documents" :key="item.id" type="button" class="document-chip" @click="preview(item)"><Document />{{ documentLabel(item.document_type) }} · {{ item.original_name }}</button><p v-if="!documents.length" class="muted">尚未上传材料</p></section>
            </div>
            <div class="confirmations">
              <el-checkbox v-model="truthfulnessConfirmed">本人承诺以上资料真实、准确、完整且持续有效</el-checkbox>
              <el-checkbox v-model="acceptedRules">我已阅读并同意<button type="button" @click.prevent="agreementDialog='platform_rules'">《平台服务规则》</button></el-checkbox>
              <el-checkbox v-model="acceptedPrivacy">我已阅读并同意<button type="button" @click.prevent="agreementDialog='privacy_policy'">《隐私政策》</button></el-checkbox>
            </div>
          </div>
        </el-form>

        <div class="wizard-actions">
          <el-button
            type="primary"
            size="large"
            :loading="saving || submitting"
            @click="allDataStepsCompleted ? submit() : nextStep()"
          >{{ allDataStepsCompleted ? '提交入驻申请' : '保存并继续' }}</el-button>
        </div>
      </section>
    </main>

    <el-dialog :model-value="!!previewDocument" :title="previewDocument?.original_name" width="min(900px, calc(100% - 24px))" destroy-on-close @close="closePreview">
      <iframe v-if="previewDocument?.mime_type==='application/pdf'" class="document-preview" :src="previewUrl" sandbox="allow-same-origin" />
      <img v-else class="image-preview" :src="previewUrl" alt="资质材料预览" />
    </el-dialog>
    <el-dialog :model-value="!!agreementDialog" :title="agreementDialog && agreements?.[agreementDialog]?.title" width="min(560px, calc(100% - 32px))" @close="agreementDialog=null">
      <p class="agreement-version">版本：{{ agreementDialog && agreements?.[agreementDialog]?.version }}</p><p class="agreement-content">{{ agreementDialog && agreements?.[agreementDialog]?.content }}</p>
      <template #footer><el-button type="primary" @click="agreementDialog=null">我已阅读</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.onboarding-page{min-height:100vh;background:linear-gradient(145deg,#edf8f5,#f8f8f3)}header{height:70px;padding:0 max(24px,5vw);display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,.92);border-bottom:1px solid var(--line)}header>div{display:flex;align-items:center;gap:12px;color:var(--muted);font-size:12px}.brand{color:var(--ink)!important;font-size:17px!important}.brand>span{width:36px;height:36px;padding:8px;display:grid;place-items:center;border-radius:10px;background:var(--brand);color:#fff}main{width:min(1040px,calc(100% - 32px));margin:30px auto 60px}.wizard-shell,.status-card{padding:32px;border-radius:20px;background:#fff;box-shadow:0 18px 55px rgba(24,77,72,.08)}.intro{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.eyebrow{margin:0 0 7px;color:var(--brand);font-size:11px;font-weight:700;letter-spacing:1px}.intro h1,.status-card h1{margin:0;font-size:26px}.review-alert{margin-bottom:22px}.desktop-steps{margin:30px 0 38px}.desktop-steps :deep(.el-step){cursor:default}.desktop-steps :deep(.el-step.clickable){cursor:pointer}.desktop-steps :deep(.el-step.clickable:hover .el-step__title){color:var(--brand)}.mobile-progress{display:none}.step-form{min-height:440px}.step-heading{display:flex;gap:14px;align-items:flex-start;margin-bottom:28px}.step-heading>span{width:40px;height:40px;display:grid;place-items:center;border-radius:12px;background:#dff1ed;color:var(--brand);font-weight:800}.step-heading h2{margin:0 0 6px;font-size:20px}.step-heading p,.permit-section>p,.permit-title p{margin:0;color:var(--muted);font-size:12px;line-height:1.7}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}.wide{grid-column:1/-1}.form-grid :deep(.el-select),.form-grid :deep(.el-input-number){width:100%}.upload-box{width:100%;display:flex;flex-direction:column;gap:8px}.upload-box>label{min-height:86px;border:1px dashed #b9d5d0;border-radius:12px;background:#f8fbfa;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:4px;color:var(--brand);cursor:pointer}.upload-box>label svg{width:22px}.upload-box>label small{color:var(--muted);font-size:10px}.upload-box input,.small-upload input{display:none}.file-row{display:grid;grid-template-columns:20px minmax(0,1fr) auto auto;gap:8px;align-items:center;padding:10px 12px;border-radius:9px;background:#f3f7f6;font-size:12px}.file-row>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.file-row button,.confirmations button{border:0;background:none;color:var(--brand);cursor:pointer}.file-row button.danger{color:#df6269}.permit-section{padding:19px;margin-bottom:14px;border:1px solid var(--line);border-radius:13px}.permit-section h3{margin:0 0 6px;font-size:15px}.permit-radio{display:flex;margin:16px 0}.permit-fields{margin-top:16px}.permit-title{display:flex;align-items:center;justify-content:space-between}.extra-permit{display:grid;grid-template-columns:1fr 1fr 105px 45px;gap:8px;margin-top:12px}.small-upload{height:32px;border:1px solid #b8d4cf;border-radius:6px;color:var(--brand);display:grid;place-items:center;font-size:12px;cursor:pointer}.review-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.review-grid section{padding:18px;border-radius:12px;background:#f6f9f8}.review-grid h3{margin:0 0 13px}.review-grid p{display:flex;gap:15px;margin:8px 0;font-size:12px}.review-grid p span{width:90px;flex:none;color:var(--muted)}.review-grid p b{overflow-wrap:anywhere}.document-chip{width:100%;padding:9px;margin:4px 0;border:1px solid var(--line);border-radius:7px;background:#fff;color:#435351;display:flex;align-items:center;gap:6px;text-align:left;cursor:pointer}.document-chip svg{width:15px}.muted{color:var(--muted)}.confirmations{display:flex;flex-direction:column;align-items:flex-start;gap:4px;margin-top:22px}.wizard-actions{display:flex;justify-content:flex-end;gap:10px;padding-top:24px;margin-top:24px;border-top:1px solid var(--line)}.status-card{max-width:560px;margin:80px auto;text-align:center}.status-icon{width:64px;height:64px;padding:17px;margin:0 auto 20px;display:grid;place-items:center;border-radius:50%;background:#fff0dd;color:#bd6e24}.status-card>p{color:var(--muted);font-size:13px;line-height:1.7}.submitted-store{margin:24px 0;padding:18px;border-radius:12px;background:#f4f8f7;display:flex;flex-direction:column;gap:5px}.submitted-store span,.submitted-store small{color:var(--muted);font-size:12px}.document-preview{width:100%;height:70vh;border:0}.image-preview{display:block;max-width:100%;max-height:70vh;margin:auto;object-fit:contain}.agreement-version{color:var(--muted);font-size:12px}.agreement-content{white-space:pre-wrap;line-height:1.9;color:#435351}
@media(max-width:700px){header{padding:0 16px}header>div>span{display:none}main{width:calc(100% - 20px);margin:10px auto 100px}.wizard-shell,.status-card{padding:20px 16px;border-radius:15px}.intro{align-items:flex-start}.intro h1{font-size:21px}.intro>.el-button{display:none}.desktop-steps{display:none}.mobile-progress{display:flex;flex-direction:column;gap:9px;padding:14px;margin:16px 0 26px;border-radius:11px;background:#f3f8f7}.mobile-progress-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.mobile-progress-head span{color:var(--muted);font-size:10px}.mobile-progress-head b{font-size:15px}.mobile-progress>i{height:4px;border-radius:4px;background:#d9e5e2;overflow:hidden}.mobile-progress>i em{display:block;height:100%;background:var(--brand);transition:width .2s}.mobile-step-links{display:grid;grid-template-columns:repeat(5,1fr);gap:5px}.mobile-step-links button{min-width:0;padding:6px 2px;border:1px solid #dce8e5;border-radius:7px;background:#fff;color:#879391;font-size:9px;white-space:nowrap}.mobile-step-links button.completed{border-color:#9bcfc8;color:var(--brand)}.mobile-step-links button.active{border-color:var(--brand);background:var(--brand);color:#fff;font-weight:700}.mobile-step-links button:disabled{cursor:not-allowed;opacity:.45}.step-form{min-height:0}.step-heading p{font-size:11px}.form-grid{grid-template-columns:1fr}.wide{grid-column:auto}.permit-section{padding:14px}.permit-radio{align-items:flex-start;flex-direction:column}.extra-permit{grid-template-columns:1fr 1fr}.extra-permit .small-upload,.extra-permit .el-button{width:100%}.review-grid{grid-template-columns:1fr}.confirmations :deep(.el-checkbox){height:auto;min-height:30px;white-space:normal}.wizard-actions{position:fixed;z-index:20;left:0;right:0;bottom:0;margin:0;padding:12px 14px calc(12px + env(safe-area-inset-bottom));background:#fff;box-shadow:0 -8px 25px rgba(26,67,63,.1);display:grid}.wizard-actions :deep(.el-button){width:100%;margin:0}.status-card{margin:40px auto}.document-preview{height:62vh}}
</style>
