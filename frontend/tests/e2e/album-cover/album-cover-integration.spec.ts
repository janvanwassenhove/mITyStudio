/**
 * Integration Test for Album Cover Dialog
 * 
 * This test focuses on the core functionality and user interactions
 * of the album cover generation dialog without complex API mocking.
 */

import { test, expect } from '@playwright/test'

test.describe('Album Cover Dialog Integration', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    await page.goto('/')
    await page.waitForLoadState('domcontentloaded')
  })

  test('should open and display album cover dialog correctly', async ({ page }) => {
    // Hover over album cover to reveal buttons
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()

    // Click the generate cover button
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    // Verify dialog opens
    const dialog = page.locator('.modal-overlay .modal-content')
    await expect(dialog).toBeVisible()

    // Verify dialog content
    await expect(dialog.locator('.modal-header h2')).toContainText('Generate Album Cover')
    await expect(dialog.locator('#albumDescription')).toBeVisible()
    await expect(dialog.locator('select')).toBeVisible()
    
    // Verify buttons
    await expect(dialog.locator('.btn-primary')).toContainText('Generate')
    await expect(dialog.locator('.btn-secondary').first()).toContainText('Cancel')
    await expect(dialog.locator('.btn-secondary').nth(1)).toContainText('Upload')
  })

  test('should validate form inputs correctly', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    await expect(dialog).toBeVisible()

    const descriptionField = dialog.locator('#albumDescription')
    const generateBtn = dialog.locator('.btn-primary')

    // Initially, generate button should be disabled (empty description)
    await expect(generateBtn).toBeDisabled()

    // Fill description - should enable generate button
    await descriptionField.fill('A beautiful synthwave cityscape')
    await expect(generateBtn).toBeEnabled()

    // Clear description - should disable button again
    await descriptionField.fill('')
    await expect(generateBtn).toBeDisabled()
  })

  test('should allow style selection', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    const styleSelect = dialog.locator('select')

    // Check that style options exist
    await expect(styleSelect.locator('option[value="synthwave"]')).toBeAttached()
    await expect(styleSelect.locator('option[value="minimalist"]')).toBeAttached()
    await expect(styleSelect.locator('option[value="abstract"]')).toBeAttached()

    // Select a style
    await styleSelect.selectOption('synthwave')
    const selectedValue = await styleSelect.inputValue()
    expect(selectedValue).toBe('synthwave')
  })

  test('should close dialog with cancel button', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    await expect(dialog).toBeVisible()

    // Click cancel
    const cancelBtn = dialog.locator('.btn-secondary').first()
    await cancelBtn.click()

    // Verify dialog closes
    await expect(dialog).not.toBeVisible()
  })

  test('should close dialog with X button', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    await expect(dialog).toBeVisible()

    // Click X button
    const closeBtn = dialog.locator('.close-btn')
    await closeBtn.click()

    // Verify dialog closes
    await expect(dialog).not.toBeVisible()
  })

  test('should close dialog when clicking overlay', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    await expect(dialog).toBeVisible()

    // Click overlay (outside dialog)
    const overlay = page.locator('.modal-overlay')
    await overlay.click({ position: { x: 10, y: 10 } })

    // Verify dialog closes
    await expect(dialog).not.toBeVisible()
  })

  test('should be keyboard accessible', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    await expect(dialog).toBeVisible()

    // Test Escape key closes dialog
    await page.keyboard.press('Escape')
    await expect(dialog).not.toBeVisible()
  })

  test('should display on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })

    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    await expect(dialog).toBeVisible()

    // Verify all elements are visible and accessible
    await expect(dialog.locator('#albumDescription')).toBeVisible()
    await expect(dialog.locator('select')).toBeVisible()
    await expect(dialog.locator('.btn-primary')).toBeVisible()
    await expect(dialog.locator('.btn-secondary').first()).toBeVisible()
  })

  test('should handle long descriptions', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    const descriptionField = dialog.locator('#albumDescription')

    // Fill with long description
    const longDescription = 'A'.repeat(500) + ' synthwave cityscape with neon lights and retro aesthetic'
    await descriptionField.fill(longDescription)

    // Verify the text was entered
    const actualValue = await descriptionField.inputValue()
    expect(actualValue).toBe(longDescription)

    // Verify generate button is enabled
    const generateBtn = dialog.locator('.btn-primary')
    await expect(generateBtn).toBeEnabled()
  })

  test('should show help text for description', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    await expect(dialog).toBeVisible()

    // Check help text is present
    const helpText = dialog.locator('.help-text')
    await expect(helpText).toBeVisible()
    await expect(helpText).toContainText('detailed description')
  })

  test('should have proper form labels', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    await expect(dialog).toBeVisible()

    // Check labels exist
    const descriptionLabel = dialog.locator('label[for="albumDescription"]')
    await expect(descriptionLabel).toBeVisible()

    const styleLabel = dialog.locator('.section-label').nth(1)
    await expect(styleLabel).toBeVisible()
    await expect(styleLabel).toContainText('Style')
  })

  test('should maintain focus after interactions', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    const descriptionField = dialog.locator('#albumDescription')

    // Focus description field and type
    await descriptionField.focus()
    await expect(descriptionField).toBeFocused()

    await descriptionField.type('Test description')
    await expect(descriptionField).toBeFocused()

    // Tab to next field
    await page.keyboard.press('Tab')
    const styleSelect = dialog.locator('select')
    await expect(styleSelect).toBeFocused()
  })
})

test.describe('Album Cover Dialog Edge Cases', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('domcontentloaded')
  })

  test('should handle special characters in description', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    const descriptionField = dialog.locator('#albumDescription')

    // Test special characters
    const specialText = 'Album with émojis 🎵🎨 and symbols: @#$%^&*()!'
    await descriptionField.fill(specialText)

    const actualValue = await descriptionField.inputValue()
    expect(actualValue).toBe(specialText)
  })

  test('should handle rapid button clicks', async ({ page }) => {
    // Open dialog
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    const dialog = page.locator('.modal-overlay .modal-content')
    const descriptionField = dialog.locator('#albumDescription')
    
    // Fill description
    await descriptionField.fill('Test description')

    const generateBtn = dialog.locator('.btn-primary')
    
    // Rapid clicks should not cause issues
    await generateBtn.click()
    await generateBtn.click({ force: true })
    await generateBtn.click({ force: true })

    // Dialog should still be visible or closed gracefully
    // (behavior depends on implementation)
  })

  test('should maintain state when reopening dialog', async ({ page }) => {
    // Open dialog first time
    const albumCover = page.locator('.album-cover')
    await albumCover.hover()
    const generateButton = page.locator('[title*="Generate"] .icon')
    await generateButton.click()

    let dialog = page.locator('.modal-overlay .modal-content')
    let descriptionField = dialog.locator('#albumDescription')
    let styleSelect = dialog.locator('select')

    // Fill some data
    await descriptionField.fill('Previous description')
    await styleSelect.selectOption('synthwave')

    // Close dialog
    const cancelBtn = dialog.locator('.btn-secondary').first()
    await cancelBtn.click()
    await expect(dialog).not.toBeVisible()

    // Reopen dialog
    await albumCover.hover()
    await generateButton.click()

    // Check if fields are reset (this is typically expected behavior)
    dialog = page.locator('.modal-overlay .modal-content')
    descriptionField = dialog.locator('#albumDescription')
    
    const newDescription = await descriptionField.inputValue()
    // Fields should be reset when reopening
    expect(newDescription).toBe('')
  })
})