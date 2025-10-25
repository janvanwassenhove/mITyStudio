/**
 * Shared utility functions for Album Cover Dialog tests
 */

import { Page } from '@playwright/test'

/**
 * Navigate to the album cover section by bypassing welcome dialog and clicking Song tab
 */
export async function navigateToAlbumCover(page: Page) {
  // Mock audio and set test mode before page loads
  await page.addInitScript(() => {
    // Set test mode to bypass welcome dialog
    if (typeof Storage !== 'undefined') {
      localStorage.setItem('test-mode', 'true')
    }
    
    // Mock Tone.js globally
    (window as any).Tone = {
      start: () => Promise.resolve(),
      context: {
        state: 'running',
        resume: () => Promise.resolve()
      },
      Destination: {
        volume: { value: 0 }
      },
      gainToDb: (gain: number) => Math.log10(gain) * 20,
      Transport: {
        start: () => {},
        stop: () => {},
        pause: () => {},
        position: '0:0:0',
        scheduleRepeat: () => {},
        cancel: () => {},
        seconds: 0
      }
    }
  })
  
  // Navigate to the app
  await page.goto('/')
  
  // Wait for page to load
  await page.waitForSelector('.right-panel', { timeout: 10000 })
  
  // Force close welcome dialog if it still appears  
  try {
    const welcomeOverlay = page.locator('.welcome-overlay')
    if (await welcomeOverlay.isVisible({ timeout: 2000 })) {
      console.log('Welcome overlay still visible, forcing close...')
      await page.keyboard.press('Escape')
      await page.waitForTimeout(500)
      
      // If Escape doesn't work, try clicking outside the dialog
      if (await welcomeOverlay.isVisible()) {
        await welcomeOverlay.click({ position: { x: 0, y: 0 } })
        await page.waitForTimeout(500)
      }
    }
  } catch (error) {
    // Ignore timeout - dialog might not be there
  }
  
  // Click on the Song tab (id: effects) where JSONStructurePanel/album cover is located
  const songTab = page.locator('.tab-btn').filter({ hasText: 'Song' }).first()
  await songTab.click()
  
  // Wait for album cover to be visible
  await page.waitForSelector('.album-cover', { timeout: 5000 })
}

/**
 * Open the album cover dialog from the album cover section
 */
export async function openAlbumCoverDialog(page: Page) {
  // Navigate to album cover section first
  await navigateToAlbumCover(page)
  
  // Hover over album cover to show buttons
  const albumCover = page.locator('.album-cover')
  await albumCover.hover()
  
  // Click generate button
  const generateBtn = page.locator('button[title*="Generate"], [title*="Generate"] button, .cover-action-btn').first()
  await generateBtn.click()
  
  // Verify dialog appears
  const dialog = page.locator('.modal-overlay')
  await dialog.waitFor({ state: 'visible', timeout: 5000 })
  
  return dialog
}

/**
 * Setup API mocking for album cover generation
 */
export async function setupAlbumCoverMocks(page: Page) {
  await page.route('**/api/ai/generate-album-cover', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        albumCover: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
      })
    })
  })
}

/**
 * Fill album cover form with test data
 */
export async function fillAlbumCoverForm(page: Page, description = 'Test album cover', style?: string) {
  console.log('Filling album cover form...')
  
  const descriptionField = page.locator('textarea').first()
  await descriptionField.fill(description)
  console.log(`Filled description: ${description}`)
  
  if (style) {
    console.log(`Selecting style: ${style}`)
    // Find the style select specifically - it's the select in the form section
    const styleSelect = page.locator('.modal-overlay select.input').first()
    await styleSelect.selectOption(style)
    console.log(`Selected style: ${style}`)
  } else {
    console.log('Skipping style selection')
  }
}

/**
 * Wait for album cover generation to complete
 */
export async function waitForGeneration(page: Page, timeout = 30000) {
  // Wait for progress indicator to appear
  await page.locator('.progress-bar').waitFor({ state: 'visible', timeout: 5000 })
  
  // Wait for generation to complete (progress bar disappears)
  await page.locator('.progress-bar').waitFor({ state: 'hidden', timeout })
}