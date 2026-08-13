import type { RouteLocationRaw } from 'vue-router'
import api from '@/services/api'
import type { InboxAction } from '@/types'

export async function inboxTargetIsAvailable(
  action: InboxAction,
  targetId: number | null,
): Promise<boolean> {
  if (action === 'open_onboarding_review' && targetId) {
    await api.get(`/merchant-onboarding/${targetId}`, { silentError: true })
    return true
  }
  if (action === 'open_service_application' && targetId) {
    await api.get(`/service-applications/${targetId}`, { silentError: true })
    return true
  }
  return true
}

export function inboxLocation(
  action: InboxAction,
  targetId: number | null,
): RouteLocationRaw {
  if (action === 'open_onboarding_review' && targetId) {
    return { path: '/merchants', query: { onboarding_id: String(targetId) } }
  }
  if (action === 'open_onboarding_form') return '/onboarding'
  if (action === 'open_service_application' && targetId) {
    return { path: '/applications', query: { id: String(targetId) } }
  }
  return '/overview'
}
