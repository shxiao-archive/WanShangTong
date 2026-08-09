<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Connection, Goods, Histogram, Shop, TrendCharts } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import api from '@/services/api'
import { session } from '@/stores/session'

use([CanvasRenderer, BarChart, PieChart, GridComponent, LegendComponent, TooltipComponent])
const router = useRouter()
const loading = ref(true)
const overview = ref<any>(null)
const summary = ref<any>(null)
const profile = ref<any>(null)
const dataScope = ref<'real' | 'demo'>('real')
const isOperator = computed(() => session.user?.role === 'operator')

const industryOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 10, right: 10, top: 10, bottom: 10, containLabel: true },
  xAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: '#edf1ef' } } },
  yAxis: { type: 'category', data: Object.keys(overview.value?.industry_distribution || {}), axisTick: { show: false }, axisLine: { show: false } },
  series: [{ type: 'bar', barWidth: 15, data: Object.values(overview.value?.industry_distribution || {}), itemStyle: { color: '#16877e', borderRadius: [0, 6, 6, 0] } }],
}))

async function load() {
  loading.value = true
  try {
    if (isOperator.value) {
      overview.value = await api.get('/dashboard/overview', { params: { data_scope: dataScope.value } })
    } else if (session.selectedMerchantId) {
      ;[summary.value, profile.value] = await Promise.all([
        api.get(`/merchants/${session.selectedMerchantId}/business-summary`, { params: { days: 7 } }),
        api.get(`/merchants/${session.selectedMerchantId}/profile`),
      ])
    }
  } finally { loading.value = false }
}
watch(dataScope, load)
onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="hero-head">
      <div>
        <span class="date-label">今日经营简报</span>
        <h1 v-if="isOperator">运营全景，<br class="operator-title-break">一目了然</h1>
        <h1 v-else>你好，{{ session.user?.display_name }}</h1>
        <p>{{ isOperator ? '掌握辖区商户状态，发现值得关注的增长机会。' : '生意的每一步变化，都值得被认真看见。' }}</p>
      </div>
      <el-segmented v-if="isOperator" v-model="dataScope" :options="[{label:'正式数据',value:'real'},{label:'演示数据',value:'demo'}]" />
    </div>

    <template v-if="isOperator && overview">
      <div class="metric-grid">
        <div class="card metric-card"><span class="metric-label">入驻商户</span><div class="metric-value">{{ overview.merchant_count }} <small>家</small></div><div class="metric-hint">覆盖万州核心商圈</div></div>
        <div class="card metric-card"><span class="metric-label">正常运营</span><div class="metric-value">{{ overview.active_count }} <small>家</small></div><div class="metric-hint">运营状态稳定</div></div>
        <div class="card metric-card"><span class="metric-label">覆盖行业</span><div class="metric-value">{{ Object.keys(overview.industry_distribution).length }} <small>类</small></div><div class="metric-hint">餐饮与零售为主</div></div>
        <div class="card metric-card highlight"><span class="metric-label">待跟进</span><div class="metric-value">{{ overview.pending_application_count }} <small>项</small></div><div class="metric-hint">等待运营处理的申请</div></div>
      </div>
      <div class="two-col">
        <section class="card card-pad"><h2 class="section-title">行业分布</h2><v-chart class="chart small-chart" :option="industryOption" autoresize /></section>
      <section class="card card-pad"><h2 class="section-title">热门数字化需求</h2><div class="need-list"><div v-for="(item,index) in overview.popular_needs" :key="item.name"><span class="rank">{{ Number(index) + 1 }}</span><b>{{ item.name }}</b><div class="bar"><i :style="{ width: `${Math.min(100,item.count / overview.active_count * 100)}%` }"></i></div><strong>{{ item.count }}</strong></div></div></section>
      </div>
      <section class="quick card">
        <div><span class="quick-icon"><Shop /></span><p><b>商户管理</b><small>搜索、筛选与维护商户档案</small></p><el-button text :icon="ArrowRight" @click="router.push('/merchants')">进入</el-button></div>
        <div><span class="quick-icon orange"><Goods /></span><p><b>资源管理</b><small>维护推荐套餐与数字服务</small></p><el-button text :icon="ArrowRight" @click="router.push('/resources')">进入</el-button></div>
      </section>
    </template>

    <template v-else-if="summary">
      <div class="metric-grid">
        <div class="card metric-card"><span class="metric-label">今日到店访客</span><div class="metric-value">{{ summary.today.visitors }} <small>人</small></div><div class="metric-hint">门店热度平稳</div></div>
        <div class="card metric-card"><span class="metric-label">今日订单</span><div class="metric-value">{{ summary.today.orders }} <small>单</small></div><div class="metric-hint">转化表现良好</div></div>
        <div class="card metric-card highlight"><span class="metric-label">今日营业额</span><div class="metric-value">¥{{ summary.today.revenue.toLocaleString() }}</div><div class="metric-hint">继续保持经营节奏</div></div>
        <div class="card metric-card"><span class="metric-label">顾客评分</span><div class="metric-value">{{ summary.today.rating }} <small>/ 5</small></div><div class="metric-hint">顾客口碑优良</div></div>
      </div>
      <div class="two-col">
        <section class="card card-pad">
          <div class="portrait-head"><div><span>本店数字画像</span><h2>{{ profile?.business_scale }}</h2></div><span class="portrait-score">{{ profile?.digital_level }}</span></div>
          <div class="portrait-items"><span><Connection />{{ profile?.network_status }}</span><span><TrendCharts />近 7 日营收 ¥{{ summary.totals.revenue.toLocaleString() }}</span></div>
          <div class="core-needs"><small>当前核心需求</small><div><span v-for="need in profile?.core_needs" :key="need" class="tag">{{ need }}</span></div></div>
          <el-button type="primary" plain @click="router.push('/portrait')">查看完整画像</el-button>
        </section>
        <section class="card card-pad action-list">
          <h2 class="section-title">常用功能</h2>
          <button @click="router.push('/analytics')"><Histogram /><span><b>查看经营分析</b><small>趋势、订单来源与营业高峰</small></span><ArrowRight /></button>
          <button @click="router.push('/recommendations')"><Goods /><span><b>获取资源推荐</b><small>找到适合门店的数字化服务</small></span><ArrowRight /></button>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.hero-head { margin: -28px -30px 24px; padding: 35px 40px 30px; background: linear-gradient(110deg,#e5f4f0,#f8f8f2); display: flex; justify-content: space-between; align-items: center; }
.date-label { font-size: 11px; color: var(--brand); font-weight: 700; letter-spacing: 1px; }
.hero-head h1 { font-size: 29px; margin: 8px 0; letter-spacing: -.6px; }
.operator-title-break { display: none; }
.hero-head p { margin: 0; color: #647674; font-size: 14px; }
.metric-card small { font-size: 12px; font-weight: 500; color: var(--muted); }
.metric-card.highlight { background: linear-gradient(135deg,#0c716a,#169086); color: #fff; }
.highlight .metric-label,.highlight .metric-hint,.highlight small { color: rgba(255,255,255,.7); }
.small-chart { height: 255px; }
.need-list > div { display: grid; grid-template-columns: 24px 95px 1fr 22px; align-items: center; gap: 8px; margin: 17px 0; font-size: 12px; }
.rank { color: #8d9b99; font-size: 11px; }
.bar { height: 7px; border-radius: 5px; background: #eef2f1; overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg,#19a095,#53b5aa); }
.need-list strong { text-align: right; color: var(--brand); }
.quick { margin-top: 18px; display: grid; grid-template-columns: 1fr 1fr; }
.quick > div { display: flex; align-items: center; padding: 18px 22px; }
.quick > div:first-child { border-right: 1px solid var(--line); }
.quick-icon { width: 42px; height: 42px; padding: 10px; background: var(--brand-soft); color: var(--brand); border-radius: 10px; }
.quick-icon.orange { background: #fff0e7; color: #dd6b2d; }
.quick p { display: flex; flex-direction: column; flex: 1; margin: 0 10px; font-size: 13px; }
.quick p small { color: var(--muted); margin-top: 4px; }
.portrait-head { display: flex; justify-content: space-between; align-items: flex-start; }
.portrait-head span { color: var(--muted); font-size: 12px; }
.portrait-head h2 { margin: 8px 0 20px; font-size: 26px; }
.portrait-score { background: #e6f5f1; color: var(--brand) !important; padding: 7px 10px; border-radius: 8px; font-weight: 700; }
.portrait-items { display: flex; gap: 20px; margin-bottom: 20px; color: #4b605e; font-size: 12px; }
.portrait-items span { display: flex; align-items: center; gap: 6px; }
.portrait-items svg { width: 16px; color: var(--brand); }
.core-needs { border-top: 1px solid var(--line); padding: 17px 0; }
.core-needs small { color: var(--muted); display: block; margin-bottom: 8px; }
.action-list button { width: 100%; display: flex; align-items: center; gap: 12px; padding: 15px 0; border: 0; border-bottom: 1px solid var(--line); background: transparent; text-align: left; cursor: pointer; color: var(--brand); }
.action-list button > svg { width: 23px; }
.action-list button span { flex: 1; display: flex; flex-direction: column; color: var(--ink); }
.action-list button small { color: var(--muted); margin-top: 4px; }
.action-list button > svg:last-child { width: 15px; color: #95a19f; }
@media (max-width: 900px) {
  .hero-head { margin: -20px -16px 20px; padding: 25px 18px; }
  .operator-title-break { display: block; }
  .quick { grid-template-columns: 1fr; }
  .quick > div:first-child { border-right: 0; border-bottom: 1px solid var(--line); }
}
</style>
