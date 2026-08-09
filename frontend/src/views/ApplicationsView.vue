<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Clock, Search } from '@element-plus/icons-vue'
import api from '@/services/api'
import { session } from '@/stores/session'
import type { ApplicationStatus, ServiceApplication } from '@/types'

const route = useRoute()
const loading = ref(false)
const items = ref<ServiceApplication[]>([])
const total = ref(0)
const page = ref(1)
const statusFilter = ref('')
const keyword = ref('')
const dataScope = ref<'real' | 'demo' | 'all'>('real')
const detailDialog = ref(false)
const detail = ref<ServiceApplication | null>(null)
const note = ref('')
const statusNote = ref('')
const working = ref(false)
const isOperator = computed(() => session.user?.role === 'operator')
const labels: Record<ApplicationStatus, string> = {
  pending: '待处理', processing: '办理中', completed: '已完成', canceled: '已取消',
}
const eventLabels: Record<string, string> = {
  created: '提交申请',
  status_changed: '状态更新',
  note: '运营跟进备注',
  merchant_note: '商户补充留言',
}
const canAddNote = computed(() => {
  if (!detail.value) return false
  return isOperator.value || ['pending', 'processing'].includes(detail.value.status)
})
const nextActions = computed(() => {
  if (!detail.value) return []
  if (!isOperator.value) return detail.value.status === 'pending' ? [{ status: 'canceled', label: '取消申请', type: 'danger' }] : []
  const map: Record<ApplicationStatus, { status: ApplicationStatus, label: string, type?: string }[]> = {
    pending: [{ status: 'processing', label: '进入办理' }, { status: 'canceled', label: '取消申请', type: 'danger' }],
    processing: [{ status: 'completed', label: '完成申请' }, { status: 'canceled', label: '取消申请', type: 'danger' }],
    completed: [], canceled: [],
  }
  return map[detail.value.status]
})

function dateTime(value: string) {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

async function load() {
  loading.value = true
  try {
    const result = await api.get('/service-applications', {
      params: {
        page: page.value,
        page_size: 20,
        status: statusFilter.value,
        keyword: keyword.value,
        data_scope: isOperator.value ? dataScope.value : 'all',
      },
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function openDetail(id: number) {
  detail.value = await api.get(`/service-applications/${id}`)
  note.value = ''
  statusNote.value = ''
  detailDialog.value = true
}

async function changeStatus(target: ApplicationStatus) {
  if (!detail.value) return
  if (target === 'canceled') {
    await ElMessageBox.confirm('取消后本次申请将结束，确认继续？', '取消申请', { type: 'warning' })
  }
  working.value = true
  try {
    await api.patch(`/service-applications/${detail.value.id}/status`, { status: target, note: statusNote.value })
    ElMessage.success('申请状态已更新')
    statusNote.value = ''
    await Promise.all([openDetail(detail.value.id), load()])
  } finally {
    working.value = false
  }
}
function performStatus(target: string) {
  return changeStatus(target as ApplicationStatus)
}

async function addNote() {
  if (!detail.value || !note.value.trim()) return ElMessage.warning('请输入跟进备注')
  working.value = true
  try {
    await api.post(`/service-applications/${detail.value.id}/notes`, { note: note.value.trim() })
    note.value = ''
    ElMessage.success(isOperator.value ? '跟进备注已添加' : '补充留言已发送')
    await openDetail(detail.value.id)
  } finally {
    working.value = false
  }
}

onMounted(async () => {
  await load()
  const id = Number(route.query.id)
  if (id) await openDetail(id)
})
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1 class="page-title">{{ isOperator ? '服务跟进' : '我的申请' }}</h1><p class="page-subtitle">{{ isOperator ? '处理商户待办、记录跟进过程并推动服务落地' : '查看服务申请状态与运营跟进记录' }}</p></div></div>
    <section class="card application-filters">
      <el-input v-if="isOperator" v-model="keyword" clearable :prefix-icon="Search" placeholder="搜索商户、联系人或电话" @keyup.enter="page=1;load()" />
      <el-select v-model="statusFilter" clearable placeholder="全部状态"><el-option v-for="(label,key) in labels" :key="key" :label="label" :value="key" /></el-select>
      <el-select v-if="isOperator" v-model="dataScope"><el-option label="正式申请" value="real" /><el-option label="演示申请" value="demo" /><el-option label="全部申请" value="all" /></el-select>
      <el-button type="primary" plain @click="page=1;load()">筛选</el-button>
      <span class="result">共 {{ total }} 项</span>
    </section>
    <section v-loading="loading" class="application-list">
      <button v-for="item in items" :key="item.id" class="card application-card" @click="openDetail(item.id)">
        <span :class="['status',item.status]">{{ labels[item.status] }}</span>
        <div class="application-main"><small v-if="isOperator">{{ item.merchant_name }} <em v-if="item.is_demo">演示数据</em></small><b>{{ item.resource_snapshot.name }}</b><p>{{ item.resource_snapshot.description }}</p></div>
        <div class="application-meta"><span><Clock />{{ dateTime(item.created_at) }}</span><span>{{ item.contact_name }} · {{ item.contact_phone }}</span></div>
      </button>
      <el-empty v-if="!loading && !items.length" description="暂无符合条件的服务申请" />
    </section>
    <div class="pagination"><el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="prev, pager, next" @current-change="load" /></div>

    <el-drawer v-model="detailDialog" :title="detail?.resource_snapshot.name || '申请详情'" size="min(620px, 100%)">
      <template v-if="detail">
        <div class="detail-head">
          <div><small>{{ detail.merchant_name }}</small><h2>{{ detail.resource_snapshot.name }}</h2><p>申请编号 #{{ detail.id }} · {{ dateTime(detail.created_at) }}</p></div>
          <span :class="['status',detail.status]">{{ labels[detail.status] }}</span>
        </div>
        <div class="detail-grid">
          <span><small>联系人</small><b>{{ detail.contact_name }}</b></span>
          <span><small>联系电话</small><b>{{ detail.contact_phone }}</b></span>
          <span><small>提交时参考价格</small><b>¥{{ detail.resource_snapshot.price }} {{ detail.resource_snapshot.unit }}</b></span>
          <span><small>提交时匹配度</small><b>{{ detail.recommendation_score }}/100</b></span>
        </div>
        <section class="snapshot"><h3>申请内容快照</h3><p>{{ detail.resource_snapshot.description }}</p><div><span v-for="service in detail.resource_snapshot.included_services" :key="service">{{ service }}</span></div><blockquote v-if="detail.merchant_note">商户留言：{{ detail.merchant_note }}</blockquote></section>

        <section v-if="canAddNote" class="note-box">
          <h3>{{ isOperator ? '添加跟进备注' : '补充留言' }}</h3>
          <el-input
            v-model="note"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
            :placeholder="isOperator ? '记录电话沟通、处理结果或下一步安排' : '补充说明联系时间或具体需求'"
          />
          <el-button type="primary" plain :icon="ChatDotRound" :loading="working" @click="addNote">
            {{ isOperator ? '保存备注' : '发送留言' }}
          </el-button>
        </section>
        <section v-if="nextActions.length" class="status-action">
          <h3>{{ isOperator ? '推进状态' : '取消申请' }}</h3>
          <el-input
            v-model="statusNote"
            type="textarea"
            :rows="2"
            maxlength="1000"
            :placeholder="isOperator ? '可填写本次状态变更说明' : '可填写取消原因（选填）'"
          />
          <div><el-button v-for="action in nextActions" :key="action.status" :type="action.type || 'primary'" :loading="working" @click="performStatus(action.status)">{{ action.label }}</el-button></div>
        </section>
        <section class="timeline"><h3>申请时间线</h3><el-timeline>
          <el-timeline-item v-for="event in detail.events" :key="event.id" :timestamp="dateTime(event.created_at)" placement="top">
            <b>{{ eventLabels[event.event_type] || event.event_type }}<template v-if="event.to_status"> · {{ event.to_status === 'contacted' ? '已联系（历史）' : labels[event.to_status as ApplicationStatus] }}</template></b>
            <p v-if="event.note">{{ event.note }}</p>
          </el-timeline-item>
        </el-timeline></section>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.application-filters{padding:16px;display:flex;align-items:center;gap:12px;margin-bottom:16px}.application-filters .el-input{width:280px}.application-filters .el-select{width:140px}.result{margin-left:auto;color:var(--muted);font-size:12px}.application-list{display:grid;gap:12px}.application-card{width:100%;border:1px solid rgba(20,42,42,.06);padding:20px 22px;display:grid;grid-template-columns:90px 1fr auto;align-items:center;gap:18px;text-align:left;color:inherit;cursor:pointer}.application-card:hover{border-color:#a6d1cb;box-shadow:0 9px 30px rgba(11,118,111,.09)}.status{display:inline-flex;width:max-content;padding:5px 9px;border-radius:7px;font-size:11px;font-style:normal}.status.pending{background:#fff0dd;color:#bd6e24}.status.contacted{background:#e8f2ff;color:#377dbb}.status.processing{background:#e7f6f3;color:#147e75}.status.completed{background:#e8f7ec;color:#2c8550}.status.canceled{background:#f0f1f1;color:#7a8483}.application-main{min-width:0}.application-main small{display:block;color:var(--brand);margin-bottom:5px}.application-main em{font-style:normal;padding:2px 5px;border-radius:4px;background:#fff1e7;color:#c5682e}.application-main b{font-size:16px}.application-main p{margin:5px 0 0;color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.application-meta{display:flex;flex-direction:column;align-items:flex-end;gap:8px;color:var(--muted);font-size:11px}.application-meta span{display:flex;align-items:center;gap:5px}.application-meta svg{width:13px}.pagination{display:flex;justify-content:flex-end;padding:18px 0}.detail-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;border-bottom:1px solid var(--line);padding-bottom:18px}.detail-head small{color:var(--brand)}.detail-head h2{margin:5px 0}.detail-head p{font-size:11px;color:var(--muted);margin:0}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0}.detail-grid span{padding:13px;border-radius:10px;background:#f5f8f7;display:flex;flex-direction:column;gap:5px}.detail-grid small{color:var(--muted)}.detail-grid b{font-size:13px}.snapshot,.status-action,.note-box,.timeline{border-top:1px solid var(--line);padding-top:18px;margin-top:18px}.snapshot h3,.status-action h3,.note-box h3,.timeline h3{font-size:15px;margin:0 0 12px}.snapshot p{font-size:12px;color:var(--muted);line-height:1.7}.snapshot div{display:flex;flex-wrap:wrap;gap:6px}.snapshot div span{font-size:11px;padding:5px 8px;border-radius:6px;background:#eaf5f2;color:var(--brand)}.snapshot blockquote{margin:14px 0 0;padding:12px;border-left:3px solid var(--brand);background:#f5f8f7;color:#526563;font-size:12px}.status-action>div{display:flex;gap:8px;margin-top:10px}.note-box .el-button{margin-top:10px}.timeline p{margin:5px 0;color:var(--muted);line-height:1.6;font-size:12px}
@media(max-width:700px){.application-filters{flex-wrap:wrap}.application-filters .el-input{width:100%}.application-filters .el-select{width:calc(50% - 6px)}.result{width:100%;margin-left:0}.application-card{grid-template-columns:1fr auto;padding:16px}.application-card>.status{grid-column:2;grid-row:1}.application-main{grid-column:1/-1;grid-row:1}.application-meta{grid-column:1/-1;align-items:flex-start}.detail-grid{grid-template-columns:1fr}.status-action>div{flex-wrap:wrap}}
</style>
