<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check, Connection, Goods, Promotion } from '@element-plus/icons-vue'
import api from '@/services/api'
import { session } from '@/stores/session'

const router = useRouter()
const loading = ref(true)
const items = ref<any[]>([])
const merchant = ref<any>(null)
const applications = ref<any[]>([])
const applyDialog = ref(false)
const selectedResource = ref<any>(null)
const applying = ref(false)
const applicationForm = reactive({ contact_name: '', contact_phone: '', merchant_note: '' })
const merchantId = computed(() => session.selectedMerchantId || session.user?.merchant_id)
const activeByResource = computed(() => Object.fromEntries(
  applications.value
    .filter(item => ['pending', 'processing'].includes(item.status))
    .map(item => [item.resource_id, item]),
))
const categoryIcon = (category: string) => category === '网络' ? Connection : category === '营销' ? Promotion : Goods

onMounted(async () => {
  try {
    [items.value, merchant.value] = await Promise.all([
      api.get(`/merchants/${merchantId.value}/recommendations`),
      api.get(`/merchants/${merchantId.value}`),
    ])
    const result = await api.get('/service-applications', {
      params: { merchant_id: merchantId.value, data_scope: 'all', page_size: 100 },
    })
    applications.value = result.items
  } finally {
    loading.value = false
  }
})

function openApply(item: any) {
  selectedResource.value = item
  applicationForm.contact_name = merchant.value.contact_name
  applicationForm.contact_phone = merchant.value.phone
  applicationForm.merchant_note = ''
  applyDialog.value = true
}

async function submitApplication() {
  applying.value = true
  try {
    const result = await api.post('/service-applications', {
      merchant_id: merchantId.value,
      resource_id: selectedResource.value.id,
      ...applicationForm,
    })
    ElMessage.success('服务申请已提交')
    applyDialog.value = false
    router.push({ path: '/applications', query: { id: result.id } })
  } catch (error: any) {
    const existingId = error.response?.data?.data?.application_id
    if (existingId) router.push({ path: '/applications', query: { id: existingId } })
  } finally {
    applying.value = false
  }
}
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head"><div><h1 class="page-title">资源推荐</h1><p class="page-subtitle">根据行业、网络环境和真实需求，为门店匹配更合适的数字化服务</p></div><span class="updated">已按最新档案计算</span></div>
    <section v-if="merchant" class="basis card">
      <div><small>当前商户</small><b>{{ merchant.name }}</b></div><i></i><div><small>行业场景</small><b>{{ merchant.industry }}</b></div><i></i><div><small>当前网络</small><b>{{ merchant.network_environment }} · {{ merchant.bandwidth_mbps }}Mbps</b></div><i></i><div class="basis-needs"><small>重点需求</small><span v-for="need in merchant.needs.slice(0,3)" :key="need">{{ need }}</span></div>
    </section>
    <div v-if="items.length" class="rec-list">
      <article v-for="(item,index) in items" :key="item.id" class="card rec-card" :class="{ best:index===0 }">
        <div v-if="index===0" class="best-label">最佳匹配</div>
        <div class="rec-rank">0{{ index+1 }}</div>
        <div class="rec-icon"><component :is="categoryIcon(item.category)" /></div>
        <div class="rec-main">
          <span class="category">{{ item.category }}</span><h2>{{ item.name }}</h2><p>{{ item.description }}</p>
          <div class="reason"><b>为什么推荐</b><span v-for="reason in item.reasons" :key="reason"><Check />{{ reason }}</span></div>
        </div>
        <div class="rec-side">
          <div class="score"><span>匹配度</span><strong>{{ item.score }}</strong><small>/100</small></div>
          <div class="price"><small>参考价格</small><b>¥{{ item.price }}</b><span>/ {{ item.unit.replace('元/','') }}</span></div>
        </div>
        <div class="included">
          <small>包含服务</small><span v-for="service in item.included_services" :key="service"><Check />{{ service }}</span>
          <el-button v-if="activeByResource[item.id]" type="primary" plain @click="router.push({path:'/applications',query:{id:activeByResource[item.id].id}})">查看申请进度</el-button>
          <el-button v-else type="primary" @click="openApply(item)">申请服务</el-button>
        </div>
      </article>
    </div>
    <div v-else-if="!loading" class="card empty"><Goods /><h3>暂无精确推荐</h3><p>请完善店铺需求，平台将自动提供通用基础资源。</p></div>
    <section class="notice"><b>推荐说明</b><p>匹配分数由行业适配、需求标签、网络升级空间和通用性规则共同计算。价格为参考价格，具体服务以运营人员跟进确认为准。</p></section>

    <el-dialog v-model="applyDialog" title="申请数字化服务" width="520px">
      <div v-if="selectedResource" class="apply-resource"><b>{{ selectedResource.name }}</b><span>参考价 ¥{{ selectedResource.price }} / {{ selectedResource.unit.replace('元/','') }}</span></div>
      <el-form label-position="top">
        <el-form-item label="联系人"><el-input v-model="applicationForm.contact_name" maxlength="80" /></el-form-item>
        <el-form-item label="联系电话"><el-input v-model="applicationForm.contact_phone" maxlength="30" /></el-form-item>
        <el-form-item label="给运营人员的留言"><el-input v-model="applicationForm.merchant_note" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="可说明希望联系的时间或具体需求" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="applyDialog=false">取消</el-button><el-button type="primary" :loading="applying" @click="submitApplication">确认申请</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.updated{font-size:11px;color:#4d8f88}.updated::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:#38a77d;margin-right:7px}.basis{padding:18px 24px;display:flex;align-items:center;gap:25px;margin-bottom:18px}.basis>div{display:flex;flex-direction:column;gap:5px}.basis small{font-size:10px;color:var(--muted)}.basis b{font-size:13px}.basis>i{height:30px;width:1px;background:var(--line)}.basis-needs{flex-direction:row!important;align-items:center;flex-wrap:wrap;margin-left:auto}.basis-needs small{width:100%}.basis-needs span{font-size:10px;padding:4px 7px;background:#edf7f4;color:var(--brand);border-radius:5px}.rec-list{display:flex;flex-direction:column;gap:16px}.rec-card{position:relative;padding:26px 28px;display:grid;grid-template-columns:36px 48px 1fr 140px;column-gap:18px;overflow:hidden}.rec-card.best{border:1px solid #9bcfc8;box-shadow:0 10px 32px rgba(11,118,111,.1)}.best-label{position:absolute;right:0;top:0;padding:7px 15px;background:var(--brand);color:#fff;border-radius:0 16px 0 12px;font-size:10px}.rec-rank{color:#a9b4b2;font-size:12px;padding-top:8px}.rec-icon{width:48px;height:48px;padding:12px;border-radius:13px;background:#e4f3ef;color:var(--brand)}.rec-icon svg{width:100%}.category{font-size:10px;color:var(--brand);font-weight:700}.rec-main h2{font-size:20px;margin:5px 0 7px}.rec-main>p{font-size:12px;color:var(--muted);margin:0;line-height:1.7}.reason{margin-top:16px;display:flex;align-items:center;gap:13px;flex-wrap:wrap}.reason b{font-size:11px}.reason span,.included span{font-size:11px;color:#56706d;display:flex;align-items:center;gap:4px}.reason svg,.included svg{width:12px;color:#179079}.rec-side{border-left:1px solid var(--line);padding-left:24px;display:flex;flex-direction:column;justify-content:center;gap:18px}.score span,.price small{display:block;font-size:10px;color:var(--muted)}.score strong{font-size:27px;color:var(--brand)}.score small{font-size:10px}.price b{font-size:20px}.price span{font-size:10px;color:var(--muted)}.included{grid-column:3/-1;border-top:1px dashed var(--line);padding-top:15px;margin-top:18px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}.included>small{color:var(--muted)}.included .el-button{margin-left:auto}.notice{margin-top:18px;border-radius:12px;padding:16px 20px;background:#eef3f2;display:flex;gap:15px;font-size:11px}.notice b{white-space:nowrap;color:#536866}.notice p{margin:0;color:#71807f}.empty svg{width:42px;color:#a6b3b1}.empty h3{color:var(--ink)}.empty p{font-size:12px}.apply-resource{padding:15px;margin-bottom:18px;border-radius:10px;background:#eff8f6;display:flex;justify-content:space-between;gap:12px}.apply-resource span{color:var(--muted);font-size:12px}
@media(max-width:720px){.basis{align-items:flex-start;flex-wrap:wrap;gap:14px}.basis>i{display:none}.basis-needs{margin-left:0!important;width:100%}.rec-card{grid-template-columns:30px 42px 1fr;padding:22px 16px;column-gap:10px}.rec-icon{width:42px;height:42px}.rec-side{grid-column:2/-1;border-left:0;border-top:1px solid var(--line);padding:15px 0 0;margin-top:15px;flex-direction:row;justify-content:space-between}.included{grid-column:2/-1;flex-wrap:wrap}.included .el-button{width:100%;margin-left:0}.reason{align-items:flex-start;flex-direction:column;gap:7px}.notice{flex-direction:column;gap:5px}.apply-resource{flex-direction:column}:deep(.el-dialog){width:calc(100% - 24px)!important}}
</style>
