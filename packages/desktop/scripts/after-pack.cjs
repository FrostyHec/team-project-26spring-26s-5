const fs = require('node:fs/promises')
const path = require('node:path')

async function exists(filePath) {
  try {
    await fs.access(filePath)
    return true
  } catch {
    return false
  }
}

async function afterPack(context) {
  if (context.electronPlatformName !== 'linux') {
    return
  }

  const executableName =
    context.packager.executableName ||
    context.packager.appInfo?.executableName ||
    context.packager.appInfo?.sanitizedProductName
  if (!executableName) {
    throw new Error('Cannot determine Linux executable name for no-sandbox wrapper')
  }

  const executablePath = path.join(context.appOutDir, executableName)
  const realExecutablePath = `${executablePath}.bin`
  if (!(await exists(executablePath))) {
    throw new Error(`Linux executable not found: ${executablePath}`)
  }

  const currentContent = await fs.readFile(executablePath)
  if (currentContent.subarray(0, 2).toString() === '#!') {
    return
  }
  if (await exists(realExecutablePath)) {
    throw new Error(`Wrapped executable already exists: ${realExecutablePath}`)
  }

  await fs.rename(executablePath, realExecutablePath)
  await fs.writeFile(
    executablePath,
    [
      '#!/usr/bin/env sh',
      'APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"',
      `exec "$APP_DIR/${executableName}.bin" --no-sandbox "$@"`,
      '',
    ].join('\n'),
    { mode: 0o755 },
  )
  await fs.chmod(executablePath, 0o755)
}

module.exports = afterPack
module.exports.default = afterPack
