import { app } from 'electron'
import { copyFileSync, cpSync, existsSync, mkdirSync } from 'node:fs'
import path from 'node:path'

export interface DesktopPaths {
  releaseRoot: string
  backendBin: string
  staticDir: string
  editableEnvFile: string
  envTemplate: string
  defaultPdfDir: string
}

export function getDesktopPaths(): DesktopPaths {
  const resourcesPath =
    (process as NodeJS.Process & { resourcesPath?: string }).resourcesPath ??
    process.cwd()
  const releaseRoot = getReleaseRoot()
  const backendName = process.platform === 'win32' ? 'react-agent-backend.exe' : 'react-agent-backend'
  return {
    releaseRoot,
    backendBin:
      process.env.REACT_AGENT_BACKEND_BIN ??
      path.join(resourcesPath, 'backend', 'bin', backendName),
    staticDir:
      process.env.REACT_AGENT_STATIC_DIR ?? path.join(resourcesPath, 'backend', 'gui'),
    editableEnvFile:
      process.env.REACT_AGENT_ENV_FILE ?? path.join(releaseRoot, 'config', '.env'),
    envTemplate:
      process.env.REACT_AGENT_ENV_TEMPLATE ??
      path.join(resourcesPath, 'env-template', 'env.template'),
    defaultPdfDir:
      process.env.REACT_AGENT_DEFAULT_PDF_DIR ??
      path.join(resourcesPath, 'default-data', 'pdfs'),
  }
}

export function ensureEditableRuntime(paths: DesktopPaths): DesktopPaths {
  const envFile = ensureEnvFile(paths.editableEnvFile, paths.envTemplate)
  const outputPdfDir = path.join(path.dirname(path.dirname(envFile)), 'output', 'pdfs')
  if (!existsSync(outputPdfDir) && existsSync(paths.defaultPdfDir)) {
    mkdirSync(path.dirname(outputPdfDir), { recursive: true })
    cpSync(paths.defaultPdfDir, outputPdfDir, { recursive: true })
  }
  return { ...paths, editableEnvFile: envFile }
}

function ensureEnvFile(target: string, template: string): string {
  try {
    if (!existsSync(target)) {
      mkdirSync(path.dirname(target), { recursive: true })
      copyFileSync(template, target)
    }
    return target
  } catch {
    const fallback = path.join(app.getPath('userData'), 'config', '.env')
    if (!existsSync(fallback)) {
      mkdirSync(path.dirname(fallback), { recursive: true })
      copyFileSync(template, fallback)
    }
    return fallback
  }
}

function getReleaseRoot(): string {
  if (process.env.REACT_AGENT_RELEASE_ROOT) {
    return process.env.REACT_AGENT_RELEASE_ROOT
  }
  if (!app.isPackaged) {
    return path.resolve(__dirname, '..', '..', '..')
  }
  if (process.platform === 'darwin') {
    return path.resolve(path.dirname(process.execPath), '..', '..', '..')
  }
  return path.dirname(process.execPath)
}
