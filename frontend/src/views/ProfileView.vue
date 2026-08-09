<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Connection, DataAnalysis, OfficeBuilding, TrendCharts } from '@element-plus/icons-vue'
import api from '@/services/api'
import { session } from '@/stores/session'

const profile = ref<any>(null)
const loading = ref(true)
const merchantId = computed(() => session.selectedMerchantId || session.user?.merchant_id)
onMounted(async()=>{try{profile.value=await api.get(`/merchants/${merchantId.value}/profile`)}finally{loading.value=false}})
const cards = computed(()=> profile.value ? [
  { label:'经营规模',value:profile.value.business_scale,icon:OfficeBuilding,tone:'green' },
  { label:'数字化程度',value:profile.value.digital_level,icon:DataAnalysis,tone:'blue' },
  { label:'网络状况',value:profile.value.network_status,icon:Connection,tone:'orange' },
  { label:'所属行业',value:profile.value.industry,icon:TrendCharts,tone:'violet' },
] : [])
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head"><div><h1 class="page-title">商户画像</h1><p class="page-subtitle">基于档案与经营数据生成，所有结论都有明确判断依据</p></div><span class="rule-badge">透明规则 · 实时计算</span></div>
    <template v-if="profile">
      <section class="portrait-hero card">
        <div class="rings"><i></i><i></i><span>{{ profile.industry.slice(0,1) }}</span></div>
        <div class="portrait-copy"><span class="eyebrow">MERCHANT PORTRAIT</span><h2>{{ profile.business_scale }}</h2><p>{{ profile.digital_level }} · {{ profile.network_status }}</p><div class="portrait-tags"><span v-for="need in profile.core_needs" :key="need">{{ need }}</span></div></div>
        <div class="confidence"><b>规则命中</b><strong>100%</strong><small>画像随档案与经营数据实时更新</small></div>
      </section>
      <div class="profile-grid">
        <div v-for="card in cards" :key="card.label" class="card profile-card"><span :class="card.tone"><component :is="card.icon" /></span><small>{{ card.label }}</small><b>{{ card.value }}</b></div>
      </div>
      <section class="card card-pad evidence">
        <div class="section-head"><h3 class="section-title">判断依据</h3><span>不使用黑盒算法</span></div>
        <div class="evidence-table">
          <div v-for="(item,index) in profile.evidence" :key="item.label"><span class="num">0{{ Number(index)+1 }}</span><div><small>{{ item.label }}</small><b>{{ item.value }}</b></div><p>{{ item.reason }}</p></div>
        </div>
      </section>
      <section class="explain"><b>画像如何生成？</b><p>系统综合行业、人员规模、店铺面积、网络接入、近 30 日经营表现和需求标签，通过固定阈值与可读规则实时计算。修改资料后，画像和推荐会同步变化。</p></section>
    </template>
  </div>
</template>

<style scoped>
.rule-badge{font-size:11px;background:#e6f4f1;color:var(--brand);padding:7px 10px;border-radius:7px}.portrait-hero{min-height:230px;padding:34px 38px;display:grid;grid-template-columns:170px 1fr 180px;align-items:center;gap:28px;background:linear-gradient(110deg,#fff,#e9f6f2);overflow:hidden}.rings{position:relative;width:150px;height:150px;display:grid;place-items:center}.rings i{position:absolute;inset:0;border:1px solid #b9ddd7;border-radius:50%}.rings i:nth-child(2){inset:16px;border:1px dashed #63aaa2}.rings span{width:90px;height:90px;border-radius:50%;background:linear-gradient(145deg,#0b766f,#2aa397);color:#fff;font-size:34px;font-weight:800;display:grid;place-items:center;box-shadow:0 15px 28px rgba(11,118,111,.2)}.portrait-copy{min-width:0}.eyebrow{font-size:10px;color:var(--brand);letter-spacing:2px}.portrait-hero h2{margin:10px 0 5px;font-size:30px}.portrait-hero p{color:var(--muted);margin:0 0 18px}.portrait-tags{display:flex;flex-wrap:wrap;align-items:center;gap:7px}.portrait-tags span{max-width:100%;font-size:11px;line-height:1.35;background:#fff;border:1px solid #dbeae7;border-radius:7px;padding:6px 9px;overflow-wrap:anywhere}.confidence{display:flex;flex-direction:column;border-left:1px solid #d8e9e6;padding-left:25px}.confidence b{font-size:11px;color:var(--muted)}.confidence strong{font-size:30px;color:var(--brand);margin:5px 0}.confidence small{color:var(--muted);line-height:1.6}.profile-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-top:18px}.profile-card{padding:20px;display:grid;grid-template-columns:42px 1fr;grid-template-rows:auto auto;column-gap:12px}.profile-card>span{grid-row:span 2;width:42px;height:42px;border-radius:11px;padding:10px}.profile-card svg{width:100%}.profile-card .green{background:#e1f2ee;color:#0b766f}.profile-card .blue{background:#e5eef9;color:#427ab6}.profile-card .orange{background:#fff0e4;color:#d97736}.profile-card .violet{background:#eeeafb;color:#755ab7}.profile-card small{color:var(--muted)}.profile-card b{font-size:14px;margin-top:4px}.evidence{margin-top:18px}.section-head{display:flex;justify-content:space-between}.section-head span{font-size:11px;color:#458d86}.evidence-table>div{display:grid;grid-template-columns:40px 270px 1fr;gap:15px;align-items:center;padding:17px 5px;border-top:1px solid var(--line)}.num{font-size:12px;color:#9ba6a4}.evidence-table div>div{display:flex;flex-direction:column;gap:5px}.evidence-table small{color:var(--muted)}.evidence-table p{color:#687775;font-size:12px}.explain{margin-top:18px;padding:18px 22px;border-radius:13px;border:1px solid #d9eae7;background:#edf7f5;display:flex;gap:18px;font-size:12px}.explain b{white-space:nowrap;color:var(--brand)}.explain p{margin:0;color:#58706d;line-height:1.7}
@media(max-width:760px){.portrait-hero{grid-template-columns:90px minmax(0,1fr);padding:24px 18px;gap:15px}.rings{width:85px;height:85px}.rings span{width:55px;height:55px;font-size:22px}.portrait-hero h2{font-size:25px;line-height:1.25}.portrait-hero p{font-size:13px;line-height:1.55;margin-bottom:14px}.portrait-tags{gap:6px}.portrait-tags span{font-size:12px}.confidence{grid-column:1/-1;border:0;border-top:1px solid #d8e9e6;padding:15px 0 0}.profile-grid{grid-template-columns:1fr 1fr}.evidence-table>div{grid-template-columns:28px 1fr}.evidence-table p{grid-column:2}.explain{flex-direction:column;gap:5px}}
</style>
