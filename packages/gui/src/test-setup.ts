/**
 * Vitest setup file — runs before each test file.
 * Provides jsdom-compatible globals that the browser environment provides.
 */

const noopStorage = {
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {},
  clear: () => {},
  key: () => null,
  get length(): number {
    return 0
  },
}

Object.defineProperty(globalThis, 'localStorage', {
  value: noopStorage,
  writable: true,
  configurable: true,
})
