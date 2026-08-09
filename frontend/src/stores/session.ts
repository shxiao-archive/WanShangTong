import { reactive } from 'vue'
import api from '@/services/api'
import type { User } from '@/types'

export const session = reactive<{
  user: User | null
  selectedMerchantId: number | null
  hydrated: boolean
}>({
  user: null,
  selectedMerchantId: null,
  hydrated: false,
})

export function setSession(user: User) {
  localStorage.removeItem('wst_token')
  localStorage.removeItem('wst_user')
  session.user = user
  session.selectedMerchantId = user.merchant_id
  session.hydrated = true
}

export function updateSessionUser(user: User) {
  localStorage.removeItem('wst_user')
  session.user = user
  session.selectedMerchantId = user.merchant_id
  session.hydrated = true
}

export function clearSession() {
  localStorage.removeItem('wst_token')
  localStorage.removeItem('wst_user')
  session.user = null
  session.selectedMerchantId = null
  session.hydrated = true
}

export async function logoutSession() {
  try {
    await api.post('/auth/logout', null, { silentAuth: true })
  } finally {
    clearSession()
  }
}

export async function hydrateSession() {
  if (session.hydrated) return session.user
  try {
    const user = await api.get('/auth/me', { silentAuth: true })
    localStorage.removeItem('wst_user')
    session.user = user
    if (user.role === 'merchant') session.selectedMerchantId = user.merchant_id
    session.hydrated = true
    return user
  } catch {
    clearSession()
    return null
  }
}
