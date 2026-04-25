import type { LlmSettingsResponse } from '@/api/settings'

function nextGeneratedProviderId(seed: number, usedProviderIds: Set<string>): string {
  let candidateNumber = Math.max(1, seed)
  let candidateId = `provider_${candidateNumber}`

  while (usedProviderIds.has(candidateId)) {
    candidateNumber += 1
    candidateId = `provider_${candidateNumber}`
  }

  return candidateId
}

export function normalizeProviderIds(
  providers: LlmSettingsResponse['providers'],
): LlmSettingsResponse['providers'] {
  const usedProviderIds = new Set<string>()

  return providers.map((provider, index) => {
    const trimmedProviderId = provider.id.trim()
    const normalizedProviderId =
      trimmedProviderId && !usedProviderIds.has(trimmedProviderId)
        ? trimmedProviderId
        : nextGeneratedProviderId(index + 1, usedProviderIds)

    usedProviderIds.add(normalizedProviderId)

    return {
      ...provider,
      id: normalizedProviderId,
    }
  })
}

export type LlmSettingsValidationIssue =
  | {
      code: 'provider-id-required'
      index: number
    }
  | {
      code: 'provider-id-duplicate'
      index: number
      providerId: string
    }
  | {
      code: 'provider-api-key-required'
      index: number
      providerId: string
      providerName: string
    }
  | {
      code: 'provider-name-required'
      index: number
    }
  | {
      code: 'provider-base-url-required'
      index: number
      providerName: string
    }
  | {
      code: 'provider-model-required'
      index: number
      providerName: string
    }
  | {
      code: 'provider-priority-invalid'
      index: number
      providerName: string
    }
  | {
      code: 'provider-enabled-required'
      index: number
      providerName: string
    }

export function validateLlmSettings(settings: LlmSettingsResponse): LlmSettingsValidationIssue[] {
  const issues: LlmSettingsValidationIssue[] = []
  const seenProviderIds = new Set<string>()

  settings.providers.forEach((provider, index) => {
    const providerId = provider.id.trim()
    const providerName = provider.name.trim()

    if (!providerId) {
      issues.push({
        code: 'provider-id-required',
        index,
      })
    } else if (seenProviderIds.has(providerId)) {
      issues.push({
        code: 'provider-id-duplicate',
        index,
        providerId,
      })
    } else {
      seenProviderIds.add(providerId)
    }

    if (!providerName) {
      issues.push({
        code: 'provider-name-required',
        index,
      })
    }

    if (!provider.base_url.trim()) {
      issues.push({
        code: 'provider-base-url-required',
        index,
        providerName,
      })
    }

    if (!provider.model.trim()) {
      issues.push({
        code: 'provider-model-required',
        index,
        providerName,
      })
    }

    if (!Number.isInteger(provider.priority) || provider.priority < 0) {
      issues.push({
        code: 'provider-priority-invalid',
        index,
        providerName,
      })
    }

    if (typeof provider.enabled !== 'boolean') {
      issues.push({
        code: 'provider-enabled-required',
        index,
        providerName,
      })
    }

    if (provider.enabled && !provider.api_key.trim()) {
      issues.push({
        code: 'provider-api-key-required',
        index,
        providerId,
        providerName,
      })
    }
  })

  return issues
}
