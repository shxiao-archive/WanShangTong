<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Lock } from '@element-plus/icons-vue'
import api from '@/services/api'
import { session, setSession } from '@/stores/session'

const router = useRouter()
const loading = ref(false)
const form = reactive({ current_password: '', new_password: '', confirm_password: '' })
const firstLogin = computed(() => !!session.user?.must_change_password)

async function submit() {
  if (form.new_password !== form.confirm_password) return ElMessage.warning('两次输入的新密码不一致')
  loading.value = true
  try {
    const result = await api.post('/auth/change-password', {
      current_password: form.current_password,
      new_password: form.new_password,
    })
    setSession(result.user)
    ElMessage.success('密码已修改，请使用新密码继续')
    router.replace('/overview')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="password-page">
    <section class="password-card">
      <div class="mark"><DataAnalysis /></div>
      <h1>{{ firstLogin ? '首次登录，请设置新密码' : '修改登录密码' }}</h1>
      <p>密码为 8–32 位，至少包含一个英文字母和一个数字；区分大小写但不要求同时使用大小写字母，可以使用特殊字符。</p>
      <el-alert v-if="firstLogin" title="完成改密前，暂时不能进入其他功能。" type="warning" :closable="false" />
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="当前密码">
          <el-input v-model="form.current_password" type="password" show-password :prefix-icon="Lock" autocomplete="current-password" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="form.new_password" type="password" show-password :prefix-icon="Lock" autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="再次输入新密码">
          <el-input v-model="form.confirm_password" type="password" show-password :prefix-icon="Lock" autocomplete="new-password" @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" class="submit" :loading="loading" @click="submit">保存新密码</el-button>
      </el-form>
      <el-button v-if="!firstLogin" text class="back" @click="router.back()">返回平台</el-button>
    </section>
  </div>
</template>

<style scoped>
.password-page{min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 20% 0,#d8f0eb,transparent 38%),#f3f6f5}.password-card{width:min(460px,100%);padding:36px;background:#fff;border:1px solid var(--line);border-radius:20px;box-shadow:0 18px 60px rgba(17,66,62,.12)}.mark{width:44px;height:44px;padding:11px;border-radius:12px;background:var(--brand);color:#fff}.mark svg{width:100%;height:100%}h1{font-size:25px;margin:22px 0 8px}.password-card>p{font-size:13px;color:var(--muted);line-height:1.75;margin:0 0 18px}.el-alert{margin-bottom:20px}.submit{width:100%;height:44px}.back{width:100%;margin-top:10px}
@media(max-width:520px){.password-card{padding:25px 20px}h1{font-size:21px}}
</style>
