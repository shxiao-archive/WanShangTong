<script setup lang="ts">
const icpNumber = import.meta.env.VITE_ICP_NUMBER?.trim() || ''
const publicSecurityNumber = import.meta.env.VITE_PUBLIC_SECURITY_NUMBER?.trim() || ''
const publicSecurityCode = import.meta.env.VITE_PUBLIC_SECURITY_CODE?.trim() || ''
const publicSecurityUrl = publicSecurityCode
  ? `https://beian.mps.gov.cn/#/query/webSearch?code=${encodeURIComponent(publicSecurityCode)}`
  : 'https://beian.mps.gov.cn/'
</script>

<template>
  <div class="app-root">
    <router-view />
    <footer v-if="icpNumber || publicSecurityNumber" class="site-footer">
      <a v-if="icpNumber" href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
        {{ icpNumber }}
      </a>
      <span v-if="icpNumber && publicSecurityNumber" aria-hidden="true">|</span>
      <a
        v-if="publicSecurityNumber"
        :href="publicSecurityUrl"
        target="_blank"
        rel="noopener noreferrer"
      >
        {{ publicSecurityNumber }}
      </a>
    </footer>
  </div>
</template>

<style scoped>
.app-root { min-height: 100vh; }
.site-footer {
  padding: 16px 20px 20px;
  color: #788786;
  background: #f3f6f5;
  text-align: center;
  font-size: 12px;
  line-height: 1.5;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 10px;
}
.site-footer a { color: inherit; text-decoration: none; }
.site-footer a:hover { color: var(--brand); }
@media (max-width: 900px) {
  .site-footer { padding-bottom: calc(88px + env(safe-area-inset-bottom)); }
}
</style>
