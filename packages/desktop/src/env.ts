import { readFileSync } from 'node:fs'

export interface RuntimeEnv {
  appHost: string
  appPort: number
  dataPath: string
}

export function readRuntimeEnv(envFile: string): RuntimeEnv {
  const values = parseEnv(readFileSync(envFile, 'utf8'))
  const rawPort = values.APP_PORT ?? '8000'
  const appPort = Number.parseInt(rawPort, 10)
  if (!Number.isInteger(appPort) || appPort <= 0 || appPort > 65535) {
    throw new Error(`Invalid APP_PORT in ${envFile}: ${rawPort}`)
  }
  return {
    appHost: values.APP_HOST || '127.0.0.1',
    appPort,
    dataPath: values.DATA_PATH || './output',
  }
}

export function parseEnv(content: string): Record<string, string> {
  const values: Record<string, string> = {}
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) {
      continue
    }
    const separator = trimmed.indexOf('=')
    if (separator < 0) {
      continue
    }
    const key = trimmed.slice(0, separator).trim()
    let value = trimmed.slice(separator + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    values[key] = value
  }
  return values
}
