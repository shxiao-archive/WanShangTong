<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, Check, Clock, DocumentChecked, Service } from '@element-plus/icons-vue'
import api from '@/services/api'
import { inboxLocation, inboxTargetIsAvailable } from '@/services/inbox'
import type { InboxNotification, InboxSummary, WorkItem } from '@/types'

const props = withDefaults(defineProps<{
  modelValue: boolean
  summary: InboxSummary
  showWorkItems?: boolean
}>(), {
  showWorkItems: true,
})
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  refresh: []
}>()
const router = useRouter()
const activeTab = ref<'work' | 'notifications'>(props.showWorkItems ? 'work' : 'notifications')
const workCategory = ref<'all' | 'onboarding' | 'service'>('all')
const notificationState = ref<'all' | 'unread'>('all')
const notificationCategory = ref<'all' | 'onboarding' | 'service'>('all')
const notificationPeriod = ref<'7d' | '30d' | 'all'>('7d')
const workItems = ref<WorkItem[]>([])
const notifications = ref<InboxNotification[]>([])
const workTotal = ref(0)
const notificationTotal = ref(0)
const workPage = ref(1)
const notificationPage = ref(1)
const workLoading = ref(false)
const notificationLoading = ref(false)
const readingAll = ref(false)
const pageSize = 20

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})
const workHasMore = computed(() => workItems.value.length < workTotal.value)
const notificationHasMore = computed(() => notifications.value.length < notificationTotal.value)

function dateTime(value: string) {
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

async function loadWorkItems(reset = true) {
  if (workLoading.value) return
  if (reset) {
    workPage.value = 1
    workItems.value = []
  }
  workLoading.value = true
  try {
    const result = await api.get('/inbox/work-items', {
      params: { page: workPage.value, page_size: pageSize, category: workCategory.value },
    })
    workItems.value = reset ? result.items : [...workItems.value, ...result.items]
    workTotal.value = result.total
  } finally {
    workLoading.value = false
  }
}

async function loadNotifications(reset = true) {
  if (notificationLoading.value) return
  if (reset) {
    notificationPage.value = 1
    notifications.value = []
  }
  notificationLoading.value = true
  try {
    const result = await api.get('/inbox/notifications', {
      params: {
        page: notificationPage.value,
        page_size: pageSize,
        state: notificationState.value,
        category: notificationCategory.value,
        period: props.showWorkItems ? notificationPeriod.value : 'all',
      },
    })
    notifications.value = reset ? result.items : [...notifications.value, ...result.items]
    notificationTotal.value = result.total
  } finally {
    notificationLoading.value = false
  }
}

async function loadMoreWork() {
  workPage.value += 1
  await loadWorkItems(false)
}

async function loadMoreNotifications() {
  notificationPage.value += 1
  await loadNotifications(false)
}

async function openWorkItem(item: WorkItem) {
  visible.value = false
  await router.push(inboxLocation(item.action, item.target_id))
}

async function markRead(item: InboxNotification) {
  if (item.read_at) return
  const updated = await api.patch(`/inbox/notifications/${item.id}/read`)
  item.read_at = updated.read_at
  emit('refresh')
}

async function openNotification(item: InboxNotification) {
  try {
    await markRead(item)
    await inboxTargetIsAvailable(item.action, item.target_id)
    visible.value = false
    await router.push(inboxLocation(item.action, item.target_id))
  } catch (error: any) {
    if (error?.response?.status === 404) {
      ElMessage.info('该申请不存在或已无权查看，通知中心已刷新')
      await refreshLists()
      emit('refresh')
      return
    }
    throw error
  }
}

async function refreshLists() {
  const requests: Promise<unknown>[] = [loadNotifications()]
  if (props.showWorkItems) requests.push(loadWorkItems())
  await Promise.all(requests)
}

async function readAll() {
  if (!props.summary.unread_count || readingAll.value) return
  readingAll.value = true
  try {
    await api.post('/inbox/notifications/read-all')
    ElMessage.success('全部通知已标为已读')
    await loadNotifications()
    emit('refresh')
  } finally {
    readingAll.value = false
  }
}

watch(visible, value => {
  if (value) void refreshLists()
})
watch(workCategory, () => {
  if (props.showWorkItems) void loadWorkItems()
})
watch([notificationState, notificationCategory, notificationPeriod], () => loadNotifications())
</script>

<template>
  <el-drawer
    v-model="visible"
    class="inbox-drawer"
    size="520px"
    :with-header="false"
    append-to-body
    destroy-on-close
  >
    <header class="inbox-head">
      <div><span class="inbox-symbol"><Bell /></span><div><h2>{{ showWorkItems ? '通知与待办' : '通知中心' }}</h2><p>{{ showWorkItems ? '重要事项集中处理，多设备实时同步' : '查看与你的店铺和申请相关的消息' }}</p></div></div>
      <button type="button" aria-label="关闭通知中心" @click="visible=false">×</button>
    </header>

    <el-tabs v-model="activeTab" class="inbox-tabs" :class="{ 'notifications-only': !showWorkItems }">
      <el-tab-pane v-if="showWorkItems" name="work">
        <template #label><span class="tab-label">待办<i v-if="summary.todo_count">{{ summary.todo_count > 99 ? '99+' : summary.todo_count }}</i></span></template>
        <div class="inbox-toolbar">
          <el-segmented v-model="workCategory" :options="[{label:'全部',value:'all'},{label:'入驻审核',value:'onboarding'},{label:'服务申请',value:'service'}]" />
        </div>
        <div v-loading="workLoading" class="inbox-list">
          <button v-for="item in workItems" :key="item.key" type="button" class="inbox-row" @click="openWorkItem(item)">
            <span :class="['row-icon', item.category]">
              <DocumentChecked v-if="item.category==='onboarding'" /><Service v-else />
            </span>
            <span class="row-copy"><span><b>{{ item.title }}</b><em v-if="item.is_demo">演示数据</em></span><small>{{ item.summary }}</small><time><Clock />{{ dateTime(item.updated_at) }}</time></span>
            <span :class="['row-status', item.status]">{{ item.status_label }}</span>
          </button>
          <el-empty v-if="!workLoading && !workItems.length" description="当前没有待办事项" :image-size="64" />
          <el-button v-if="workHasMore" class="load-more" text :loading="workLoading" @click="loadMoreWork">加载更多</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane name="notifications">
        <template #label><span class="tab-label">通知<i v-if="summary.unread_count">{{ summary.unread_count > 99 ? '99+' : summary.unread_count }}</i></span></template>
        <div class="inbox-toolbar notification-toolbar">
          <div>
            <el-radio-group v-model="notificationState" size="small"><el-radio-button value="all">全部</el-radio-button><el-radio-button value="unread">未读</el-radio-button></el-radio-group>
            <el-select v-model="notificationCategory" size="small" aria-label="通知业务分类"><el-option label="全部分类" value="all" /><el-option label="入驻申请" value="onboarding" /><el-option label="服务申请" value="service" /></el-select>
            <el-select v-if="showWorkItems" v-model="notificationPeriod" class="notification-period" size="small" aria-label="通知时间范围"><el-option label="近7天" value="7d" /><el-option label="近30天" value="30d" /><el-option label="全部" value="all" /></el-select>
          </div>
          <el-button text type="primary" :icon="Check" :loading="readingAll" :disabled="!summary.unread_count" @click="readAll">全部已读</el-button>
        </div>
        <div v-loading="notificationLoading" class="inbox-list">
          <button v-for="item in notifications" :key="item.id" type="button" :class="['inbox-row','notification-row',{ unread: !item.read_at }]" @click="openNotification(item)">
            <span :class="['row-icon', item.category]"><DocumentChecked v-if="item.category==='onboarding'" /><Service v-else /></span>
            <span class="row-copy"><span><b>{{ item.title }}</b><em v-if="item.is_demo">演示数据</em></span><small>{{ item.message }}</small><time><Clock />{{ dateTime(item.created_at) }}</time></span>
            <i v-if="!item.read_at" class="unread-dot" aria-label="未读" />
          </button>
          <el-empty v-if="!notificationLoading && !notifications.length" description="暂无通知" :image-size="64" />
          <el-button v-if="notificationHasMore" class="load-more" text :loading="notificationLoading" @click="loadMoreNotifications">加载更多</el-button>
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-drawer>
</template>

<style scoped>
.inbox-head{display:flex;align-items:center;justify-content:space-between;padding:4px 0 17px;border-bottom:1px solid var(--line)}.inbox-head>div{display:flex;align-items:center;gap:12px}.inbox-symbol{width:40px;height:40px;padding:10px;box-sizing:border-box;border-radius:12px;background:var(--brand-soft);color:var(--brand)}.inbox-head h2{margin:0 0 4px;font-size:19px}.inbox-head p{margin:0;color:var(--muted);font-size:11px}.inbox-head>button{width:34px;height:34px;border:0;background:transparent;color:#73817f;font-size:26px;cursor:pointer}.inbox-tabs{height:calc(100vh - 90px)}.inbox-tabs :deep(.el-tabs__header){margin:0}.inbox-tabs :deep(.el-tabs__content){height:calc(100% - 40px);overflow:hidden}.inbox-tabs.notifications-only :deep(.el-tabs__header){display:none}.inbox-tabs.notifications-only :deep(.el-tabs__content){height:100%}.inbox-tabs :deep(.el-tab-pane){height:100%;display:flex;flex-direction:column}.tab-label{display:flex;align-items:center;gap:6px}.tab-label i{min-width:18px;height:18px;padding:0 5px;box-sizing:border-box;display:grid;place-items:center;border-radius:10px;background:#e77c45;color:#fff;font-size:9px;font-style:normal}.inbox-toolbar{padding:14px 0 12px;border-bottom:1px solid var(--line)}.inbox-toolbar :deep(.el-segmented){width:100%}.notification-toolbar{display:flex;align-items:center;justify-content:space-between;gap:8px}.notification-toolbar>div{display:flex;align-items:center;gap:8px}.notification-toolbar .el-select{width:108px}.notification-toolbar .notification-period{width:92px}.inbox-list{min-height:180px;overflow:auto;padding-bottom:22px}.inbox-row{position:relative;width:100%;padding:16px 3px;border:0;border-bottom:1px solid var(--line);background:#fff;color:inherit;display:grid;grid-template-columns:40px minmax(0,1fr) auto;gap:11px;align-items:start;text-align:left;cursor:pointer}.inbox-row:hover{background:#f8fbfa}.notification-row.unread{background:#f1f9f7}.row-icon{width:38px;height:38px;padding:10px;box-sizing:border-box;border-radius:11px}.row-icon.onboarding{color:#137c73;background:#e2f3ef}.row-icon.service{color:#bb682c;background:#fff0e5}.row-copy{min-width:0;display:flex;flex-direction:column;gap:5px}.row-copy>span{display:flex;align-items:center;gap:6px;min-width:0}.row-copy b{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row-copy em{flex:0 0 auto;padding:2px 5px;border-radius:5px;background:#fff0e5;color:#c46d31;font-size:8px;font-style:normal}.row-copy small{color:#687a78;font-size:11px;line-height:1.5}.row-copy time{display:flex;align-items:center;gap:4px;color:#98a3a1;font-size:9px}.row-copy time svg{width:11px}.row-status{margin-top:3px;padding:4px 7px;border-radius:6px;font-size:9px;white-space:nowrap}.row-status.pending,.row-status.needs_changes{background:#fff0dd;color:#b76a27}.row-status.processing{background:#e2f3ef;color:#137c73}.unread-dot{width:7px;height:7px;margin:8px 5px 0;border-radius:50%;background:#e77c45}.load-more{display:block;margin:12px auto 0}.inbox-list :deep(.el-empty){padding:50px 0}
@media(max-width:600px){.inbox-head{padding-top:max(4px,env(safe-area-inset-top))}.inbox-tabs{height:calc(100dvh - 94px - env(safe-area-inset-top))}.notification-toolbar{align-items:flex-start;flex-direction:column}.notification-toolbar>div{width:100%;justify-content:space-between}.notification-toolbar>.el-button{align-self:flex-end}.inbox-row{padding:14px 2px}.row-copy small{font-size:10px}}
</style>

<style>
@media(max-width:600px){.inbox-drawer{width:100vw!important;max-width:100vw}.inbox-drawer .el-drawer__body{padding:14px 16px calc(18px + env(safe-area-inset-bottom))}}
</style>
