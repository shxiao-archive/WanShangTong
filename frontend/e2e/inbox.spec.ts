import { expect, test, type Page, type Route } from '@playwright/test'

const operator = {
  id: 1,
  username: 'operator',
  display_name: '测试运营员',
  role: 'operator',
  merchant_id: null,
  must_change_password: false,
  is_active: true,
}

const merchantUser = {
  id: 2,
  username: 'merchant',
  display_name: '测试商户',
  role: 'merchant',
  merchant_id: 1,
  must_change_password: false,
  is_active: true,
}

function envelope(data: unknown, message = 'ok') {
  return JSON.stringify({ code: 0, message, data })
}

function application(id: number) {
  return {
    id,
    merchant_id: 1,
    merchant_name: '三峡巷子老火锅',
    resource_id: id,
    created_by: 2,
    contact_name: '测试联系人',
    contact_phone: '13800000000',
    merchant_note: '',
    recommendation_score: 92,
    recommendation_reason: '测试推荐理由',
    resource_snapshot: {
      name: `测试套餐 ${id}`,
      price: 100,
      unit: '月',
      description: '用于通知中心深链验证',
      included_services: ['服务一'],
    },
    status: id === 43 ? 'completed' : 'pending',
    is_demo: false,
    created_at: '2026-08-12T12:00:00+08:00',
    updated_at: '2026-08-12T12:00:00+08:00',
    completed_at: null,
    events: [],
  }
}

async function mockInboxApi(page: Page, account = operator) {
  let workItemRequestCount = 0
  const notificationPeriods: string[] = []
  const notifications = [
    {
      id: 103,
      type: 'service_operator_note_added',
      category: 'service',
      title: '服务申请有新的跟进备注',
      message: '测试套餐 42 新增了运营跟进信息',
      action: 'open_service_application',
      target_type: 'service_application',
      target_id: 42,
      is_demo: false,
      read_at: null as string | null,
      created_at: '2026-08-12T12:11:00+08:00',
    },
    {
      id: 102,
      type: 'service_application_status_changed',
      category: 'service',
      title: '服务申请状态已更新',
      message: '测试套餐 42 当前状态：待处理',
      action: 'open_service_application',
      target_type: 'service_application',
      target_id: 42,
      is_demo: false,
      read_at: null as string | null,
      created_at: '2026-08-12T12:10:00+08:00',
    },
    {
      id: 100,
      type: 'service_application_status_changed',
      category: 'service',
      title: '已结束的服务申请',
      message: '该事项已经办理完成',
      action: 'open_service_application',
      target_type: 'service_application',
      target_id: 43,
      is_demo: false,
      read_at: '2026-08-12T12:20:00+08:00',
      created_at: '2026-08-12T11:50:00+08:00',
    },
    {
      id: 101,
      type: 'onboarding_submitted',
      category: 'onboarding',
      title: '新的商户入驻申请',
      message: '测试门店已提交入驻资料，请及时审核',
      action: 'open_onboarding_review',
      target_type: 'merchant_onboarding_application',
      target_id: 7,
      is_demo: false,
      read_at: null as string | null,
      created_at: '2026-08-12T12:00:00+08:00',
    },
    {
      id: 99,
      type: 'service_application_status_changed',
      category: 'service',
      title: '20天前的通知',
      message: '用于验证近30天筛选',
      action: 'open_service_application',
      target_type: 'service_application',
      target_id: 44,
      is_demo: false,
      read_at: '2026-07-24T12:10:00+08:00',
      created_at: '2026-07-24T12:00:00+08:00',
    },
    {
      id: 98,
      type: 'service_application_status_changed',
      category: 'service',
      title: '45天前的通知',
      message: '用于验证全部时间筛选',
      action: 'open_service_application',
      target_type: 'service_application',
      target_id: 45,
      is_demo: false,
      read_at: '2026-06-29T12:10:00+08:00',
      created_at: '2026-06-29T12:00:00+08:00',
    },
  ]
  const workItems = [
    {
      key: 'onboarding:7',
      category: 'onboarding',
      title: '测试门店',
      summary: '测试申请人提交的入驻申请',
      status: 'pending',
      status_label: '待审核',
      is_demo: false,
      created_at: '2026-08-12T12:00:00+08:00',
      updated_at: '2026-08-12T12:00:00+08:00',
      action: 'open_onboarding_review',
      target_id: 7,
    },
    {
      key: 'service:41',
      category: 'service',
      title: '演示网络套餐',
      summary: '演示商户提交的服务申请',
      status: 'processing',
      status_label: '办理中',
      is_demo: true,
      created_at: '2026-08-12T11:00:00+08:00',
      updated_at: '2026-08-12T12:05:00+08:00',
      action: 'open_service_application',
      target_id: 41,
    },
  ]

  await page.route('**/api/v1/**', async (route: Route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')
    const method = request.method()
    let data: unknown = null

    if (path === '/auth/me') data = account
    else if (path === '/merchants') data = { items: [{ id: 1, name: '三峡巷子老火锅' }], total: 1 }
    else if (path === '/inbox/summary') {
      data = {
        unread_count: notifications.filter(item => !item.read_at).length,
        latest_notification_id: 103,
        todo_count: 2,
        onboarding_pending_count: 1,
        service_pending_count: 0,
        service_processing_count: 1,
        onboarding_needs_changes_count: 0,
      }
    } else if (path === '/inbox/work-items') {
      workItemRequestCount += 1
      const category = url.searchParams.get('category') || 'all'
      const items = workItems.filter(item => category === 'all' || item.category === category)
      data = { items, total: items.length, page: 1, page_size: 20 }
    } else if (path === '/inbox/notifications' && method === 'GET') {
      const state = url.searchParams.get('state') || 'all'
      const category = url.searchParams.get('category') || 'all'
      const period = url.searchParams.get('period') || '7d'
      notificationPeriods.push(period)
      const cutoff = period === '7d'
        ? Date.parse('2026-08-06T00:00:00+08:00')
        : period === '30d' ? Date.parse('2026-07-14T00:00:00+08:00') : 0
      const items = notifications.filter(item => (
        (state === 'all' || !item.read_at)
        && (category === 'all' || item.category === category)
        && Date.parse(item.created_at) >= cutoff
      ))
      data = { items, total: items.length, page: 1, page_size: 20 }
    } else if (/^\/inbox\/notifications\/\d+\/read$/.test(path) && method === 'PATCH') {
      const id = Number(path.split('/')[3])
      const item = notifications.find(value => value.id === id)
      if (!item) return route.fulfill({ status: 404, contentType: 'application/json', body: envelope(null, '通知不存在') })
      const readAt = '2026-08-12T12:20:00+08:00'
      notifications
        .filter(value => value.target_type === item.target_type && value.target_id === item.target_id)
        .forEach(value => { value.read_at ||= readAt })
      data = item
    } else if (path === '/inbox/notifications/read-all' && method === 'POST') {
      notifications.forEach(item => { item.read_at ||= '2026-08-12T12:20:00+08:00' })
      data = { updated_count: 2 }
    } else if (path === '/service-applications') data = { items: [], total: 0, page: 1, page_size: 20 }
    else if (/^\/service-applications\/\d+$/.test(path)) data = application(Number(path.split('/').at(-1)))
    else if (path === '/dashboard/overview') {
      data = {
        merchant_count: 1,
        active_count: 1,
        industry_distribution: { 餐饮: 1 },
        active_application_count: 1,
        pending_application_count: 0,
        popular_needs: [],
      }
    } else {
      return route.fulfill({ status: 404, contentType: 'application/json', body: envelope(null, `未模拟 ${path}`) })
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: envelope(data) })
  })
  return {
    workItemRequestCount: () => workItemRequestCount,
    notificationPeriods: () => notificationPeriods,
  }
}

test.beforeEach(async ({ page }) => {
  await mockInboxApi(page)
})

test('notification center shows shared work and supports read all', async ({ page }) => {
  await page.goto('/overview')
  const bell = page.getByRole('button', { name: '打开通知与待办中心' })
  const icon = bell.locator(':scope > .el-icon')
  const badge = bell.locator(':scope > .inbox-count')
  await expect(bell).toBeVisible()
  await expect(icon).toHaveCSS('position', 'static')
  await expect(icon).toHaveCSS('color', 'rgb(11, 118, 111)')
  await expect(badge).toHaveCSS('background-color', 'rgb(231, 124, 69)')
  await expect(badge).toHaveText('3')
  await bell.click()

  const drawer = page.locator('.inbox-drawer')
  await expect(drawer).toBeVisible()
  await expect(drawer.getByText('测试门店', { exact: true })).toBeVisible()
  await expect(drawer.getByText('演示数据', { exact: true })).toBeVisible()
  await drawer.getByRole('tab', { name: /通知/ }).click()
  await expect(drawer.locator('.notification-row.unread')).toHaveCount(3)
  await drawer.getByRole('button', { name: '全部已读' }).click()
  await expect(drawer.locator('.notification-row.unread')).toHaveCount(0)
  await expect(badge).toHaveCount(0)
})

test('operator notification center defaults to seven days and supports time ranges', async ({ page }) => {
  await page.unroute('**/api/v1/**')
  const requests = await mockInboxApi(page)
  await page.goto('/overview')
  await page.getByRole('button', { name: '打开通知与待办中心' }).click()
  const drawer = page.locator('.inbox-drawer')
  await drawer.getByRole('tab', { name: /通知/ }).click()

  const periodControl = drawer.locator('.notification-period')
  await expect(periodControl).toContainText('近7天')
  await expect(drawer.locator('.notification-row')).toHaveCount(4)

  await periodControl.click()
  await page.getByRole('option', { name: '近30天' }).click()
  await expect(drawer.locator('.notification-row')).toHaveCount(5)

  await periodControl.click()
  await page.getByRole('option', { name: '全部', exact: true }).click()
  await expect(drawer.locator('.notification-row')).toHaveCount(6)
  expect(requests.notificationPeriods()).toEqual(expect.arrayContaining(['7d', '30d', 'all']))
})

test('merchant client has notifications only and never requests work items', async ({ page }) => {
  await page.unroute('**/api/v1/**')
  const requests = await mockInboxApi(page, merchantUser)
  await page.goto('/overview')
  await page.getByRole('button', { name: '打开通知中心' }).click()

  const drawer = page.locator('.inbox-drawer')
  await expect(drawer).toBeVisible()
  await expect(drawer.getByRole('heading', { name: '通知中心' })).toBeVisible()
  await expect(drawer.getByRole('tab', { name: /待办/ })).toHaveCount(0)
  await expect(drawer.locator('.notification-row')).toHaveCount(6)
  await expect(drawer.getByLabel('通知时间范围')).toHaveCount(0)
  expect(requests.workItemRequestCount()).toBe(0)

  await drawer.getByText('已结束的服务申请', { exact: true }).click()
  await expect(page).toHaveURL(/\/applications\?id=43/)
  await expect(page.locator('.detail-head h2')).toHaveText('测试套餐 43')
  await expect(page.locator('.detail-head .status.completed')).toHaveText('已完成')
})

test('notification deep link switches details on the same route', async ({ page }) => {
  await page.goto('/applications?id=41')
  await expect(page.locator('.detail-head h2')).toHaveText('测试套餐 41')
  await page.locator('.el-drawer__close-btn').click()
  await page.getByRole('button', { name: '打开通知与待办中心' }).click()
  const drawer = page.locator('.inbox-drawer')
  await drawer.getByRole('tab', { name: /通知/ }).click()
  await drawer.getByText('服务申请状态已更新', { exact: true }).click()
  await expect(page).toHaveURL(/\/applications\?id=42/)
  await expect(page.locator('.detail-head h2')).toHaveText('测试套餐 42')

  await page.locator('.el-drawer__close-btn').click()
  await page.getByRole('button', { name: '打开通知与待办中心' }).click()
  const refreshedInbox = page.locator('.inbox-drawer')
  await refreshedInbox.getByRole('tab', { name: /通知/ }).click()
  await expect(refreshedInbox.getByText('服务申请状态已更新', { exact: true }).locator('xpath=ancestor::button').locator('.unread-dot')).toHaveCount(0)
  await expect(refreshedInbox.getByText('服务申请有新的跟进备注', { exact: true }).locator('xpath=ancestor::button').locator('.unread-dot')).toHaveCount(0)
})

test('work item opens its processing drawer', async ({ page }) => {
  await page.goto('/overview')
  await page.getByRole('button', { name: '打开通知与待办中心' }).click()
  const drawer = page.locator('.inbox-drawer')
  await drawer.getByText('演示网络套餐', { exact: true }).click()
  await expect(page).toHaveURL(/\/applications\?id=41/)
  await expect(page.locator('.detail-head h2')).toHaveText('测试套餐 41')
})

test('completed notification opens and can reopen its processing drawer', async ({ page }) => {
  await page.goto('/overview')
  await page.getByRole('button', { name: '打开通知与待办中心' }).click()
  const drawer = page.locator('.inbox-drawer')
  await drawer.getByRole('tab', { name: /通知/ }).click()
  await drawer.getByText('已结束的服务申请', { exact: true }).click()
  await expect(page).toHaveURL(/\/applications\?id=43/)
  await expect(page.locator('.detail-head h2')).toHaveText('测试套餐 43')
  await expect(page.locator('.detail-head .status.completed')).toHaveText('已完成')

  await page.locator('.el-drawer__close-btn').click()
  await expect(page).toHaveURL(/\/applications$/)
  await page.getByRole('button', { name: '打开通知与待办中心' }).click()
  const reopenedInbox = page.locator('.inbox-drawer')
  await reopenedInbox.getByRole('tab', { name: /通知/ }).click()
  await reopenedInbox.getByText('已结束的服务申请', { exact: true }).click()
  await expect(page.locator('.detail-head h2')).toHaveText('测试套餐 43')
})

test('mobile notification center fills the viewport without adding bottom navigation', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile-only layout check')
  await page.goto('/overview')
  await page.getByRole('button', { name: '打开通知与待办中心' }).click()
  const drawer = page.locator('.inbox-drawer')
  await expect(drawer).toBeVisible()
  const box = await drawer.boundingBox()
  expect(box?.width).toBeGreaterThanOrEqual(385)
  expect(box?.height).toBeGreaterThanOrEqual(650)
  await expect(page.locator('.mobile-nav a')).toHaveCount(7)
  await expect(page.locator('.mobile-nav').getByText('通知与待办')).toHaveCount(0)
})
