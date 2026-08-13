<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElLoading, ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Check, Document, Search, View } from '@element-plus/icons-vue'
import api from '@/services/api'
import { session } from '@/stores/session'
import type { Merchant } from '@/types'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const items = ref<Merchant[]>([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const industry = ref('')
const status = ref('')
const dataScope = ref<'all' | 'real' | 'demo'>('all')
const onboardingItems = ref<any[]>([])
const onboardingLoading = ref(false)
const onboardingDetail = ref<any>(null)
const detailVisible = ref(false)
const detailLoading = ref(false)
const previewUrl = ref('')
const previewDocument = ref<any>(null)
const previewLoading = ref(false)
const expandedMerchantId = ref<number | null>(null)
const onboardingStatus = computed(() => ({
  draft: { label: '草稿', type: 'info' },
  pending: { label: '待审核', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  needs_changes: { label: '待补资料', type: 'danger' },
} as Record<string, { label: string, type: 'info' | 'warning' | 'success' | 'danger' }>)[onboardingDetail.value?.status] || { label: '未知状态', type: 'info' })

async function load() {
  loading.value = true
  try {
    const result = await api.get('/merchants', { params: { page: page.value, page_size: 10, keyword: keyword.value, industry: industry.value, status: status.value, data_scope: dataScope.value } })
    items.value = result.items
    total.value = result.total
    if (!items.value.some(item => item.id === expandedMerchantId.value)) expandedMerchantId.value = null
  } finally { loading.value = false }
}
async function loadOnboarding() {
  onboardingLoading.value = true
  try {
    const result = await api.get('/merchant-onboarding', { params: { status: 'pending', page_size: 100 } })
    onboardingItems.value = result.items
  } finally {
    onboardingLoading.value = false
  }
}

function inspect(item: Merchant) {
  session.selectedMerchantId = item.id
  router.push('/store')
}
function onboardingRelation(value: string) {
  return ({ legal_representative: '法定代表人', business_operator: '个体经营者', store_manager: '店长', authorized_agent: '授权经办人' } as Record<string,string>)[value] || '未填写'
}
function toggleActions(item: Merchant) {
  expandedMerchantId.value = expandedMerchantId.value === item.id ? null : item.id
}
async function openOnboarding(item: any) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    onboardingDetail.value = await api.get(`/merchant-onboarding/${item.id}`)
  } finally {
    detailLoading.value = false
  }
}
function clearOnboardingRoute() {
  if (!onboardingDetail.value || String(route.query.onboarding_id || '') !== String(onboardingDetail.value.id)) return
  const query = { ...route.query }
  delete query.onboarding_id
  void router.replace({ query })
}
async function approveOnboarding() {
  const item = onboardingDetail.value
  await ElMessageBox.confirm(`确认通过“${item.merchant_name}”的入驻申请？通过后将创建商户并绑定账号 ${item.username}。`, '通过入驻申请', { type: 'warning' })
  await api.patch(`/merchant-onboarding/${item.id}/review`, { action: 'approve', note: '' })
  ElMessage.success('入驻申请已通过')
  detailVisible.value = false
  await Promise.all([loadOnboarding(), load()])
  window.dispatchEvent(new CustomEvent('wst:onboarding-refresh'))
}
async function requestChanges() {
  const item = onboardingDetail.value
  const result = await ElMessageBox.prompt('请明确填写需要申请人补充或修改的内容', `要求“${item.merchant_name}”补充资料`, {
    inputType: 'textarea',
    inputPlaceholder: '该说明会完整展示给申请人',
    inputValidator: value => !!value.trim() || '请填写补充说明',
  })
  await api.patch(`/merchant-onboarding/${item.id}/review`, { action: 'request_changes', note: result.value.trim() })
  ElMessage.success('已通知申请人补充资料')
  detailVisible.value = false
  await loadOnboarding()
  window.dispatchEvent(new CustomEvent('wst:onboarding-refresh'))
}
async function previewCredential(document: any) {
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
function refreshOnboardingFromNotification() {
  loadOnboarding()
}
onMounted(() => Promise.all([load(), loadOnboarding()]))
onMounted(() => window.addEventListener('wst:onboarding-changed', refreshOnboardingFromNotification))
watch(() => route.query.onboarding_id, async value => {
  const id = Number(value)
  if (!Number.isInteger(id) || id <= 0) return
  if (id === onboardingDetail.value?.id) detailVisible.value = true
  else await openOnboarding({ id })
}, { immediate: true })
onBeforeUnmount(() => {
  closePreview()
  window.removeEventListener('wst:onboarding-changed', refreshOnboardingFromNotification)
})
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1 class="page-title">商户管理</h1><p class="page-subtitle">审核商户入驻申请，查看已通过的商户档案</p></div></div>
    <section class="card onboarding-review">
      <div class="onboarding-head">
        <div><h2 class="section-title">待审核入驻申请</h2><span>审核通过后才会创建商户并开放对应工作台</span></div>
        <b>{{ onboardingItems.length }} 项</b>
      </div>
      <div v-loading="onboardingLoading" class="onboarding-list">
        <article v-for="item in onboardingItems" :key="item.id">
          <div class="onboarding-main">
            <span class="application-avatar">{{ item.merchant_name.slice(0,1) }}</span>
            <div><b>{{ item.merchant_name }}</b><small>账号 {{ item.username }} · 申请人 {{ item.display_name }}</small><p>{{ item.industry }} · {{ item.contact_name }} · {{ item.phone }}</p><p>{{ item.address }}</p></div>
          </div>
          <div class="onboarding-facts">
            <span><small>经营规模</small><b>{{ item.scale }}</b></span>
            <span><small>员工 / 面积</small><b>{{ item.employee_count }} 人 / {{ item.store_area }}㎡</b></span>
            <span><small>当前网络</small><b>{{ item.network_environment }} · {{ item.bandwidth_mbps }}Mbps</b></span>
          </div>
          <div class="onboarding-actions"><el-button type="primary" plain :icon="View" @click="openOnboarding(item)">查看申请</el-button></div>
        </article>
        <el-empty v-if="!onboardingLoading && !onboardingItems.length" description="暂无待审核入驻申请" :image-size="56" />
      </div>
    </section>
    <el-drawer v-model="detailVisible" class="onboarding-drawer" size="min(720px, 100%)" title="入驻申请详情" @closed="clearOnboardingRoute">
      <div v-loading="detailLoading" class="application-detail">
        <template v-if="onboardingDetail">
          <div class="detail-hero">
            <span class="application-avatar">{{ onboardingDetail.merchant_name.slice(0,1) }}</span>
            <div><h2>{{ onboardingDetail.merchant_name }}</h2><p>账号 {{ onboardingDetail.username }} · 申请人 {{ onboardingDetail.display_name }}</p></div>
            <el-tag :type="onboardingStatus.type">{{ onboardingStatus.label }}</el-tag>
          </div>
          <el-alert v-if="onboardingDetail.existing_entity" :closable="false" type="warning" show-icon :title="`该主体已绑定 ${onboardingDetail.existing_entity.merchant_count} 家门店`" />
          <el-alert v-if="onboardingDetail.duplicate_store" :closable="false" type="error" show-icon title="该主体下已存在同名同址门店，当前申请不能通过" />
          <section class="detail-section"><h3>主体资质</h3><dl><dt>主体类型</dt><dd>{{ onboardingDetail.subject_type==='enterprise' ? '企业' : '个体工商户' }}</dd><dt>营业执照名称</dt><dd>{{ onboardingDetail.legal_name }}</dd><dt>统一社会信用代码</dt><dd>{{ onboardingDetail.unified_social_credit_code }}</dd><dt>代表人 / 经营者</dt><dd>{{ onboardingDetail.legal_representative }}</dd><dt>注册地址</dt><dd>{{ onboardingDetail.registered_address }}</dd><dt>经营范围</dt><dd>{{ onboardingDetail.business_scope }}</dd></dl></section>
          <section class="detail-section"><h3>门店资料</h3><dl><dt>展示名称</dt><dd>{{ onboardingDetail.merchant_name }}</dd><dt>所属行业</dt><dd>{{ onboardingDetail.industry }}</dd><dt>经营地址</dt><dd>{{ onboardingDetail.address }}</dd><dt>营业时间</dt><dd>{{ onboardingDetail.business_hours }}</dd><dt>经营规模</dt><dd>{{ onboardingDetail.scale }} · {{ onboardingDetail.employee_count }}人 · {{ onboardingDetail.store_area }}㎡</dd><dt>当前网络</dt><dd>{{ onboardingDetail.network_environment }} · {{ onboardingDetail.bandwidth_mbps }}Mbps</dd></dl></section>
          <section class="detail-section"><h3>联系与授权</h3><dl><dt>联系人</dt><dd>{{ onboardingDetail.contact_name }}</dd><dt>联系电话</dt><dd>{{ onboardingDetail.phone }}</dd><dt>关系</dt><dd>{{ onboardingRelation(onboardingDetail.contact_relationship) }}</dd><dt>授权声明</dt><dd>{{ onboardingDetail.authorization_confirmed ? '已确认' : '不适用' }}</dd></dl></section>
          <section class="detail-section"><h3>资质材料（{{ onboardingDetail.documents.length }}）</h3><button v-for="document in onboardingDetail.documents" :key="document.id" type="button" class="credential-row" @click="previewCredential(document)"><Document /><span><b>{{ document.original_name }}</b><small>{{ document.mime_type }} · {{ Math.ceil(document.file_size/1024) }}KB</small></span><em>安全预览</em></button></section>
          <el-alert v-if="onboardingDetail.status==='needs_changes' && onboardingDetail.review_note" :closable="false" type="error" :title="`补充说明：${onboardingDetail.review_note}`" />
          <div v-if="onboardingDetail.status==='pending'" class="review-actions"><el-button plain @click="requestChanges">要求补充资料</el-button><el-button type="primary" :icon="Check" :disabled="onboardingDetail.duplicate_store" @click="approveOnboarding">通过申请</el-button></div>
        </template>
      </div>
    </el-drawer>
    <el-dialog :model-value="!!previewDocument" :title="previewDocument?.original_name" width="min(900px, calc(100% - 24px))" @close="closePreview">
      <iframe v-if="previewDocument?.mime_type==='application/pdf'" class="credential-preview" :src="previewUrl" sandbox="allow-same-origin" />
      <img v-else class="credential-image" :src="previewUrl" alt="资质材料预览" />
    </el-dialog>
    <section class="card filters">
      <el-input v-model="keyword" clearable placeholder="搜索商户名称或地址" :prefix-icon="Search" @keyup.enter="load" />
      <el-select v-model="industry" clearable placeholder="全部行业"><el-option v-for="item in ['餐饮','零售','生活服务','住宿']" :key="item" :label="item" :value="item" /></el-select>
      <el-select v-model="status" clearable placeholder="全部状态"><el-option label="正常运营" value="enabled" /><el-option label="已停用" value="disabled" /></el-select>
      <el-select v-model="dataScope" placeholder="数据类型"><el-option label="全部数据" value="all" /><el-option label="正式商户" value="real" /><el-option label="演示商户" value="demo" /></el-select>
      <el-button type="primary" plain @click="page=1;load()">筛选</el-button>
      <span class="result">共 {{ total }} 家商户</span>
    </section>
    <section class="card table-card">
      <el-table v-loading="loading" :data="items" class="desktop-merchant-table" style="width:100%">
        <el-table-column label="商户" min-width="210">
          <template #default="{ row }"><div class="merchant-cell"><span :class="`industry-icon industry-${row.industry}`">{{ row.name.slice(0,1) }}</span><div><b>{{ row.name }} <em v-if="row.is_demo">演示数据</em></b><small>{{ row.address }}</small></div></div></template>
        </el-table-column>
        <el-table-column prop="industry" label="行业" width="100" />
        <el-table-column label="网络环境" min-width="135"><template #default="{ row }">{{ row.network_environment }}<small class="bandwidth">{{ row.bandwidth_mbps }}Mbps</small></template></el-table-column>
        <el-table-column label="核心需求" min-width="200"><template #default="{ row }"><span v-for="need in row.needs.slice(0,2)" :key="need" class="tag">{{ need }}</span><span v-if="row.needs.length>2" class="more">+{{ row.needs.length-2 }}</span></template></el-table-column>
        <el-table-column label="状态" width="105"><template #default="{ row }"><span :class="['status-dot',row.status]">{{ row.status === 'enabled' ? '正常运营' : '已停用' }}</span></template></el-table-column>
        <el-table-column label="操作" width="90" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="inspect(row)">查看</el-button></template></el-table-column>
      </el-table>
      <div v-loading="loading" class="mobile-merchant-list">
        <article v-for="item in items" :key="item.id" class="mobile-merchant-row" :class="{ expanded: expandedMerchantId === item.id }">
          <button
            type="button"
            class="mobile-merchant-summary"
            :aria-expanded="expandedMerchantId === item.id"
            @click="toggleActions(item)"
          >
            <span :class="`industry-icon industry-${item.industry}`">{{ item.name.slice(0,1) }}</span>
            <span class="mobile-merchant-copy">
              <b>{{ item.name }} <em v-if="item.is_demo">演示</em></b>
              <small>{{ item.address }}</small>
            </span>
            <span :class="['status-dot',item.status]">{{ item.status === 'enabled' ? '正常' : '停用' }}</span>
            <el-icon class="expand-icon"><ArrowDown /></el-icon>
          </button>
          <transition name="merchant-expand">
            <div v-if="expandedMerchantId === item.id" class="mobile-merchant-panel">
              <div class="mobile-merchant-meta">
                <span><small>所属行业</small><b>{{ item.industry }}</b></span>
                <span><small>网络环境</small><b>{{ item.network_environment }} · {{ item.bandwidth_mbps }}Mbps</b></span>
              </div>
              <div v-if="item.needs.length" class="mobile-needs">
                <span v-for="need in item.needs" :key="need" class="tag">{{ need }}</span>
              </div>
              <div class="mobile-merchant-actions">
                <el-button type="primary" plain @click="inspect(item)">查看档案</el-button>
              </div>
            </div>
          </transition>
        </article>
        <div v-if="!loading && !items.length" class="empty">没有找到符合条件的商户</div>
      </div>
      <div class="pagination"><el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="prev, pager, next" @current-change="load" /></div>
    </section>
  </div>
</template>

<style scoped>
.filters { padding: 16px; display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }
.onboarding-review{margin-bottom:16px;overflow:hidden}.onboarding-head{padding:17px 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}.onboarding-head .section-title{margin-bottom:4px}.onboarding-head span{color:var(--muted);font-size:11px}.onboarding-head>b{min-width:44px;padding:7px 10px;border-radius:9px;background:#fff0dd;color:#b96a23;text-align:center;font-size:12px}.onboarding-list>article{padding:17px 20px;display:grid;grid-template-columns:minmax(260px,1.4fr) minmax(320px,1fr) auto;align-items:center;gap:18px;border-bottom:1px solid var(--line)}.onboarding-list>article:last-of-type{border-bottom:0}.onboarding-main{min-width:0;display:flex;align-items:center;gap:12px}.application-avatar{width:42px;height:42px;flex:0 0 42px;display:grid;place-items:center;border-radius:11px;background:#dff1ed;color:var(--brand);font-weight:700}.onboarding-main>div{min-width:0;display:flex;flex-direction:column;gap:3px}.onboarding-main small,.onboarding-main p{margin:0;color:var(--muted);font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.onboarding-facts{display:grid;grid-template-columns:.7fr 1fr 1.4fr;gap:10px}.onboarding-facts span{display:flex;min-width:0;flex-direction:column;gap:4px}.onboarding-facts small{color:var(--muted);font-size:9px}.onboarding-facts b{font-size:11px;overflow-wrap:anywhere}.onboarding-actions{display:flex;gap:7px}.onboarding-actions :deep(.el-button){margin:0}
.filters .el-input { width: 270px; }.filters .el-select{width:140px}.result{margin-left:auto;color:var(--muted);font-size:12px}
.table-card { overflow: hidden; }.table-card :deep(.el-table__cell){padding:15px 0}
.merchant-cell{display:flex;align-items:center;gap:11px}.merchant-cell>span{width:38px;height:38px;border-radius:10px;display:grid;place-items:center;background:#dff1ed;color:var(--brand);font-weight:700}
.merchant-cell div{display:flex;flex-direction:column;gap:4px}.merchant-cell small{color:var(--muted);max-width:250px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.merchant-cell em,.mobile-merchant-copy em{display:inline-block;white-space:nowrap;font-style:normal;font-size:9px;font-weight:500;padding:2px 5px;border-radius:5px;background:#fff1e7;color:#c5682e}
.bandwidth{display:block;color:var(--muted);margin-top:3px}.more{font-size:11px;color:var(--muted)}.status-dot{font-size:12px}.status-dot::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:6px}.status-dot.enabled::before{background:#2ca67d}.status-dot.disabled::before{background:#a6aeac}
.mobile-merchant-list{display:none}.pagination{display:flex;justify-content:flex-end;padding:16px 20px}
.application-detail{min-height:300px;padding:0 5px 90px}.detail-hero{display:grid;grid-template-columns:46px minmax(0,1fr) auto;gap:12px;align-items:center;margin-bottom:18px}.detail-hero h2{margin:0 0 4px;font-size:20px}.detail-hero p{margin:0;color:var(--muted);font-size:11px}.detail-section{padding:18px 0;border-bottom:1px solid var(--line)}.detail-section h3{margin:0 0 13px;font-size:15px}.detail-section dl{display:grid;grid-template-columns:120px minmax(0,1fr);gap:10px 14px;margin:0;font-size:12px}.detail-section dt{color:var(--muted)}.detail-section dd{margin:0;overflow-wrap:anywhere}.credential-row{width:100%;display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:9px;align-items:center;padding:11px;margin:7px 0;border:1px solid var(--line);border-radius:9px;background:#f8fbfa;color:inherit;text-align:left;cursor:pointer}.credential-row>span{display:flex;min-width:0;flex-direction:column;gap:3px}.credential-row b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.credential-row small{color:var(--muted)}.credential-row em{font-style:normal;color:var(--brand);font-size:11px}.review-actions{position:sticky;bottom:0;display:flex;justify-content:flex-end;gap:8px;padding:16px 0;background:#fff}.credential-preview{width:100%;height:70vh;border:0}.credential-image{display:block;max-width:100%;max-height:70vh;margin:auto;object-fit:contain}
@media(max-width:1024px){
  .onboarding-list>article{grid-template-columns:1fr}.onboarding-facts{padding-left:54px}.onboarding-actions{padding-left:54px}.onboarding-actions :deep(.el-button){flex:1}
  .filters{flex-wrap:wrap}.filters .el-input{width:100%}.filters .el-select{width:calc(50% - 6px)}.result{width:100%;margin-left:0}
  .table-card{overflow:hidden}.desktop-merchant-table{display:none}.mobile-merchant-list{display:block;min-height:120px}
  .mobile-merchant-row{border-bottom:1px solid var(--line);background:#fff}.mobile-merchant-row:last-child{border-bottom:0}.mobile-merchant-row.expanded{background:#fbfdfc}
  .mobile-merchant-summary{width:100%;min-width:0;border:0;background:transparent;color:inherit;padding:15px 14px;display:grid;grid-template-columns:42px minmax(0,1fr) auto 20px;align-items:center;gap:11px;text-align:left;cursor:pointer}
  .mobile-merchant-summary>.industry-icon{width:42px;min-width:42px;height:42px;border-radius:12px;display:grid;place-items:center;background:#dff1ed;color:var(--brand);font-weight:700}
  .mobile-merchant-copy{min-width:0;display:flex;flex-direction:column;gap:4px}.mobile-merchant-copy b,.mobile-merchant-copy small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mobile-merchant-copy b{font-size:14px}.mobile-merchant-copy small{color:var(--muted);font-size:11px}
  .mobile-merchant-summary .status-dot{white-space:nowrap;color:var(--muted);font-size:11px}.expand-icon{color:#849391;transition:transform .2s}.expanded .expand-icon{transform:rotate(180deg);color:var(--brand)}
  .mobile-merchant-panel{padding:0 14px 15px 67px}.mobile-merchant-meta{display:grid;grid-template-columns:1fr 1.4fr;gap:10px;padding:12px 0;border-top:1px dashed #dfe8e6}.mobile-merchant-meta span{display:flex;min-width:0;flex-direction:column;gap:4px}.mobile-merchant-meta small{color:var(--muted);font-size:10px}.mobile-merchant-meta b{font-size:12px;overflow-wrap:anywhere}
  .mobile-needs{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:12px}.mobile-needs .tag{margin:0}.mobile-merchant-actions{display:grid;grid-template-columns:1fr;gap:8px}.mobile-merchant-actions :deep(.el-button){width:100%;margin:0;padding-left:8px;padding-right:8px}
  .merchant-expand-enter-active,.merchant-expand-leave-active{transition:opacity .18s ease,transform .18s ease}.merchant-expand-enter-from,.merchant-expand-leave-to{opacity:0;transform:translateY(-4px)}
  .pagination{justify-content:center;padding:14px 8px}
}
@media(max-width:560px){.onboarding-head{align-items:flex-start}.onboarding-list>article{padding:15px 14px}.onboarding-facts,.onboarding-actions{padding-left:0}.onboarding-facts{grid-template-columns:1fr 1fr}.onboarding-facts span:last-child{grid-column:1/-1}.detail-section dl{grid-template-columns:90px minmax(0,1fr)}.review-actions{display:grid;grid-template-columns:1fr 1fr}.review-actions :deep(.el-button){margin:0}.credential-preview{height:62vh}}
</style>
