<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import api from '@/services/api'

const props = withDefaults(defineProps<{
  imageId: number
  alt?: string
  fit?: 'fill' | 'contain' | 'cover' | 'none' | 'scale-down'
  preview?: boolean
}>(), { alt: '', fit: 'contain', preview: true })

const source = ref('')
const loading = ref(false)

function release() {
  if (source.value) URL.revokeObjectURL(source.value)
  source.value = ''
}

async function load() {
  release()
  loading.value = true
  try {
    const blob = await api.get(`/media/${props.imageId}/content`, { responseType: 'blob' })
    source.value = URL.createObjectURL(blob)
  } finally {
    loading.value = false
  }
}

watch(() => props.imageId, load, { immediate: true })
onBeforeUnmount(release)
</script>

<template>
  <el-image
    v-loading="loading"
    :src="source"
    :alt="alt"
    :fit="fit"
    :preview-src-list="preview && source ? [source] : []"
    preview-teleported
    hide-on-click-modal
  >
    <template #error><div class="image-error">图片加载失败</div></template>
  </el-image>
</template>

<style scoped>
.image-error{width:100%;height:100%;display:grid;place-items:center;color:var(--muted);font-size:11px;background:#f3f6f5}
</style>
