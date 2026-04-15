import { describe, it, expect } from 'vitest'
import { createI18n } from 'vue-i18n'
import en from '../locales/en.json'
import zh from '../locales/zh.json'

describe('i18n email placeholders', () => {
  it('renders English email placeholders without linked-format errors', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'en',
      messages: { en },
    })

    expect(i18n.global.t('email.toPlaceholder')).toContain('recipient')
    expect(i18n.global.t('email.ccPlaceholder')).toContain('CC')
  })

  it('renders Chinese email placeholders without linked-format errors', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh',
      messages: { zh },
    })

    expect(i18n.global.t('email.toPlaceholder').length).toBeGreaterThan(0)
    expect(i18n.global.t('email.ccPlaceholder').length).toBeGreaterThan(0)
  })
})
