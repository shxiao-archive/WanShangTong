import { expect, test } from '@playwright/test'

async function login(page: import('@playwright/test').Page, role: 'merchant' | 'operator') {
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(role)
  const password = role === 'merchant'
    ? process.env.DEMO_MERCHANT_PASSWORD
    : process.env.DEMO_OPERATOR_PASSWORD
  if (!password) throw new Error(`Missing test password for ${role}`)
  await page.locator('input[type="password"]').fill(password)
  await page.getByRole('button', { name: '进入平台' }).click()
  await expect(page).toHaveURL(/\/overview/)
}

function validUscc(seed: string) {
  const charset = '0123456789ABCDEFGHJKLMNPQRTUWXY'
  const weights = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]
  const numericSeed = [...seed].reduce((total, char) => total + char.charCodeAt(0), 0) % 100000
  const base = `91500101MA5U${String(numericSeed).padStart(5, '0')}`
  const total = [...base].reduce((sum, char, index) => sum + charset.indexOf(char) * weights[index], 0)
  return `${base}${charset[(31 - total % 31) % 31]}`
}

test('merchant registration enters a persistent five-step onboarding draft', async ({ page }, testInfo) => {
  const suffix = `${testInfo.project.name}_${Date.now()}`
  await page.goto('/login')
  await page.getByText('创建账号', { exact: true }).click()
  await page.getByLabel('登录账号').fill(`trial_${suffix}`)
  await page.getByLabel('联系人姓名').fill('入驻测试人')
  await page.getByLabel('设置密码').fill('Trial2026Pass')
  await page.getByLabel('确认密码').fill('Trial2026Pass')
  await page.getByRole('checkbox').nth(0).check()
  await page.getByRole('checkbox').nth(1).check()
  await page.getByRole('button', { name: '创建账号，下一步' }).click()
  await expect(page).toHaveURL(/\/onboarding/)
  await expect(page.getByRole('heading', { name: '主体资质' })).toBeVisible()

  await page.getByText('个体工商户', { exact: true }).click()
  await page.getByLabel('营业执照名称 *').fill('万州区入驻自动化测试经营部')
  await page.getByLabel('统一社会信用代码 *').fill(validUscc(suffix))
  await page.getByLabel('法定代表人 / 经营者 *').fill('入驻测试人')
  await page.getByLabel('营业执照注册地址 *').fill('重庆市万州区测试路1号')
  await page.getByLabel('营业执照经营范围 *').fill('依法开展经营活动')
  await page.locator('input[type=file]').first().setInputFiles({
    name: 'license.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'),
  })
  await expect(page.getByText('营业执照上传成功')).toBeVisible()
  await page.getByRole('button', { name: '保存并继续' }).click()
  await expect(page.getByRole('heading', { name: '店铺资料' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: '店铺资料' })).toBeVisible()
})

test('merchant can navigate the core business loop', async ({ page }, testInfo) => {
  await login(page, 'merchant')
  await expect(page.getByText('最新营业额', { exact: true })).toBeVisible()
  await page.goto('/store')
  await expect(page.getByRole('heading', { name: '示例餐饮店 A' })).toBeVisible()
  await page.getByRole('button', { name: '管理商品与图片' }).click()
  await expect(page.getByRole('dialog', { name: '管理商品与图片' })).toBeVisible()
  await expect(page.getByRole('button', { name: '添加商品' })).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()
  await page.goto('/analytics')
  await expect(page.getByText('营收与客流趋势')).toBeVisible()
  await page.goto('/portrait')
  await expect(page.getByRole('heading', { name: '判断依据' })).toBeVisible()
  await page.goto('/recommendations')
  await expect(page.getByText('最佳匹配')).toBeVisible()
  await expect(page.getByRole('button', { name: /申请服务|查看申请进度/ }).first()).toBeVisible()
  if (testInfo.project.name === 'desktop') {
    await page.screenshot({ path: '/tmp/wst-recommendations.png', fullPage: true })
  }
})

test('operator can access merchant and resource management', async ({ page }, testInfo) => {
  await login(page, 'operator')
  await page.goto('/merchants')
  const merchantName = testInfo.project.name === 'mobile'
    ? page.locator('.mobile-merchant-list').getByText('示例餐饮店 A').first()
    : page.locator('.el-table').getByText('示例餐饮店 A').first()
  await expect(merchantName).toBeVisible()
  await expect(page.getByText('共 6 家商户')).toBeVisible()
  await page.goto('/store')
  await expect(page.getByRole('button', { name: '编辑资料' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '管理商品与图片' })).toHaveCount(0)
  await page.goto('/analytics')
  await expect(page.getByRole('button', { name: '录入数据' })).toHaveCount(0)
  await expect(page.getByText('Excel 导入', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '编辑' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '删除' })).toHaveCount(0)
  await page.goto('/resources')
  await expect(page.getByText('千兆商企宽带')).toBeVisible()
})

for (const role of ['merchant', 'operator'] as const) {
  test(`${role} can open change password from user menu`, async ({ page }) => {
    await login(page, role)
    await page.locator('.user-menu').click()
    await page.getByRole('menuitem', { name: '修改密码' }).click()
    await expect(page).toHaveURL(/\/change-password/)
    await expect(page.getByRole('heading', { name: '修改登录密码' })).toBeVisible()
  })
}

test('mobile shell exposes compact navigation', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile-only visual check')
  await login(page, 'merchant')
  await expect(page.locator('.mobile-nav')).toBeVisible()
  await page.screenshot({ path: '/tmp/wst-mobile.png', fullPage: true })
})

test('mobile merchant pages keep facts centered and portrait tags separated', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile-only layout check')
  await login(page, 'merchant')

  await page.goto('/store')
  const scaleFact = page.locator('.facts > div').first()
  await expect(scaleFact).toBeVisible()
  const centers = await scaleFact.evaluate((element) => {
    const parent = element.getBoundingClientRect()
    const label = element.querySelector('span')!.getBoundingClientRect()
    const value = element.querySelector('b')!.getBoundingClientRect()
    return {
      parent: parent.left + parent.width / 2,
      label: label.left + label.width / 2,
      value: value.left + value.width / 2,
    }
  })
  expect(Math.abs(centers.label - centers.parent)).toBeLessThan(2)
  expect(Math.abs(centers.value - centers.parent)).toBeLessThan(2)
  await page.screenshot({ path: testInfo.outputPath('mobile-store.png'), fullPage: true })

  await page.goto('/portrait')
  const portraitTags = page.locator('.portrait-tags span')
  await expect(portraitTags.first()).toBeVisible()
  const tagsAreSeparated = await portraitTags.evaluateAll((elements) => {
    const boxes = elements.map(element => element.getBoundingClientRect())
    return boxes.every((box, index) => boxes.every((other, otherIndex) => (
      index === otherIndex
      || box.right <= other.left
      || other.right <= box.left
      || box.bottom <= other.top
      || other.bottom <= box.top
    )))
  })
  expect(tagsAreSeparated).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('mobile-portrait.png'), fullPage: true })
})

test('mobile operator can expand one merchant and reach every navigation item', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile-only interaction check')
  await login(page, 'operator')
  await page.goto('/merchants')

  await expect(page.locator('.desktop-merchant-table')).toBeHidden()
  const summaries = page.locator('.mobile-merchant-summary')
  await expect(summaries.first()).toBeVisible()
  await expect(page.locator('.mobile-merchant-panel')).toHaveCount(0)
  await summaries.first().click()
  await expect(page.locator('.mobile-merchant-panel')).toHaveCount(1)
  await summaries.nth(1).click()
  await expect(page.locator('.mobile-merchant-panel')).toHaveCount(1)
  await expect(summaries.first()).toHaveAttribute('aria-expanded', 'false')
  await expect(summaries.nth(1)).toHaveAttribute('aria-expanded', 'true')
  await page.screenshot({ path: testInfo.outputPath('mobile-merchants-expanded.png'), fullPage: true })
  const selectedMerchantName = (await summaries.nth(1).locator('.mobile-merchant-copy b').innerText()).replace('演示', '').trim()
  await page.locator('.mobile-merchant-panel').getByRole('button', { name: '查看档案' }).click()
  await expect(page).toHaveURL(/\/store/)
  await expect(page.getByRole('heading', { name: selectedMerchantName })).toBeVisible()

  const mobileNav = page.locator('.mobile-nav')
  await expect(mobileNav.locator('a')).toHaveCount(7)
  const navWidths = await mobileNav.evaluate(element => ({
    client: element.clientWidth,
    scroll: element.scrollWidth,
  }))
  expect(navWidths.scroll).toBeGreaterThan(navWidths.client)
  const resourcesLink = mobileNav.getByText('资源管理', { exact: true })
  await resourcesLink.scrollIntoViewIfNeeded()
  await resourcesLink.click()
  await expect(page).toHaveURL(/\/resources/)
  await expect(page.getByRole('heading', { name: '资源管理' })).toBeVisible()
})

test('mobile operator overview keeps the title at the intended line break', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile-only layout check')
  await login(page, 'operator')
  await expect(page.getByRole('heading', { name: '运营全景，一目了然' })).toBeVisible()
  expect(await page.locator('.operator-title-break').evaluate(
    element => getComputedStyle(element).display,
  )).toBe('block')
})

for (const role of ['merchant', 'operator'] as const) {
  test(`mobile ${role} can expand business data actions below one row`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile', 'mobile-only interaction check')
    await login(page, role)
    await page.goto('/analytics')

    await expect(page.locator('.desktop-data-table')).toBeHidden()
    const summaries = page.locator('.mobile-data-summary')
    await expect(summaries.first()).toBeVisible()
    await expect(page.locator('.mobile-data-panel')).toHaveCount(0)
    await summaries.first().click()
    await expect(page.locator('.mobile-data-panel')).toHaveCount(1)
    if (role === 'merchant') {
      await expect(page.locator('.mobile-data-panel').getByRole('button', { name: '编辑' })).toBeVisible()
      await expect(page.locator('.mobile-data-panel').getByRole('button', { name: '删除' })).toBeVisible()
    } else {
      await expect(page.locator('.mobile-data-panel').getByRole('button', { name: '编辑' })).toHaveCount(0)
      await expect(page.locator('.mobile-data-panel').getByRole('button', { name: '删除' })).toHaveCount(0)
    }
    await summaries.nth(1).click()
    await expect(page.locator('.mobile-data-panel')).toHaveCount(1)
    await expect(summaries.first()).toHaveAttribute('aria-expanded', 'false')
    await expect(summaries.nth(1)).toHaveAttribute('aria-expanded', 'true')
  })
}
