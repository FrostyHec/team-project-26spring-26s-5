import { test, expect } from '@playwright/test'

test('renders chat layout and toggles sidebar collapse', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByRole('button', { name: 'New Chat' })).toBeVisible()
  await expect(page.locator('div[class*="max-w-[920px]"]').first()).toBeVisible()

  const sidebar = page.locator('aside').first()
  const toggleSidebarBtn = page.getByTitle('Toggle Session Sidebar')

  await expect(sidebar).toHaveClass(/w-64/)
  await expect(toggleSidebarBtn).toBeVisible()

  await toggleSidebarBtn.click()
  await expect(sidebar).toHaveClass(/w-16/)
  await expect(page.locator('span').filter({ hasText: /^New Chat$/ })).toHaveCount(0)

  const collapsedNewChat = page.getByRole('button', { name: 'New Chat' })
  await expect(collapsedNewChat).toBeVisible()
  await collapsedNewChat.click()

  await toggleSidebarBtn.click()
  await expect(sidebar).toHaveClass(/w-64/)
  await expect(page.getByRole('button', { name: 'New Chat' })).toBeVisible()
})
