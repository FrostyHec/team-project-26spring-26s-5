import { app, BrowserWindow, dialog, Menu } from 'electron'
import path from 'node:path'

import { startBackend, stopBackend, waitForHealth, type BackendHandle } from './backend'
import { readRuntimeEnv } from './env'
import { ensureEditableRuntime, getDesktopPaths } from './paths'

let backend: BackendHandle | null = null

if (process.platform === 'linux' && app.isPackaged) {
  app.commandLine.appendSwitch('no-sandbox')
}

async function createWindow(): Promise<void> {
  const paths = ensureEditableRuntime(getDesktopPaths())
  const runtimeEnv = readRuntimeEnv(paths.editableEnvFile)
  const logRoot = path.resolve(
    path.dirname(paths.editableEnvFile),
    runtimeEnv.dataPath,
    'logs',
  )
  backend = startBackend({
    backendBin: paths.backendBin,
    envFile: paths.editableEnvFile,
    staticDir: paths.staticDir,
    host: runtimeEnv.appHost,
    port: runtimeEnv.appPort,
    logRoot,
  })

  try {
    await waitForHealth(backend.url)
  } catch (error) {
    stopBackend(backend)
    backend = null
    const message = error instanceof Error ? error.message : String(error)
    await dialog.showMessageBox({
      type: 'error',
      title: 'SUSTech Campus Assistant failed to start',
      message,
      detail: `Check ${paths.editableEnvFile}. If the port is occupied, edit APP_PORT and restart.`,
    })
    app.quit()
    return
  }

  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  await window.loadURL(backend.url)
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null)
  void createWindow()
})

app.on('before-quit', () => {
  stopBackend(backend)
})

app.on('window-all-closed', () => {
  stopBackend(backend)
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
