<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Delete, Download, Edit, Plus, Upload } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import api from '@/services/api'
import { session } from '@/stores/session'
import type { BusinessData } from '@/types'

use([CanvasRenderer, LineChart, BarChart, PieChart, GridComponent, LegendComponent, TooltipComponent])
const loading = ref(true)
const days = ref(7)
const summary = ref<any>(null)
const rows = ref<BusinessData[]>([])
const expandedDataId = ref<number | null>(null)
const dialog = ref(false)
const editingId = ref<number | null>(null)
const importDialog = ref(false)
const importFile = ref<File | null>(null)
const importPreview = ref<any>(null)
const overwrite = ref(false)
const importing = ref(false)
const emptyForm = () => ({
  business_date: new Date().toISOString().slice(0, 10),
  visitors: 0, orders: 0, revenue: 0, rating: 5,
  dine_in_orders: 0, delivery_orders: 0, group_buy_orders: 0, other_orders: 0, peak_hour: 12,
})
const form = reactive(emptyForm())
const merchantId = computed(() => session.selectedMerchantId || session.user?.merchant_id)
const canMaintain = computed(() => session.user?.role === 'merchant')
const displayRows = computed(() => [...rows.value].reverse())
const axisStyle = { axisLine: { lineStyle: { color: '#dfe7e5' } }, axisLabel: { color: '#84908f', fontSize: 10 }, axisTick: { show: false } }
const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' }, legend: { right: 0, data: ['营业额', '访客'], textStyle: { color: '#687876', fontSize: 11 } },
  grid: { left: 18, right: 18, bottom: 10, top: 45, containLabel: true },
  xAxis: { type: 'category', data: summary.value?.trend.map((item:any) => item.date.slice(5)) || [], ...axisStyle },
  yAxis: [{ type: 'value', ...axisStyle, splitLine: { lineStyle: { color: '#edf2f0' } } }, { type: 'value', ...axisStyle, splitLine: { show: false } }],
  series: [
    { name: '营业额', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, data: summary.value?.trend.map((item:any) => item.revenue) || [], itemStyle: { color: '#0d8178' }, lineStyle: { width: 3 }, areaStyle: { color: 'rgba(13,129,120,.09)' } },
    { name: '访客', type: 'line', smooth: true, yAxisIndex: 1, symbol: 'none', data: summary.value?.trend.map((item:any) => item.visitors) || [], lineStyle: { width: 2, color: '#e49350' } },
  ],
}))
const sourceOption = computed(() => ({
  tooltip: { trigger: 'item' }, legend: { bottom: 0, itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 10 } },
  series: [{ type: 'pie', radius: ['46%', '68%'], center: ['50%', '43%'], label: { formatter: '{d}%', fontSize: 10 }, data: summary.value?.sources || [], color: ['#11847b', '#49a99f', '#e79755', '#a4b7b3'] }],
}))
const peakOption = computed(() => ({
  tooltip: { trigger: 'axis' }, grid: { left: 10, right: 10, top: 15, bottom: 8, containLabel: true },
  xAxis: { type: 'category', data: summary.value?.peak_hours.map((item:any) => item.hour) || [], ...axisStyle },
  yAxis: { type: 'value', ...axisStyle, splitLine: { lineStyle: { color: '#edf2f0' } } },
  series: [{ type: 'bar', barMaxWidth: 26, data: summary.value?.peak_hours.map((item:any) => item.orders) || [], itemStyle: { color: '#e38a49', borderRadius: [6, 6, 0, 0] } }],
}))

async function load() {
  if (!merchantId.value) return
  loading.value = true
  try {
    [summary.value, rows.value] = await Promise.all([
      api.get(`/merchants/${merchantId.value}/business-summary`, { params: { days: days.value } }),
      api.get(`/merchants/${merchantId.value}/business-data`, { params: { days: 366 } }),
    ])
    if (!rows.value.some(row => row.id === expandedDataId.value)) expandedDataId.value = null
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, emptyForm())
  dialog.value = true
}
function openEdit(row: BusinessData) {
  editingId.value = row.id
  Object.assign(form, row)
  dialog.value = true
}
function toggleDataActions(row: BusinessData) {
  expandedDataId.value = expandedDataId.value === row.id ? null : row.id
}
async function save() {
  const sources = form.dine_in_orders + form.delivery_orders + form.group_buy_orders + form.other_orders
  if (sources !== form.orders) return ElMessage.warning(`订单来源合计为 ${sources}，必须与总订单 ${form.orders} 一致`)
  if (editingId.value) await api.put(`/merchants/${merchantId.value}/business-data/${editingId.value}`, form)
  else await api.post(`/merchants/${merchantId.value}/business-data`, form)
  ElMessage.success(editingId.value ? '经营数据已更新' : '经营数据已录入')
  dialog.value = false
  load()
}
async function remove(row: BusinessData) {
  await ElMessageBox.confirm(`确认删除 ${row.business_date} 的经营数据？删除后统计会同步排除。`, '删除经营数据', { type: 'warning' })
  await api.delete(`/merchants/${merchantId.value}/business-data/${row.id}`)
  ElMessage.success('经营数据已删除')
  load()
}
function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
async function downloadTemplate() {
  const blob = await api.get(`/merchants/${merchantId.value}/business-data/template`, { responseType: 'blob' })
  saveBlob(blob, '经营数据导入模板.xlsx')
}
async function exportData() {
  const blob = await api.get(`/merchants/${merchantId.value}/business-data/export`, { responseType: 'blob' })
  saveBlob(blob, '经营数据报表.xlsx')
}
async function selectImport(event: Event) {
  const input = event.target as HTMLInputElement
  importFile.value = input.files?.[0] || null
  input.value = ''
  if (!importFile.value) return
  overwrite.value = false
  await previewImport()
  importDialog.value = true
}
async function previewImport() {
  if (!importFile.value) return
  importing.value = true
  try {
    const data = new FormData()
    data.append('file', importFile.value)
    importPreview.value = await api.post(`/merchants/${merchantId.value}/business-data/import`, data, {
      params: { dry_run: true, conflict_mode: overwrite.value ? 'overwrite' : 'skip' },
    })
  } finally {
    importing.value = false
  }
}
async function commitImport() {
  if (!importFile.value || importPreview.value?.error_count) return
  importing.value = true
  try {
    const data = new FormData()
    data.append('file', importFile.value)
    await api.post(`/merchants/${merchantId.value}/business-data/import`, data, {
      params: { dry_run: false, conflict_mode: overwrite.value ? 'overwrite' : 'skip' },
    })
    ElMessage.success('Excel 经营数据已导入')
    importDialog.value = false
    await load()
  } finally {
    importing.value = false
  }
}
watch(days, load)
watch(overwrite, () => { if (importDialog.value) previewImport() })
onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head">
      <div><h1 class="page-title">经营分析</h1><p class="page-subtitle">{{ canMaintain ? '维护真实经营数据，用趋势发现变化并支持资源匹配' : '查看商户经营趋势与经营数据明细' }}</p></div>
      <div class="head-actions">
        <el-radio-group v-model="days"><el-radio-button :value="7">近 7 日</el-radio-button><el-radio-button :value="30">近 30 日</el-radio-button></el-radio-group>
        <el-button v-if="canMaintain" type="primary" :icon="Plus" @click="openCreate">录入数据</el-button>
      </div>
    </div>
    <template v-if="summary">
      <div class="metric-grid">
        <div class="card metric-card"><span class="metric-label">最新访客</span><div class="metric-value">{{ summary.today.visitors }}<small> 人</small></div><div class="metric-hint">最近有数据日期</div></div>
        <div class="card metric-card"><span class="metric-label">最新订单</span><div class="metric-value">{{ summary.today.orders }}<small> 单</small></div><div class="metric-hint">订单转化表现</div></div>
        <div class="card metric-card revenue"><span class="metric-label">最新营业额</span><div class="metric-value">¥{{ summary.today.revenue.toLocaleString() }}</div><div class="metric-hint">{{ days }} 日累计 ¥{{ summary.totals.revenue.toLocaleString() }}</div></div>
        <div class="card metric-card"><span class="metric-label">客单价</span><div class="metric-value">¥{{ summary.totals.average_order_value }}</div><div class="metric-hint">最新评分 {{ summary.today.rating }}</div></div>
      </div>
      <section class="card card-pad trend"><div class="chart-head"><h2 class="section-title">营收与客流趋势</h2><span>{{ days }} 日累计 {{ summary.totals.visitors }} 人 · {{ summary.totals.orders }} 笔订单</span></div><v-chart class="chart" :option="trendOption" autoresize /></section>
      <div class="two-col">
        <section class="card card-pad"><h2 class="section-title">订单来源占比</h2><v-chart class="sub-chart" :option="sourceOption" autoresize /></section>
        <section class="card card-pad"><h2 class="section-title">营业高峰时段</h2><v-chart class="sub-chart" :option="peakOption" autoresize /></section>
      </div>
    </template>

    <section class="card data-list">
      <div class="list-head">
        <div><h2 class="section-title">经营数据明细</h2><span>同一日期仅保留一条有效数据</span></div>
        <div>
          <el-button v-if="canMaintain" :icon="Download" @click="downloadTemplate">下载模板</el-button>
          <label v-if="canMaintain" class="import-button"><input type="file" accept=".xlsx" @change="selectImport" /><el-icon><Upload /></el-icon>Excel 导入</label>
          <el-button :icon="Download" @click="exportData">导出报表</el-button>
        </div>
      </div>
      <el-table :data="displayRows" class="desktop-data-table" style="width:100%">
        <el-table-column prop="business_date" label="日期" width="120" />
        <el-table-column prop="visitors" label="访客" />
        <el-table-column prop="orders" label="订单" />
        <el-table-column label="营业额"><template #default="{row}">¥{{ row.revenue }}</template></el-table-column>
        <el-table-column prop="rating" label="评分" />
        <el-table-column label="订单来源" min-width="190"><template #default="{row}">到店 {{ row.dine_in_orders }} · 外卖 {{ row.delivery_orders }} · 团购 {{ row.group_buy_orders }} · 其他 {{ row.other_orders }}</template></el-table-column>
        <el-table-column v-if="canMaintain" label="操作" width="120" fixed="right"><template #default="{row}"><el-button link :icon="Edit" @click="openEdit(row)">编辑</el-button><el-button link type="danger" :icon="Delete" @click="remove(row)">删除</el-button></template></el-table-column>
      </el-table>
      <div class="mobile-data-list">
        <article
          v-for="row in displayRows"
          :key="row.id"
          class="mobile-data-row"
          :class="{ expanded: expandedDataId === row.id }"
        >
          <button
            type="button"
            class="mobile-data-summary"
            :aria-expanded="expandedDataId === row.id"
            @click="toggleDataActions(row)"
          >
            <span><small>日期</small><b>{{ row.business_date }}</b></span>
            <span><small>访客</small><b>{{ row.visitors }}</b></span>
            <span><small>营业额</small><b>¥{{ row.revenue }}</b></span>
            <el-icon class="expand-icon"><ArrowDown /></el-icon>
          </button>
          <transition name="data-expand">
            <div v-if="expandedDataId === row.id" class="mobile-data-panel">
              <div class="mobile-data-meta">
                <span><small>订单</small><b>{{ row.orders }}</b></span>
                <span><small>评分</small><b>{{ row.rating }}</b></span>
                <span><small>高峰时段</small><b>{{ row.peak_hour }}:00</b></span>
              </div>
              <div class="mobile-data-sources">
                到店 {{ row.dine_in_orders }} · 外卖 {{ row.delivery_orders }} · 团购 {{ row.group_buy_orders }} · 其他 {{ row.other_orders }}
              </div>
              <div v-if="canMaintain" class="mobile-data-actions">
                <el-button :icon="Edit" @click="openEdit(row)">编辑</el-button>
                <el-button type="danger" plain :icon="Delete" @click="remove(row)">删除</el-button>
              </div>
            </div>
          </transition>
        </article>
      </div>
      <el-empty v-if="!rows.length" :description="canMaintain ? '暂无经营数据，可手工录入或导入 Excel' : '暂无经营数据'" />
    </section>

    <el-dialog v-if="canMaintain" v-model="dialog" :title="editingId ? '编辑经营数据' : '录入经营数据'" width="620px">
      <el-alert type="info" :closable="false" title="到店、外卖、团购和其他订单之和必须等于总订单。" />
      <el-form label-position="top" class="data-form">
        <el-form-item label="经营日期"><el-date-picker v-model="form.business_date" type="date" value-format="YYYY-MM-DD" :disabled-date="(value:Date)=>value.getTime()>Date.now()" /></el-form-item>
        <el-form-item label="访客数"><el-input-number v-model="form.visitors" :min="0" /></el-form-item>
        <el-form-item label="订单数"><el-input-number v-model="form.orders" :min="0" /></el-form-item>
        <el-form-item label="营业额（元）"><el-input-number v-model="form.revenue" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="到店订单"><el-input-number v-model="form.dine_in_orders" :min="0" /></el-form-item>
        <el-form-item label="外卖订单"><el-input-number v-model="form.delivery_orders" :min="0" /></el-form-item>
        <el-form-item label="团购订单"><el-input-number v-model="form.group_buy_orders" :min="0" /></el-form-item>
        <el-form-item label="其他订单"><el-input-number v-model="form.other_orders" :min="0" /></el-form-item>
        <el-form-item label="评分"><el-input-number v-model="form.rating" :min="0" :max="5" :step="0.1" /></el-form-item>
        <el-form-item label="高峰小时"><el-input-number v-model="form.peak_hour" :min="0" :max="23" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">{{ editingId ? '保存修改' : '确认录入' }}</el-button></template>
    </el-dialog>

    <el-dialog v-if="canMaintain" v-model="importDialog" title="Excel 导入预览" width="660px">
      <div v-loading="importing">
        <el-alert v-if="importPreview?.error_count" type="error" :closable="false" title="文件存在格式错误，整批数据不会写入。" />
        <el-alert v-else type="success" :closable="false" title="预览校验通过，确认后将使用一个事务写入。" />
        <div class="preview-metrics">
          <span><small>有效行</small><b>{{ importPreview?.valid_count || 0 }}</b></span><span><small>错误行</small><b>{{ importPreview?.error_count || 0 }}</b></span><span><small>重复日期</small><b>{{ importPreview?.duplicate_count || 0 }}</b></span><span><small>预计新增</small><b>{{ importPreview?.will_create || 0 }}</b></span>
        </div>
        <el-switch v-model="overwrite" active-text="覆盖已有日期" inactive-text="跳过已有日期" />
        <el-table v-if="importPreview?.errors?.length" :data="importPreview.errors" max-height="240"><el-table-column prop="row" label="行号" width="80" /><el-table-column prop="message" label="错误说明" /></el-table>
        <el-table v-else-if="importPreview?.duplicates?.length" :data="importPreview.duplicates" max-height="240"><el-table-column prop="row" label="行号" width="80" /><el-table-column prop="date" label="重复日期" /></el-table>
      </div>
      <template #footer><el-button @click="importDialog=false">取消</el-button><el-button type="primary" :loading="importing" :disabled="!!importPreview?.error_count" @click="commitImport">确认导入</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.head-actions{display:flex;gap:12px}.metric-card small{font-size:12px;color:var(--muted)}.revenue{background:linear-gradient(135deg,#0b766f,#159087);color:#fff}.revenue .metric-label,.revenue .metric-hint{color:rgba(255,255,255,.7)}.trend{margin-top:18px}.chart-head{display:flex;justify-content:space-between;align-items:center}.chart-head span,.list-head span{font-size:11px;color:var(--muted)}.sub-chart{height:260px}.data-list{margin-top:18px;overflow:hidden}.list-head{padding:20px 22px;display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid var(--line)}.list-head .section-title{margin-bottom:4px}.list-head>div:last-child{display:flex;gap:8px;flex-wrap:wrap}.import-button{height:32px;padding:0 15px;display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:4px;color:#5b6867;font-size:12px;cursor:pointer}.import-button:hover{border-color:var(--brand);color:var(--brand)}.import-button input{display:none}.mobile-data-list{display:none}.data-form{display:grid;grid-template-columns:1fr 1fr;gap:0 16px;margin-top:18px}.data-form :deep(.el-input-number),.data-form :deep(.el-date-editor){width:100%}.preview-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}.preview-metrics span{padding:12px;background:#f3f7f6;border-radius:9px;display:flex;flex-direction:column;gap:4px}.preview-metrics small{color:var(--muted)}.preview-metrics b{font-size:20px}
@media(max-width:760px){
  .head-actions{width:100%;justify-content:space-between;flex-wrap:wrap}.chart{height:280px}.chart-head{align-items:flex-start;flex-direction:column}.list-head{align-items:flex-start;flex-direction:column}.data-list{overflow:hidden}.desktop-data-table{display:none}.mobile-data-list{display:block}
  .mobile-data-row{border-bottom:1px solid var(--line);background:#fff}.mobile-data-row:last-child{border-bottom:0}.mobile-data-row.expanded{background:#fbfdfc}
  .mobile-data-summary{width:100%;border:0;background:transparent;color:inherit;padding:15px 14px;display:grid;grid-template-columns:1.2fr .65fr 1fr 18px;align-items:center;gap:10px;text-align:left;cursor:pointer}
  .mobile-data-summary span{min-width:0;display:flex;flex-direction:column;gap:4px}.mobile-data-summary small{font-size:10px;color:var(--muted)}.mobile-data-summary b{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mobile-data-summary span:first-child b{font-size:13px}
  .expand-icon{color:#849391;transition:transform .2s}.mobile-data-row.expanded .expand-icon{transform:rotate(180deg);color:var(--brand)}
  .mobile-data-panel{padding:0 14px 15px}.mobile-data-meta{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:12px 0;border-top:1px dashed #dfe8e6}.mobile-data-meta span{display:flex;flex-direction:column;gap:4px}.mobile-data-meta small{font-size:10px;color:var(--muted)}.mobile-data-meta b{font-size:12px}
  .mobile-data-sources{padding:10px 12px;margin-bottom:12px;border-radius:8px;background:#f3f7f6;color:var(--muted);font-size:11px;line-height:1.6}.mobile-data-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.mobile-data-actions :deep(.el-button){width:100%;margin:0}
  .data-expand-enter-active,.data-expand-leave-active{transition:opacity .18s ease,transform .18s ease}.data-expand-enter-from,.data-expand-leave-to{opacity:0;transform:translateY(-4px)}
  .data-form{grid-template-columns:1fr}.preview-metrics{grid-template-columns:1fr 1fr}:deep(.el-dialog){width:calc(100% - 24px)!important}
}
</style>
