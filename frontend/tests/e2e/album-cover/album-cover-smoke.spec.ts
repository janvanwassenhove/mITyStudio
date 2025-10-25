/**
 * Smoke Test for Album Cover Dialog
 * 
 * Basic smoke tests to verify the album cover dialog functionality
 * without complex dependencies or mocking.
 */

import { test, expect } from '@playwright/test'
import { navigateToAlbumCover, openAlbumCoverDialog, fillAlbumCoverForm } from '../../utils/album-cover-helpers'

test.describe('Album Cover Dialog - Smoke Tests', () => {
  
  test('dialog opens when generate button is clicked', async ({ page }) => {
    const dialog = await openAlbumCoverDialog(page)
    
    // Verify dialog content - be more specific to avoid strict mode violation
    await expect(page.locator('.modal-overlay h2')).toContainText('Generate Album Cover')
  })
  
  test('form validation works correctly', async ({ page }) => {
    const dialog = await openAlbumCoverDialog(page)
    
    // Find description field and generate button
    const descriptionField = page.locator('textarea').first()
    const submitBtn = page.locator('.btn-primary').filter({ hasText: /generate/i }).first()
    
    // Clear the field first to ensure it's empty
    await descriptionField.clear()
    
    // Initially generate button should be disabled (empty description)
    await expect(submitBtn).toBeDisabled()
    
    // Fill description using helper (without style selection for simplicity)
    await fillAlbumCoverForm(page, 'Test album cover description', undefined)
    
    // Generate button should be enabled
    await expect(submitBtn).toBeEnabled()
  })
  
  test('dialog can be closed', async ({ page }) => {
    const dialog = await openAlbumCoverDialog(page)
    
    // Close with cancel button
    const cancelBtn = page.locator('button').filter({ hasText: /cancel/i }).first()
    await cancelBtn.click()
    
    // Dialog should be closed
    await expect(dialog).not.toBeVisible()
  })
  
  test('dialog is responsive on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })
    
    const dialog = await openAlbumCoverDialog(page)
    
    // Verify key elements are visible on mobile
    await expect(page.locator('textarea').first()).toBeVisible()
    await expect(page.locator('select').first()).toBeVisible()
    
    // Fill description to enable the generate button
    await fillAlbumCoverForm(page, 'Mobile test description')
    await expect(page.locator('.btn-primary').filter({ hasText: /generate/i }).first()).toBeVisible()
  })
})

test.describe('Album Cover Dialog - Basic Accessibility', () => {
  
  test('dialog can be closed with cancel button', async ({ page }) => {
    const dialog = await openAlbumCoverDialog(page)
    
    // Click cancel button
    const cancelBtn = page.locator('.btn-secondary').filter({ hasText: /cancel/i }).first()
    await cancelBtn.click()
    
    // Dialog should close
    await expect(dialog).not.toBeVisible()
  })
  
  test('form elements are keyboard accessible', async ({ page }) => {
    const dialog = await openAlbumCoverDialog(page)
    
    // Tab through form elements
    await page.keyboard.press('Tab')
    const focusedElement1 = page.locator(':focus')
    await expect(focusedElement1).toBeVisible()
    
    await page.keyboard.press('Tab')
    const focusedElement2 = page.locator(':focus')
    await expect(focusedElement2).toBeVisible()
  })
})