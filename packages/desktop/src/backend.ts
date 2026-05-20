import { ChildProcess, spawn } from 'node:child_process'
import { createWriteStream, mkdirSync } from 'node:fs'
import path from 'node:path'

export interface BackendOptions {
  backendBin: string
  envFile: string
  staticDir: string
  host: string
  port: number
  logRoot: string
}

export interface BackendHandle {
  process: ChildProcess
  url: string
}

export function buildBackendArgs(options: BackendOptions): string[] {
  return [
    'serve',
    '--env-file',
    options.envFile,
    '--host',
    options.host,
    '--port',
    String(options.port),
    '--static-dir',
    options.staticDir,
  ]
}

export function startBackend(options: BackendOptions): BackendHandle {
  const url = `http://${options.host}:${options.port}`
  mkdirSync(options.logRoot, { recursive: true })
  const log = createWriteStream(path.join(options.logRoot, 'desktop-backend.log'), {
    flags: 'a',
  })
  const child = spawn(
    options.backendBin,
    buildBackendArgs(options),
    {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    },
  )
  child.stdout.pipe(log)
  child.stderr.pipe(log)
  return { process: child, url }
}

export function stopBackend(handle: BackendHandle | null): void {
  if (!handle || handle.process.killed) {
    return
  }
  handle.process.kill()
}

export async function waitForHealth(url: string, timeoutMs = 30000): Promise<void> {
  const deadline = Date.now() + timeoutMs
  const healthUrl = `${url}/api/health`
  while (Date.now() < deadline) {
    try {
      const response = await fetch(healthUrl)
      if (response.ok) {
        return
      }
    } catch {
      // Backend is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error(`Backend did not become healthy: ${healthUrl}`)
}
