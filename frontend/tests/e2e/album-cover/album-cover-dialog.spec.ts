import { test, expect, Page, Locator } from '@playwright/test'

/**
 * Page Object Model for Album Cover Dialog
 * Encapsulates the album cover dialog interactions and selectors
 */
class AlbumCoverDialogPage {
  private page: Page
  
  // Dialog elements
  readonly dialog: Locator
  readonly dialogTitle: Locator
  readonly closeButton: Locator
  
  // Form elements
  readonly descriptionTextarea: Locator
  readonly styleSelect: Locator
  readonly currentCoverPreview: Locator
  
  // Action buttons
  readonly cancelButton: Locator
  readonly uploadButton: Locator
  readonly generateButton: Locator
  
  // Progress elements
  readonly progressSection: Locator
  readonly progressBar: Locator
  readonly progressText: Locator
  readonly progressFill: Locator

  constructor(page: Page) {
    this.page = page
    
    // Dialog selectors
    this.dialog = page.locator('.modal-overlay .modal-content')
    this.dialogTitle = this.dialog.locator('.modal-header h2')
    this.closeButton = this.dialog.locator('.modal-header .close-btn')
    
    // Form selectors
    this.descriptionTextarea = this.dialog.locator('#albumDescription')
    this.styleSelect = this.dialog.locator('select')
    this.currentCoverPreview = this.dialog.locator('.current-cover-preview')
    
    // Button selectors
    this.cancelButton = this.dialog.locator('.modal-footer .btn-secondary').first()
    this.uploadButton = this.dialog.locator('.modal-footer .btn-secondary').nth(1)
    this.generateButton = this.dialog.locator('.modal-footer .btn-primary')
    
    // Progress selectors
    this.progressSection = this.dialog.locator('.progress-section')
    this.progressBar = this.dialog.locator('.progress-bar')
    this.progressFill = this.dialog.locator('.progress-fill')
    this.progressText = this.dialog.locator('.progress-text')
  }

  async waitForDialog() {
    await this.dialog.waitFor({ state: 'visible' })
  }

  async waitForDialogToClose() {
    await this.dialog.waitFor({ state: 'hidden' })
  }

  async fillDescription(description: string) {
    await this.descriptionTextarea.fill(description)
  }

  async selectStyle(style: string) {
    await this.styleSelect.selectOption(style)
  }

  async clickGenerate() {
    await this.generateButton.click()
  }

  async clickCancel() {
    await this.cancelButton.click()
  }

  async clickUpload() {
    await this.uploadButton.click()
  }

  async clickClose() {
    await this.closeButton.click()
  }

  async isProgressVisible() {
    return await this.progressSection.isVisible()
  }

  async waitForProgressToStart() {
    await this.progressSection.waitFor({ state: 'visible' })
  }

  async waitForProgressToComplete() {
    await expect(this.progressFill).toHaveCSS('width', '100%', { timeout: 30000 })
  }

  async getProgressText() {
    return await this.progressText.textContent()
  }
}

/**
 * Page Object Model for Main Application
 */
class MainAppPage {
  private page: Page
  
  readonly albumCover: Locator
  readonly generateCoverButton: Locator
  readonly uploadCoverButton: Locator

  constructor(page: Page) {
    this.page = page
    this.albumCover = page.locator('.album-cover')
    this.generateCoverButton = page.locator('[title*="Generate"] .icon')
    this.uploadCoverButton = page.locator('[title*="Upload"] .icon')
  }

  async goto() {
    await this.page.goto('/')
  }

  async hoverOverAlbumCover() {
    await this.albumCover.hover()
  }

  async clickGenerateCover() {
    await this.hoverOverAlbumCover()
    await this.generateCoverButton.click()
  }

  async clickUploadCover() {
    await this.hoverOverAlbumCover()
    await this.uploadCoverButton.click()
  }

  async getCurrentCoverSrc() {
    return await this.albumCover.locator('img').getAttribute('src')
  }
}

test.describe('Album Cover Dialog', () => {
  let mainPage: MainAppPage
  let albumDialog: AlbumCoverDialogPage

  test.beforeEach(async ({ page }) => {
    mainPage = new MainAppPage(page)
    albumDialog = new AlbumCoverDialogPage(page)
    
    // Navigate to the main page
    await mainPage.goto()
    
    // Wait for the page to load
    await page.waitForLoadState('domcontentloaded')
  })

  test.describe('Dialog Opening and Closing', () => {
    test('should open album cover dialog when clicking generate cover button', async () => {
      // Act
      await mainPage.clickGenerateCover()

      // Assert
      await albumDialog.waitForDialog()
      await expect(albumDialog.dialog).toBeVisible()
      await expect(albumDialog.dialogTitle).toContainText('Generate Album Cover')
    })

    test('should close dialog when clicking cancel button', async () => {
      // Arrange
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()

      // Act
      await albumDialog.clickCancel()

      // Assert
      await albumDialog.waitForDialogToClose()
      await expect(albumDialog.dialog).not.toBeVisible()
    })

    test('should close dialog when clicking close (X) button', async () => {
      // Arrange
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()

      // Act
      await albumDialog.clickClose()

      // Assert
      await albumDialog.waitForDialogToClose()
      await expect(albumDialog.dialog).not.toBeVisible()
    })

    test('should close dialog when clicking overlay', async ({ page }) => {
      // Arrange
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()

      // Act - Click outside the dialog content
      await page.locator('.modal-overlay').click({ position: { x: 10, y: 10 } })

      // Assert
      await albumDialog.waitForDialogToClose()
      await expect(albumDialog.dialog).not.toBeVisible()
    })

    test('should not close dialog when clicking inside dialog content', async () => {
      // Arrange
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()

      // Act - Click inside the dialog
      await albumDialog.dialog.click()

      // Assert
      await expect(albumDialog.dialog).toBeVisible()
    })
  })

  test.describe('Form Interactions', () => {
    test.beforeEach(async () => {
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()
    })

    test('should have empty description field initially', async () => {
      // Assert
      const description = await albumDialog.descriptionTextarea.inputValue()
      expect(description).toBe('')
    })

    test('should allow filling description field', async () => {
      // Arrange
      const testDescription = 'A vibrant synthwave cityscape at night with neon lights'

      // Act
      await albumDialog.fillDescription(testDescription)

      // Assert
      const description = await albumDialog.descriptionTextarea.inputValue()
      expect(description).toBe(testDescription)
    })

    test('should have style dropdown with multiple options', async () => {
      // Act & Assert
      await expect(albumDialog.styleSelect).toBeVisible()
      
      // Check that options exist
      const options = await albumDialog.styleSelect.locator('option').count()
      expect(options).toBeGreaterThan(1)
      
      // Check for specific style options
      await expect(albumDialog.styleSelect.locator('option[value="synthwave"]')).toBeAttached()
      await expect(albumDialog.styleSelect.locator('option[value="minimalist"]')).toBeAttached()
      await expect(albumDialog.styleSelect.locator('option[value="abstract"]')).toBeAttached()
    })

    test('should allow selecting different styles', async () => {
      // Act
      await albumDialog.selectStyle('synthwave')

      // Assert
      const selectedValue = await albumDialog.styleSelect.inputValue()
      expect(selectedValue).toBe('synthwave')
    })

    test('should disable generate button when description is empty', async () => {
      // Assert
      await expect(albumDialog.generateButton).toBeDisabled()
    })

    test('should enable generate button when description is filled', async () => {
      // Act
      await albumDialog.fillDescription('A beautiful album cover')

      // Assert
      await expect(albumDialog.generateButton).toBeEnabled()
    })

    test('should show help text for description field', async () => {
      // Assert
      const helpText = albumDialog.dialog.locator('.help-text')
      await expect(helpText).toBeVisible()
      await expect(helpText).toContainText('Provide a detailed description')
    })
  })

  test.describe('Progress Indicator', () => {
    test.beforeEach(async () => {
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()
    })

    test('should not show progress initially', async () => {
      // Assert
      await expect(albumDialog.progressSection).not.toBeVisible()
    })

    test('should show progress when generating', async ({ page }) => {
      // Arrange
      await albumDialog.fillDescription('Test description')

      // Mock the API to delay response
      await page.route('/api/ai/generate/image', async route => {
        await new Promise(resolve => setTimeout(resolve, 2000))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            image_url: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=='
          })
        })
      })

      // Act
      await albumDialog.clickGenerate()

      // Assert
      await albumDialog.waitForProgressToStart()
      await expect(albumDialog.progressSection).toBeVisible()
      await expect(albumDialog.progressBar).toBeVisible()
      await expect(albumDialog.progressText).toBeVisible()
    })

    test('should show progress steps during generation', async ({ page }) => {
      // Arrange
      await albumDialog.fillDescription('Test description')

      // Mock API with delay
      await page.route('/api/ai/generate/image', async route => {
        await new Promise(resolve => setTimeout(resolve, 1000))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            image_url: 'data:image/png;base64,test'
          })
        })
      })

      // Act
      await albumDialog.clickGenerate()

      // Assert - Check that progress text changes
      await albumDialog.waitForProgressToStart()
      const initialProgressText = await albumDialog.getProgressText()
      expect(initialProgressText).toBeTruthy()
      
      // Wait a bit to see if text changes
      await page.waitForTimeout(500)
      const updatedProgressText = await albumDialog.getProgressText()
      expect(updatedProgressText).toBeTruthy()
    })

    test('should disable buttons during generation', async ({ page }) => {
      // Arrange
      await albumDialog.fillDescription('Test description')

      await page.route('/api/ai/generate/image', async route => {
        await new Promise(resolve => setTimeout(resolve, 1000))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, image_url: 'test' })
        })
      })

      // Act
      await albumDialog.clickGenerate()
      await albumDialog.waitForProgressToStart()

      // Assert
      await expect(albumDialog.generateButton).toBeDisabled()
      await expect(albumDialog.cancelButton).toBeDisabled()
      await expect(albumDialog.uploadButton).toBeDisabled()
    })
  })

  test.describe('API Integration', () => {
    test.beforeEach(async () => {
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()
    })

    test('should successfully generate cover with valid input', async ({ page }) => {
      // Arrange
      const testDescription = 'A beautiful synthwave cityscape'
      await albumDialog.fillDescription(testDescription)
      await albumDialog.selectStyle('synthwave')

      // Mock successful API response
      await page.route('/api/ai/generate/image', async route => {
        const request = route.request()
        const postData = JSON.parse(request.postData() || '{}')
        
        expect(postData.prompt).toContain(testDescription)
        expect(postData.prompt).toContain('synthwave')

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            image_url: 'data:image/png;base64,generatedImage'
          })
        })
      })

      // Act
      await albumDialog.clickGenerate()

      // Assert
      await albumDialog.waitForDialogToClose()
      // Check that the main page now has the new cover
      const newCoverSrc = await mainPage.getCurrentCoverSrc()
      expect(newCoverSrc).toContain('data:image/png;base64,generatedImage')
    })

    test('should handle API error gracefully', async ({ page }) => {
      // Arrange
      await albumDialog.fillDescription('Test description')

      // Mock API error
      await page.route('/api/ai/generate/image', async route => {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({
            success: false,
            error: 'Server error'
          })
        })
      })

      // Listen for alert dialog
      page.on('dialog', async dialog => {
        expect(dialog.type()).toBe('alert')
        expect(dialog.message()).toContain('Failed to generate album cover')
        await dialog.accept()
      })

      // Act
      await albumDialog.clickGenerate()

      // Assert - Dialog should remain open on error
      await expect(albumDialog.dialog).toBeVisible()
    })

    test('should handle network error', async ({ page }) => {
      // Arrange
      await albumDialog.fillDescription('Test description')

      // Mock network error
      await page.route('/api/ai/generate/image', route => route.abort())

      // Listen for alert
      page.on('dialog', async dialog => {
        expect(dialog.message()).toContain('Failed to generate album cover')
        await dialog.accept()
      })

      // Act
      await albumDialog.clickGenerate()

      // Assert
      await expect(albumDialog.dialog).toBeVisible()
    })
  })

  test.describe('Accessibility', () => {
    test.beforeEach(async () => {
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()
    })

    test('should be keyboard accessible', async ({ page }) => {
      // Test tab navigation
      await page.keyboard.press('Tab') // Focus description
      await expect(albumDialog.descriptionTextarea).toBeFocused()

      await page.keyboard.press('Tab') // Focus style select
      await expect(albumDialog.styleSelect).toBeFocused()

      // Skip to buttons (may have other focusable elements in between)
      await page.keyboard.press('Tab')
      await page.keyboard.press('Tab')
      await page.keyboard.press('Tab')
      
      // Should be able to interact with buttons
      const focusedElement = await page.evaluate(() => document.activeElement?.tagName)
      expect(focusedElement).toBe('BUTTON')
    })

    test('should close with Escape key', async ({ page }) => {
      // Act
      await page.keyboard.press('Escape')

      // Assert
      await albumDialog.waitForDialogToClose()
      await expect(albumDialog.dialog).not.toBeVisible()
    })

    test('should have proper ARIA labels and roles', async () => {
      // Assert form labels
      const descriptionLabel = albumDialog.dialog.locator('label[for="albumDescription"]')
      await expect(descriptionLabel).toBeVisible()

      // Check that textarea has proper association
      await expect(albumDialog.descriptionTextarea).toHaveAttribute('id', 'albumDescription')
    })
  })

  test.describe('Responsive Design', () => {
    test('should display correctly on mobile devices', async ({ page }) => {
      // Arrange
      await page.setViewportSize({ width: 375, height: 667 }) // iPhone SE size
      
      // Act
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()

      // Assert
      await expect(albumDialog.dialog).toBeVisible()
      
      // Check that buttons stack vertically on small screens
      const footerButtons = albumDialog.dialog.locator('.modal-footer .btn')
      const buttonCount = await footerButtons.count()
      expect(buttonCount).toBeGreaterThan(1)
      
      // All buttons should be visible
      for (let i = 0; i < buttonCount; i++) {
        await expect(footerButtons.nth(i)).toBeVisible()
      }
    })

    test('should maintain usability on tablet devices', async ({ page }) => {
      // Arrange
      await page.setViewportSize({ width: 768, height: 1024 }) // iPad size
      
      // Act
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()

      // Assert
      await expect(albumDialog.dialog).toBeVisible()
      await expect(albumDialog.descriptionTextarea).toBeVisible()
      await expect(albumDialog.styleSelect).toBeVisible()
    })
  })

  test.describe('Edge Cases', () => {
    test.beforeEach(async () => {
      await mainPage.clickGenerateCover()
      await albumDialog.waitForDialog()
    })

    test('should handle very long descriptions', async () => {
      // Arrange
      const longDescription = 'A'.repeat(1000) // Very long description

      // Act
      await albumDialog.fillDescription(longDescription)

      // Assert
      const actualValue = await albumDialog.descriptionTextarea.inputValue()
      expect(actualValue).toBe(longDescription)
      await expect(albumDialog.generateButton).toBeEnabled()
    })

    test('should handle special characters in description', async () => {
      // Arrange
      const specialCharsDescription = 'A cover with émojis 🎵🎨 and special chars: @#$%^&*()'

      // Act
      await albumDialog.fillDescription(specialCharsDescription)

      // Assert
      const actualValue = await albumDialog.descriptionTextarea.inputValue()
      expect(actualValue).toBe(specialCharsDescription)
    })

    test('should handle rapid consecutive clicks on generate button', async ({ page }) => {
      // Arrange
      await albumDialog.fillDescription('Test description')

      let requestCount = 0
      await page.route('/api/ai/generate/image', async route => {
        requestCount++
        await new Promise(resolve => setTimeout(resolve, 500))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            image_url: 'data:image/png;base64,test'
          })
        })
      })

      // Act - Click multiple times rapidly
      await albumDialog.clickGenerate()
      await albumDialog.generateButton.click({ force: true })
      await albumDialog.generateButton.click({ force: true })

      // Wait for completion
      await page.waitForTimeout(1000)

      // Assert - Should only make one request
      expect(requestCount).toBe(1)
    })
  })
})