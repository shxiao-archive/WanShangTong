<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Edit, Location, Plus, Phone, Picture, Timer, User } from '@element-plus/icons-vue'
import api from '@/services/api'
import { session } from '@/stores/session'
import type { Merchant, Product } from '@/types'
import AuthenticatedImage from '@/components/AuthenticatedImage.vue'

const merchant = ref<Merchant | null>(null)
const loading = ref(true)
const editing = ref(false)
const form = reactive<any>({})
const managingProducts = ref(false)
const productForm = ref<Product[]>([])
const uploadingIndex = ref<number | null>(null)
const productSaving = ref(false)
const merchantId = computed(() => session.selectedMerchantId || session.user?.merchant_id)
const canMaintain = computed(() => session.user?.role === 'merchant')

async function load() {
  if (!merchantId.value) return
  loading.value = true
  try { merchant.value = await api.get(`/merchants/${merchantId.value}`) } finally { loading.value = false }
}
function startEdit() { Object.assign(form, JSON.parse(JSON.stringify(merchant.value))); editing.value = true }
function startProductEdit() {
  productForm.value = (merchant.value?.products || []).map(product => ({ ...product }))
  managingProducts.value = true
}
function addProduct() {
  productForm.value.push({ id: crypto.randomUUID(), name: '', category: '', price: 0, image_id: null })
}
function removeProduct(index: number) {
  productForm.value.splice(index, 1)
}
async function uploadProductImage(index: number, event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    return ElMessage.warning('仅支持 JPG、PNG 或 WebP 图片')
  }
  if (file.size > 10 * 1024 * 1024) return ElMessage.warning('商品图片不能超过 10MB')
  uploadingIndex.value = index
  try {
    const data = new FormData()
    data.append('image', file)
    const result = await api.post(`/merchants/${merchantId.value}/product-images`, data)
    productForm.value[index].image_id = result.id
    ElMessage.success('图片上传成功')
  } finally {
    uploadingIndex.value = null
  }
}
async function saveProducts() {
  const invalid = productForm.value.some(product => !product.name.trim() || !product.category.trim() || product.price < 0)
  if (invalid) return ElMessage.warning('请完善每件商品的名称、分类和价格')
  if (!merchant.value) return
  productSaving.value = true
  try {
    merchant.value = await api.put(`/merchants/${merchantId.value}`, {
      ...merchant.value,
      products: productForm.value.map(product => ({
        ...product,
        name: product.name.trim(),
        category: product.category.trim(),
      })),
    })
    managingProducts.value = false
    ElMessage.success('商品与图片已保存')
  } finally {
    productSaving.value = false
  }
}
async function save() {
  merchant.value = await api.put(`/merchants/${merchantId.value}`, form)
  editing.value = false
  ElMessage.success('店铺档案已保存，画像与推荐将同步更新')
}
onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head"><div><h1 class="page-title">{{ session.user?.role === 'operator' ? '商户档案' : '我的店铺' }}</h1><p class="page-subtitle">{{ canMaintain ? '完整、准确的档案能帮助平台提供更适配的经营建议' : '查看商户基础档案、经营信息与商品服务' }}</p></div><el-button v-if="merchant && canMaintain" type="primary" :icon="Edit" @click="startEdit">编辑资料</el-button></div>
    <template v-if="merchant">
      <section class="store-hero card">
        <div class="cover"><span>{{ merchant.industry }}</span><i></i><i></i><i></i></div>
        <div class="store-info">
          <div class="store-title"><div><span class="industry">{{ merchant.industry }}</span><span v-if="merchant.is_demo" class="demo-label">演示数据</span><h2>{{ merchant.name }}</h2><div><span v-for="tag in merchant.tags" :key="tag" class="tag">{{ tag }}</span></div></div><span :class="['open-status',merchant.status]">{{ merchant.status==='enabled'?'营业中':'已停用' }}</span></div>
          <div class="info-grid">
            <span><Location /><i>经营地址</i><b>{{ merchant.address }}</b></span>
            <span><Phone /><i>联系电话</i><b>{{ merchant.phone }}</b></span>
            <span><Timer /><i>营业时间</i><b>{{ merchant.business_hours }}</b></span>
            <span><User /><i>店铺联系人</i><b>{{ merchant.contact_name }}</b></span>
          </div>
        </div>
      </section>
      <div class="store-columns">
        <section class="card card-pad">
          <h3 class="section-title">经营基础</h3>
          <div class="facts"><div><span>经营规模</span><b>{{ merchant.scale }}</b></div><div><span>员工人数</span><b>{{ merchant.employee_count }} 人</b></div><div><span>店铺面积</span><b>{{ merchant.store_area }} ㎡</b></div><div><span>当前网络</span><b>{{ merchant.network_environment }}</b><small>{{ merchant.bandwidth_mbps }}Mbps</small></div></div>
        </section>
        <section class="card card-pad">
          <h3 class="section-title">数字化需求</h3>
          <p class="muted">平台将根据以下需求生成画像与推荐</p>
          <div class="needs"><span v-for="need in merchant.needs" :key="need">{{ need }}</span></div>
        </section>
      </div>
      <section class="card card-pad products">
        <div class="section-heading">
          <h3 class="section-title">主要商品与服务</h3>
          <el-button v-if="canMaintain" type="primary" plain :icon="Picture" @click="startProductEdit">管理商品与图片</el-button>
        </div>
        <div v-if="merchant.products.length" class="product-grid">
          <div v-for="(product,index) in merchant.products" :key="`${product.name}-${index}`">
            <div class="product-image" :class="[!product.image_id ? `tone-${index%3}` : '', { 'has-photo': !!product.image_id }]">
              <AuthenticatedImage
                v-if="product.image_id"
                class="product-photo"
                :image-id="product.image_id"
                :alt="product.name"
                fit="contain"
              />
              <span v-else>{{ product.name.slice(0,1) }}</span>
            </div>
            <span>{{ product.category }}</span><b>{{ product.name }}</b><strong>¥{{ product.price }}</strong>
          </div>
        </div>
        <el-empty v-else description="暂未添加商品" :image-size="72"><el-button v-if="canMaintain" type="primary" :icon="Plus" @click="startProductEdit">添加第一个商品</el-button></el-empty>
      </section>
    </template>

    <el-dialog v-if="canMaintain" v-model="editing" title="编辑店铺资料" width="680px">
      <el-form label-position="top"><div class="edit-grid">
        <el-form-item label="商户名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="所属行业"><el-select v-model="form.industry"><el-option v-for="i in ['餐饮','零售','生活服务','住宿']" :key="i" :value="i" /></el-select></el-form-item>
        <el-form-item label="联系人"><el-input v-model="form.contact_name" /></el-form-item><el-form-item label="联系电话"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item class="wide" label="经营地址"><el-input v-model="form.address" /></el-form-item><el-form-item label="营业时间"><el-input v-model="form.business_hours" /></el-form-item>
        <el-form-item label="经营规模"><el-select v-model="form.scale"><el-option v-for="i in ['小微','中小','中型']" :key="i" :value="i" /></el-select></el-form-item>
        <el-form-item label="员工人数"><el-input-number v-model="form.employee_count" :min="0" /></el-form-item>
        <el-form-item label="店铺面积（㎡）"><el-input-number v-model="form.store_area" :min="0" /></el-form-item>
        <el-form-item label="网络环境"><el-select v-model="form.network_environment"><el-option v-for="i in ['无固定宽带','移动热点','共享网络','普通宽带','千兆宽带','企业专线']" :key="i" :value="i" /></el-select></el-form-item>
        <el-form-item label="当前带宽（Mbps）"><el-input-number v-model="form.bandwidth_mbps" :min="0" /></el-form-item>
        <el-form-item class="wide" label="数字化需求"><el-select v-model="form.needs" multiple filterable allow-create><el-option v-for="i in ['高速网络','稳定网络','扫码点餐','视频监控','线上营销','会员系统','短视频推广','直播带货','线上预约','全屋 Wi-Fi']" :key="i" :value="i" /></el-select></el-form-item>
      </div></el-form>
      <template #footer><el-button @click="editing=false">取消</el-button><el-button type="primary" @click="save">保存更新</el-button></template>
    </el-dialog>

    <el-dialog v-if="canMaintain" v-model="managingProducts" title="管理商品与图片" width="720px" class="product-dialog">
      <div class="product-editor-list">
        <article v-for="(product,index) in productForm" :key="index" class="product-editor">
          <div class="product-editor-image" :class="{ empty: !product.image_id }">
            <AuthenticatedImage
              v-if="product.image_id"
              class="product-editor-photo"
              :image-id="product.image_id"
              :alt="product.name || '商品图片'"
              fit="contain"
            />
            <el-icon v-else><Picture /></el-icon>
          </div>
          <div class="product-editor-fields">
            <el-input v-model="product.name" maxlength="80" placeholder="商品或服务名称" />
            <el-input v-model="product.category" maxlength="50" placeholder="商品分类，如：招牌菜" />
            <el-input-number v-model="product.price" :min="0" :max="99999999" :precision="2" controls-position="right" />
          </div>
          <div class="product-editor-actions">
            <label class="image-upload-button" :class="{ disabled: uploadingIndex !== null }">
              <input type="file" accept="image/jpeg,image/png,image/webp" :disabled="uploadingIndex !== null" @change="uploadProductImage(index,$event)" />
              {{ uploadingIndex === index ? '上传中…' : (product.image_id ? '更换图片' : '上传图片') }}
            </label>
            <el-button v-if="product.image_id" link @click="product.image_id=null">移除图片</el-button>
            <el-button link type="danger" :icon="Delete" @click="removeProduct(index)">删除商品</el-button>
          </div>
        </article>
        <el-empty v-if="!productForm.length" description="还没有商品，点击下方按钮开始添加" :image-size="72" />
      </div>
      <el-button class="add-product" plain type="primary" :icon="Plus" @click="addProduct">添加商品</el-button>
      <p class="upload-tip">支持 JPG、PNG、WebP，单张不超过 10MB</p>
      <template #footer>
        <el-button @click="managingProducts=false">取消</el-button>
        <el-button type="primary" :loading="productSaving" :disabled="uploadingIndex !== null" @click="saveProducts">保存商品</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.demo-label{font-size:9px;margin-left:8px;padding:3px 6px;border-radius:5px;background:#fff0e5;color:#c7672d}
.store-hero{overflow:hidden;display:grid;grid-template-columns:300px 1fr}.cover{min-height:230px;position:relative;overflow:hidden;background:linear-gradient(145deg,#174e49,#e18a45);display:grid;place-items:center}.cover>span{position:relative;z-index:3;color:#fff;border:1px solid rgba(255,255,255,.55);padding:12px 18px;letter-spacing:4px;font-size:14px}.cover i{position:absolute;width:220px;height:220px;border-radius:50%;border:30px solid rgba(255,255,255,.07)}.cover i:nth-child(2){left:-100px;top:-80px}.cover i:nth-child(3){right:-100px;bottom:-110px}.cover i:nth-child(4){width:90px;height:90px;border-width:15px;right:30px;top:25px}.store-info{padding:28px 32px}.store-title{display:flex;justify-content:space-between}.industry{font-size:11px;color:var(--brand);font-weight:700}.store-title h2{font-size:25px;margin:8px 0 10px}.open-status{font-size:12px;padding:6px 10px;height:max-content;border-radius:7px;background:#e4f6ec;color:#168052}.open-status.disabled{background:#eee;color:#888}.info-grid{border-top:1px solid var(--line);margin-top:20px;padding-top:18px;display:grid;grid-template-columns:1fr 1fr;gap:17px}.info-grid>span{display:grid;grid-template-columns:20px 80px 1fr;align-items:center;font-size:12px}.info-grid svg{width:15px;color:var(--brand)}.info-grid i{font-style:normal;color:var(--muted)}.info-grid b{font-weight:600}.store-columns{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px}.facts{display:grid;grid-template-columns:repeat(4,1fr)}.facts>div{display:flex;flex-direction:column;border-right:1px solid var(--line);padding:0 15px}.facts>div:first-child{padding-left:0}.facts>div:last-child{border:0}.facts span,.facts small,.muted{font-size:11px;color:var(--muted)}.facts b{margin-top:9px;font-size:16px}.facts small{margin-top:3px}.muted{margin-top:-10px}.needs{display:flex;flex-wrap:wrap;gap:8px}.needs span{padding:7px 11px;border-radius:8px;background:#eef8f6;color:var(--brand-dark);font-size:12px}.products{margin-top:18px}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.section-heading .section-title{margin-bottom:0}.product-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:20px}.product-grid>div{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px}.product-image{grid-column:1/-1;height:120px;border-radius:12px;background:linear-gradient(135deg,#d4ebe5,#7cb4a5);display:grid;place-items:center;margin-bottom:7px;overflow:hidden}.product-image.has-photo{background:#f3f6f5}.product-photo{width:100%;height:100%;cursor:zoom-in}.product-image span{font-size:35px;color:rgba(255,255,255,.8);font-weight:800}.tone-1{background:linear-gradient(135deg,#ffe3c7,#d98951)}.tone-2{background:linear-gradient(135deg,#e7decf,#9e896a)}.product-grid>div>span{font-size:10px;color:var(--muted);grid-column:1/-1}.product-grid b{font-size:13px;overflow-wrap:anywhere}.product-grid strong{font-size:13px;color:#d86b2f}.edit-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}.edit-grid .wide{grid-column:1/-1}.edit-grid :deep(.el-select),.edit-grid :deep(.el-input-number){width:100%}.product-editor-list{display:grid;gap:14px;max-height:58vh;overflow:auto;padding-right:4px}.product-editor{display:grid;grid-template-columns:120px minmax(0,1fr);gap:14px;padding:14px;border:1px solid var(--line);border-radius:12px}.product-editor-image{grid-row:1/3;width:120px;height:120px;border-radius:10px;overflow:hidden;background:#f1f7f6;display:grid;place-items:center}.product-editor-photo{width:100%;height:100%;cursor:zoom-in}.product-editor-image svg{width:30px;height:30px;color:var(--muted)}.product-editor-fields{display:grid;grid-template-columns:1fr 1fr 150px;gap:10px}.product-editor-fields :deep(.el-input-number){width:100%}.product-editor-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.image-upload-button{height:30px;box-sizing:border-box;display:inline-flex;align-items:center;padding:0 12px;border:1px solid var(--brand);border-radius:4px;color:var(--brand);font-size:12px;cursor:pointer}.image-upload-button:hover{background:#eef8f6}.image-upload-button.disabled{opacity:.55;cursor:not-allowed}.image-upload-button input{display:none}.add-product{margin-top:16px;width:100%}.upload-tip{text-align:center;color:var(--muted);font-size:11px;margin:8px 0 0}
@media(max-width:800px){.store-hero{grid-template-columns:1fr}.cover{min-height:160px}.store-info{padding:20px}.info-grid{grid-template-columns:1fr}.store-columns{grid-template-columns:1fr}.facts{grid-template-columns:1fr 1fr;gap:18px}.facts>div{align-items:center;text-align:center;padding:0 10px}.facts>div:first-child{padding-left:10px}.facts>div:nth-child(2){border:0}.product-grid{grid-template-columns:1fr 1fr}.edit-grid{grid-template-columns:1fr}.edit-grid .wide{grid-column:auto}.section-heading{align-items:flex-start}.section-heading :deep(.el-button){height:auto;min-height:32px;white-space:normal}.product-editor{grid-template-columns:86px minmax(0,1fr);gap:10px;padding:10px}.product-editor-image{width:86px;height:86px}.product-editor-fields{grid-template-columns:1fr}.product-editor-actions{grid-column:1/-1;gap:8px}.product-editor-list{max-height:62vh}:deep(.el-dialog){width:calc(100% - 24px)!important}}
</style>
