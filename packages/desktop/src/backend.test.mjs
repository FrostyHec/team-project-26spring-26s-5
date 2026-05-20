import assert from 'node:assert/strict'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const distRoot = path.resolve(import.meta.dirname, '..', 'dist', 'main')
const { buildBackendArgs } = await import(pathToFileURL(path.join(distRoot, 'backend.js')).href)

const args = buildBackendArgs({
  backendBin: '/app/bin/react-agent-backend',
  envFile: '/app/config/.env',
  staticDir: '/app/gui',
  host: '127.0.0.1',
  port: 8123,
  logRoot: '/app/output/logs',
})

assert.deepEqual(args, [
  'serve',
  '--env-file',
  '/app/config/.env',
  '--host',
  '127.0.0.1',
  '--port',
  '8123',
  '--static-dir',
  '/app/gui',
])
