/**
 * E2E tests for the Settings Panel.
 *
 * Tests verify the complete user flow: opening the settings panel via
 * the Settings button in the sidebar, navigating between sections,
 * and closing the panel.
 *
 * The default locale is English so all text assertions use English strings.
 *
 * Note: Form save operations require a running backend; these tests
 * mock fetch when needed or skip backend-dependent assertions.
 */

import { test, expect, type Page } from '@playwright/test'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Return the Settings button located via its stable data-testid attribute. */
function settingsBtn(page: Page) {
  return page.getByTestId('settings-btn')
}

/** Open the settings panel and wait for it to appear. */
async function openSettings(page: Page) {
  await settingsBtn(page).click()
  await expect(page.locator('text=Settings').first()).toBeVisible({ timeout: 3_000 })
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

test.describe('Settings Panel', () => {
  test.beforeEach(async ({ page }) => {
    // Intercept the GET /settings API call to avoid needing a real backend
    await page.route('**/api/settings', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            cas_account: '',
            cas_password_is_set: false,
            email_account: '',
            email_password_is_set: false,
          }),
        })
      } else if (route.request().method() === 'PUT') {
        const body = route.request().postDataJSON()
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            cas_account: body.cas_account ?? '',
            cas_password_is_set: body.cas_password != null && body.cas_password !== '',
            email_account: body.email_account ?? '',
            email_password_is_set: body.email_password != null && body.email_password !== '',
          }),
        })
      } else if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            cas_account: '',
            cas_password_is_set: false,
            email_account: '',
            email_password_is_set: false,
          }),
        })
      }
    })

    // Stub lightweight API routes to avoid connection errors
    await page.route('**/api/health', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ status: 'ok' }) })
    })
    await page.route('**/api/sessions', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify([]) })
    })
    await page.route('**/api/skills', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify([]) })
    })

    await page.goto('/')
  })

  test('settings button is visible in the sidebar', async ({ page }) => {
    await expect(settingsBtn(page)).toBeVisible()
  })

  test('clicking settings button opens the settings panel', async ({ page }) => {
    await openSettings(page)
    // Panel heading should be present
    await expect(page.locator('text=Settings').first()).toBeVisible()
  })

  test('settings panel shows navigation sections', async ({ page }) => {
    await openSettings(page)

    await expect(page.locator('text=Campus System Service')).toBeVisible()
    await expect(page.locator('text=Email Service')).toBeVisible()
    await expect(page.locator('text=Extension Service')).toBeVisible()
    await expect(page.locator('text=Language')).toBeVisible()
  })

  test('CAS service section shows account and password fields', async ({ page }) => {
    await openSettings(page)

    // Default section is CAS service
    await expect(page.locator('#cas-account')).toBeVisible()
    await expect(page.locator('#cas-password')).toBeVisible()
  })

  test('can switch to email service section', async ({ page }) => {
    await openSettings(page)

    await page.locator('nav button', { hasText: 'Email Service' }).click()

    await expect(page.locator('#email-account')).toBeVisible()
    await expect(page.locator('#email-password')).toBeVisible()
  })

  test('extension service section shows coming soon message', async ({ page }) => {
    await openSettings(page)

    await page.locator('nav button', { hasText: 'Extension Service' }).click()

    await expect(page.locator('text=Coming Soon')).toBeVisible()
  })

  test('closing settings panel returns to chat view', async ({ page }) => {
    await openSettings(page)

    await page.locator('[title="Close Settings"]').click()

    await expect(page.locator('[title="Close Settings"]')).not.toBeVisible({ timeout: 2_000 })
  })

  test('can fill and save CAS account', async ({ page }) => {
    await openSettings(page)

    await page.locator('#cas-account').fill('12345678')
    await page.locator('#cas-password').fill('mypassword')

    await page.locator('button', { hasText: 'Save' }).first().click()

    await expect(page.locator('text=Settings saved')).toBeVisible({ timeout: 3_000 })
  })

  test('can switch to language settings section', async ({ page }) => {
    await openSettings(page)

    await page.locator('nav button', { hasText: 'Language' }).click()

    await expect(page.locator('text=English')).toBeVisible()
  })
})
