import assert from 'node:assert/strict'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const distRoot = path.resolve(import.meta.dirname, '..', 'dist', 'main')
const { resolveEditableEnvFile } = await import(
  pathToFileURL(path.join(distRoot, 'paths.js')).href
)

const releaseRoot = path.join(path.sep, 'Applications')
const userDataPath = path.join(
  path.sep,
  'Users',
  'student',
  'Library',
  'Application Support',
  'SUSTech Campus Assistant',
)

assert.equal(
  resolveEditableEnvFile({
    isPackaged: true,
    platform: 'darwin',
    releaseRoot,
    userDataPath,
  }),
  path.join(userDataPath, 'config', '.env'),
)

assert.equal(
  resolveEditableEnvFile({
    isPackaged: true,
    platform: 'linux',
    releaseRoot,
    userDataPath,
  }),
  path.join(releaseRoot, 'config', '.env'),
)

assert.equal(
  resolveEditableEnvFile({
    envOverride: '/tmp/custom.env',
    isPackaged: true,
    platform: 'darwin',
    releaseRoot,
    userDataPath,
  }),
  '/tmp/custom.env',
)
