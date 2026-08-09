import { createRouter, createWebHistory } from 'vue-router'
import { hydrateSession, session } from '@/stores/session'
import LoginView from '@/views/LoginView.vue'
import ChangePasswordView from '@/views/ChangePasswordView.vue'
import OnboardingView from '@/views/OnboardingView.vue'
import AppLayout from '@/components/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/change-password', component: ChangePasswordView, meta: { passwordChange: true } },
    { path: '/onboarding', component: OnboardingView, meta: { onboarding: true } },
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', redirect: '/overview' },
        { path: 'overview', component: () => import('@/views/OverviewView.vue') },
        { path: 'merchants', component: () => import('@/views/MerchantsView.vue'), meta: { operator: true } },
        { path: 'store', component: () => import('@/views/StoreView.vue') },
        { path: 'analytics', component: () => import('@/views/AnalyticsView.vue') },
        { path: 'portrait', component: () => import('@/views/ProfileView.vue') },
        { path: 'recommendations', component: () => import('@/views/RecommendationsView.vue'), meta: { merchant: true } },
        { path: 'applications', component: () => import('@/views/ApplicationsView.vue') },
        { path: 'resources', component: () => import('@/views/ResourcesView.vue'), meta: { operator: true } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  await hydrateSession()
  if (!to.meta.public && !session.user) return '/login'
  if (session.user?.must_change_password && !to.meta.passwordChange) return '/change-password'
  const awaitingOnboarding = session.user?.role === 'merchant' && !session.user.merchant_id
  if (awaitingOnboarding && !to.meta.onboarding && !to.meta.passwordChange) return '/onboarding'
  if (to.meta.onboarding && !awaitingOnboarding) return '/overview'
  if (to.path === '/login' && session.user) {
    if (session.user.must_change_password) return '/change-password'
    return awaitingOnboarding ? '/onboarding' : '/overview'
  }
  if (to.meta.operator && session.user?.role !== 'operator') return '/overview'
  if (to.meta.merchant && session.user?.role !== 'merchant') return '/resources'
})

export default router
