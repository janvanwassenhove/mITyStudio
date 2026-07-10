// macOS notarization hook (electron-builder afterSign).
//
// TODO (manual prerequisite, cannot be automated): notarization requires a
// paid Apple Developer account. Once available, set these secrets in the
// GitHub repo (and locally for manual builds):
//   APPLE_ID           — developer Apple ID e-mail
//   APPLE_APP_PASSWORD — app-specific password
//   APPLE_TEAM_ID      — team identifier
// and `npm i -D @electron/notarize` in apps/desktop. Until then this hook
// no-ops and the produced .dmg runs only with right-click → Open (Gatekeeper).
//
// Windows equivalent (also manual): an EV/OV code-signing certificate.
// Provide it via electron-builder env vars CSC_LINK (path/base64 of .pfx)
// and CSC_KEY_PASSWORD; without it the installer is unsigned and SmartScreen
// shows "unknown publisher" until reputation accrues.
exports.default = async function notarize(context) {
  if (context.electronPlatformName !== 'darwin') return
  const { APPLE_ID, APPLE_APP_PASSWORD, APPLE_TEAM_ID } = process.env
  if (!APPLE_ID || !APPLE_APP_PASSWORD || !APPLE_TEAM_ID) {
    console.log('[notarize] skipped — Apple credentials not configured (see build/notarize.js)')
    return
  }
  const { notarize } = require('@electron/notarize')
  const appName = context.packager.appInfo.productFilename
  await notarize({
    appPath: `${context.appOutDir}/${appName}.app`,
    appleId: APPLE_ID,
    appleIdPassword: APPLE_APP_PASSWORD,
    teamId: APPLE_TEAM_ID,
  })
}
