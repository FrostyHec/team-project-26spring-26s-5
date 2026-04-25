import { describe, expect, it } from 'vitest'
import { createDefaultLlmSettings } from '@/api/settings'
import { normalizeProviderIds, validateLlmSettings } from '../llmSettingsValidation'

describe('validateLlmSettings', () => {
  it('flags enabled providers missing an API key', () => {
    const settings = createDefaultLlmSettings()
    settings.providers = [
      {
        id: 'provider_2',
        name: 'Backup',
        priority: 0,
        base_url: '',
        api_key: 'secret',
        model: 'gpt-4.1',
        enabled: true,
      },
      {
        id: 'provider_3',
        name: 'Fallback',
        priority: 1,
        base_url: '',
        api_key: '   ',
        model: 'gpt-4.1-mini',
        enabled: true,
      },
    ]

    expect(validateLlmSettings(settings)).toContainEqual({
      code: 'provider-api-key-required',
      index: 1,
      providerId: 'provider_3',
      providerName: 'Fallback',
    })
  })

  it('flags missing required provider fields before submit', () => {
    const settings = createDefaultLlmSettings()
    settings.providers = [
      {
        id: 'provider_1',
        name: '   ',
        priority: -1,
        base_url: '   ',
        api_key: 'secret',
        model: '   ',
        enabled: true,
      },
    ]

    expect(validateLlmSettings(settings)).toEqual(
      expect.arrayContaining([
        {
          code: 'provider-name-required',
          index: 0,
        },
        {
          code: 'provider-base-url-required',
          index: 0,
          providerName: '',
        },
        {
          code: 'provider-model-required',
          index: 0,
          providerName: '',
        },
        {
          code: 'provider-priority-invalid',
          index: 0,
          providerName: '',
        },
      ]),
    )
  })

  it('flags missing and duplicate provider ids before submit', () => {
    const settings = createDefaultLlmSettings()
    settings.providers = [
      {
        id: 'provider_1',
        name: 'Primary',
        priority: 0,
        base_url: 'https://primary.example/v1',
        api_key: 'secret',
        model: 'gpt-4.1',
        enabled: true,
      },
      {
        id: '',
        name: 'Unnamed',
        priority: 1,
        base_url: 'https://unnamed.example/v1',
        api_key: 'secret',
        model: 'gpt-4.1-mini',
        enabled: false,
      },
      {
        id: 'provider_1',
        name: 'Duplicate',
        priority: 2,
        base_url: 'https://duplicate.example/v1',
        api_key: 'secret',
        model: 'gpt-4.1-nano',
        enabled: true,
      },
    ]

    expect(validateLlmSettings(settings)).toEqual(
      expect.arrayContaining([
        {
          code: 'provider-id-required',
          index: 1,
        },
        {
          code: 'provider-id-duplicate',
          index: 2,
          providerId: 'provider_1',
        },
      ]),
    )
  })

  it('normalizes missing and duplicate provider ids for the settings form', () => {
    const settings = createDefaultLlmSettings()
    settings.providers = [
      {
        id: 'provider_1',
        name: 'Primary',
        priority: 0,
        base_url: '',
        api_key: 'secret',
        model: 'gpt-4.1',
        enabled: true,
      },
      {
        id: '',
        name: 'Unnamed',
        priority: 1,
        base_url: '',
        api_key: 'secret',
        model: 'gpt-4.1-mini',
        enabled: false,
      },
      {
        id: 'provider_1',
        name: 'Duplicate',
        priority: 2,
        base_url: '',
        api_key: 'secret',
        model: 'gpt-4.1-nano',
        enabled: true,
      },
    ]

    expect(normalizeProviderIds(settings.providers).map((provider) => provider.id)).toEqual([
      'provider_1',
      'provider_2',
      'provider_3',
    ])
  })
})
