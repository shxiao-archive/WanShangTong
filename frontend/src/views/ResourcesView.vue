<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import api from '@/services/api'
import type { Resource } from '@/types'

const items=ref<Resource[]>([])
const loading=ref(true)
const keyword=ref('')
const dialog=ref(false)
const editingId=ref<number|null>(null)
const blank=()=>({name:'',category:'网络',description:'',price:99,unit:'元/月',bandwidth_mbps:null as number|null,target_industries:[] as string[],matched_needs:[] as string[],included_services:[] as string[],is_universal:false,status:'enabled' as 'enabled'|'disabled'})
const form=reactive(blank())
const filtered=()=>items.value.filter(i=>!keyword.value||i.name.includes(keyword.value)||i.category.includes(keyword.value))
async function load(){loading.value=true;try{items.value=await api.get('/resources')}finally{loading.value=false}}
function create(){editingId.value=null;Object.assign(form,blank());dialog.value=true}
function edit(item:Resource){editingId.value=item.id;Object.assign(form,JSON.parse(JSON.stringify(item)));dialog.value=true}
async function save(){if(!form.name||!form.description)return ElMessage.warning('请填写资源名称和说明');if(editingId.value)await api.put(`/resources/${editingId.value}`,form);else await api.post('/resources',form);ElMessage.success('推荐资源已保存');dialog.value=false;load()}
async function toggle(item:Resource){await api.patch(`/resources/${item.id}/status`,{status:item.status==='enabled'?'disabled':'enabled'});ElMessage.success('资源状态已更新');load()}
onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1 class="page-title">资源管理</h1><p class="page-subtitle">维护宽带套餐和数字化服务，启停操作不会物理删除数据</p></div><el-button type="primary" :icon="Plus" @click="create">新增资源</el-button></div>
    <section class="card toolbar"><el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索资源名称或类型" /><div class="legend"><span><i class="on"></i>启用 {{ items.filter(i=>i.status==='enabled').length }}</span><span><i></i>停用 {{ items.filter(i=>i.status==='disabled').length }}</span></div></section>
    <section class="resource-grid" v-loading="loading">
      <article v-for="item in filtered()" :key="item.id" class="card resource">
        <div class="resource-head"><span :class="`cat ${item.category}`">{{ item.category }}</span><span class="resource-meta"><span :class="['state',item.status]">{{ item.status==='enabled'?'已启用':'已停用' }}</span><b>已订阅 {{ item.subscription_count }} 家</b></span></div>
        <h2>{{ item.name }}</h2><p>{{ item.description }}</p>
        <div class="price"><b>¥{{ item.price }}</b><span>/ {{ item.unit.replace('元/','') }}</span><em v-if="item.bandwidth_mbps">{{ item.bandwidth_mbps }}Mbps</em></div>
        <div class="match"><small>适配行业</small><span v-if="item.is_universal" class="tag">通用资源</span><span v-for="industry in item.target_industries" :key="industry" class="tag">{{ industry }}</span></div>
        <div class="services"><small>包含服务</small><p>{{ item.included_services.join(' · ') }}</p></div>
        <div class="resource-actions"><el-button link type="primary" @click="edit(item)">编辑详情</el-button><el-switch :model-value="item.status==='enabled'" @change="toggle(item)" /></div>
      </article>
    </section>
    <el-dialog v-model="dialog" :title="editingId?'编辑推荐资源':'新增推荐资源'" width="680px">
      <el-form label-position="top"><div class="resource-form">
        <el-form-item label="资源名称 *"><el-input v-model="form.name" /></el-form-item><el-form-item label="资源类型"><el-select v-model="form.category"><el-option v-for="i in ['网络','数字化','安防','营销','基础服务']" :key="i" :value="i" /></el-select></el-form-item>
        <el-form-item class="wide" label="资源说明 *"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item><el-form-item label="参考价格"><el-input-number v-model="form.price" :min="0" /></el-form-item><el-form-item label="计价单位"><el-input v-model="form.unit" /></el-form-item>
        <el-form-item label="带宽（Mbps，可选）"><el-input-number v-model="form.bandwidth_mbps" :min="0" /></el-form-item><el-form-item label="通用基础资源"><el-switch v-model="form.is_universal" /></el-form-item>
        <el-form-item class="wide" label="适配行业"><el-select v-model="form.target_industries" multiple><el-option v-for="i in ['餐饮','零售','生活服务','住宿']" :key="i" :value="i" /></el-select></el-form-item>
        <el-form-item class="wide" label="匹配需求"><el-select v-model="form.matched_needs" multiple filterable allow-create><el-option v-for="i in ['高速网络','稳定网络','扫码点餐','视频监控','线上营销','会员系统','短视频推广','直播带货','线上预约','全屋 Wi-Fi']" :key="i" :value="i" /></el-select></el-form-item>
        <el-form-item class="wide" label="包含服务"><el-select v-model="form.included_services" multiple filterable allow-create /></el-form-item>
      </div></el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存资源</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar{padding:15px 18px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center}.toolbar .el-input{width:310px}.legend{display:flex;gap:18px;font-size:11px;color:var(--muted)}.legend i{display:inline-block;width:7px;height:7px;border-radius:50%;background:#aab3b1;margin-right:5px}.legend i.on{background:#28a47a}.resource-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.resource{padding:21px;display:flex;flex-direction:column}.resource-head{display:flex;justify-content:space-between;align-items:flex-start}.resource-meta{display:flex;flex-direction:column;align-items:flex-end;gap:5px}.resource-meta b{font-size:10px;color:var(--brand);font-weight:600}.cat{font-size:10px;background:#e6f4f1;color:var(--brand);padding:5px 8px;border-radius:6px}.cat.营销{background:#fff0e6;color:#d77535}.cat.安防{background:#ebeff8;color:#4e6ea3}.state{font-size:10px;color:#288561}.state.disabled{color:#929c9a}.resource h2{font-size:17px;margin:14px 0 8px}.resource>p{font-size:11px;color:var(--muted);line-height:1.65;min-height:38px;margin:0}.price{margin:17px 0}.price b{font-size:22px;color:var(--brand)}.price span{font-size:10px;color:var(--muted)}.price em{font-style:normal;float:right;background:#f2f5f4;color:#667573;padding:4px 7px;border-radius:5px;font-size:10px}.match,.services{border-top:1px solid var(--line);padding-top:12px;margin-top:8px}.match small,.services small{display:block;color:var(--muted);font-size:10px;margin-bottom:6px}.services p{font-size:11px;color:#526664;min-height:28px}.resource-actions{border-top:1px solid var(--line);margin-top:auto;padding-top:12px;display:flex;justify-content:space-between}.resource-form{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}.resource-form .wide{grid-column:1/-1}.resource-form :deep(.el-select),.resource-form :deep(.el-input-number){width:100%}
@media(max-width:1000px){.resource-grid{grid-template-columns:1fr 1fr}}@media(max-width:650px){.toolbar{align-items:flex-start;flex-direction:column;gap:14px}.toolbar .el-input{width:100%}.resource-grid{grid-template-columns:1fr}.resource-form{grid-template-columns:1fr}.resource-form .wide{grid-column:auto}:deep(.el-dialog){width:calc(100% - 24px)!important}}
</style>
