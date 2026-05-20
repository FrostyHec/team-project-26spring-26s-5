import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const distRoot = path.resolve(import.meta.dirname, '..', 'dist', 'main')
const { parseEnv, readRuntimeEnv } = await import(
  pathToFileURL(path.join(distRoot, 'env.js')).href
)

assert.deepEqual(parseEnv('APP_HOST=127.0.0.1\n# comment\nAPP_PORT=8123\n'), {
  APP_HOST: '127.0.0.1',
  APP_PORT: '8123',
})
assert.deepEqual(parseEnv('QUOTED="hello world"\nSINGLE=\'ok\''), {
  QUOTED: 'hello world',
  SINGLE: 'ok',
})

const tmp = mkdtempSync(path.join(tmpdir(), 'sustech-campus-assistant-env-'))
try {
  const envFile = path.join(tmp, '.env')
  writeFileSync(envFile, 'APP_HOST=127.0.0.2\nAPP_PORT=9234\nDATA_PATH=../output\n')
  assert.deepEqual(readRuntimeEnv(envFile), {
    appHost: '127.0.0.2',
    appPort: 9234,
    dataPath: '../output',
  })

  const badEnvFile = path.join(tmp, 'bad.env')
  writeFileSync(badEnvFile, 'APP_PORT=bad\n')
  assert.throws(() => readRuntimeEnv(badEnvFile), /Invalid APP_PORT/)
} finally {
  rmSync(tmp, { recursive: true, force: true })
}
