import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test-setup.ts'],
      exclude: [...configDefaults.exclude, 'e2e/**'],
      fileParallelism: false,
      pool: 'forks',
      root: fileURLToPath(new URL('./', import.meta.url)),
    },
  }),
)
