declare module 'electron' {
  export const app: {
    isPackaged: boolean
    commandLine: {
      appendSwitch(name: string, value?: string): void
    }
    getPath(name: string): string
    quit(): void
    whenReady(): Promise<void>
    on(event: string, listener: () => void): void
  }

  export class BrowserWindow {
    constructor(options: Record<string, unknown>)
    loadURL(url: string): Promise<void>
  }

  export const dialog: {
    showMessageBox(options: Record<string, unknown>): Promise<unknown>
  }

  export const Menu: {
    setApplicationMenu(menu: unknown): void
  }
}
