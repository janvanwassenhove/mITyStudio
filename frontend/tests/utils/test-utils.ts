/**
 * Test Utilities for Album Cover Dialog
 * 
 * This file contains utility functions and helpers for testing the album cover dialog feature.
 * It follows Playwright best practices and provides reusable test components.
 */

import { Page, Locator, expect } from '@playwright/test'

/**
 * Test Data Factory
 * Provides consistent test data for album cover generation tests
 */
export class TestDataFactory {
  static readonly VALID_DESCRIPTIONS = [
    'A vibrant synthwave cityscape at night with neon lights',
    'Minimalist abstract art with geometric shapes',
    'Vintage vinyl record cover with retro typography',
    'Modern electronic music cover with digital elements',
    'Artistic watercolor painting of musical notes',
  ]

  static readonly INVALID_DESCRIPTIONS = [
    '', // empty
    '   ', // whitespace only
  ]

  static readonly STYLES = [
    'synthwave',
    'minimalist',
    'abstract',
    'vintage',
    'modern',
    'artistic',
    'photographic',
    'illustration',
  ]

  static randomDescription(): string {
    return this.VALID_DESCRIPTIONS[Math.floor(Math.random() * this.VALID_DESCRIPTIONS.length)]
  }

  static randomStyle(): string {
    return this.STYLES[Math.floor(Math.random() * this.STYLES.length)]
  }
}

/**
 * Mock API Response Builder
 * Helps create consistent mock responses for API testing
 */
export class MockApiBuilder {
  static successResponse(imageUrl?: string) {
    return {
      success: true,
      image_url: imageUrl || 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=='
    }
  }

  static errorResponse(error?: string) {
    return {
      success: false,
      error: error || 'Generation failed'
    }
  }
}

/**
 * Wait Utilities
 * Common waiting patterns for async operations
 */
export class WaitUtils {
  static async waitForApiCall(page: Page, apiPath: string): Promise<void> {
    await page.waitForRequest(request => 
      request.url().includes(apiPath) && request.method() === 'POST'
    )
  }

  static async waitForDialogAnimation(locator: Locator): Promise<void> {
    // Wait for dialog to appear with animation
    await locator.waitFor({ state: 'visible' })
    // Additional wait for animation to complete
    await locator.page().waitForTimeout(300)
  }

  static async waitForProgressAnimation(progressBar: Locator): Promise<void> {
    // Wait for progress to start
    await progressBar.waitFor({ state: 'visible' })
    
    // Wait for some progress to be made
    await expect(progressBar.locator('.progress-fill')).not.toHaveCSS('width', '0%')
  }
}

/**
 * Assertion Helpers
 * Custom assertions for album cover dialog functionality
 */
export class AssertionHelpers {
  static async assertDialogIsOpen(dialog: Locator): Promise<void> {
    await expect(dialog).toBeVisible()
    await expect(dialog.locator('.modal-header h2')).toContainText('Generate Album Cover')
  }

  static async assertDialogIsClosed(dialog: Locator): Promise<void> {
    await expect(dialog).not.toBeVisible()
  }

  static async assertFormIsInteractive(descriptionField: Locator, styleSelect: Locator): Promise<void> {
    await expect(descriptionField).toBeEnabled()
    await expect(descriptionField).toBeEditable()
    await expect(styleSelect).toBeEnabled()
  }

  static async assertButtonStates(
    generateBtn: Locator, 
    cancelBtn: Locator, 
    uploadBtn: Locator,
    expectedState: 'enabled' | 'disabled'
  ): Promise<void> {
    const assertion = expectedState === 'enabled' ? expect : (loc: Locator) => expect(loc).toBeDisabled()
    
    if (expectedState === 'enabled') {
      await expect(generateBtn).toBeEnabled()
      await expect(cancelBtn).toBeEnabled()  
      await expect(uploadBtn).toBeEnabled()
    } else {
      await expect(generateBtn).toBeDisabled()
      await expect(cancelBtn).toBeDisabled()
      await expect(uploadBtn).toBeDisabled()
    }
  }

  static async assertProgressIsVisible(progressSection: Locator): Promise<void> {
    await expect(progressSection).toBeVisible()
    await expect(progressSection.locator('.progress-bar')).toBeVisible()
    await expect(progressSection.locator('.progress-text')).toBeVisible()
  }

  static async assertApiRequestPayload(page: Page, expectedDescription: string, expectedStyle?: string): Promise<void> {
    const request = await page.waitForRequest(req => 
      req.url().includes('/api/ai/generate/image') && req.method() === 'POST'
    )
    
    const postData = JSON.parse(request.postData() || '{}')
    expect(postData.prompt).toContain(expectedDescription)
    
    if (expectedStyle) {
      expect(postData.prompt).toContain(expectedStyle)
    }
  }
}

/**
 * Accessibility Test Helpers
 * Utilities for testing accessibility compliance
 */
export class AccessibilityHelpers {
  static async testKeyboardNavigation(page: Page, focusableElements: Locator[]): Promise<void> {
    for (let i = 0; i < focusableElements.length; i++) {
      await page.keyboard.press('Tab')
      await expect(focusableElements[i]).toBeFocused()
    }
  }

  static async testAriaLabels(dialog: Locator): Promise<void> {
    // Check form labels exist and are properly associated
    const descriptionLabel = dialog.locator('label[for="albumDescription"]')
    await expect(descriptionLabel).toBeVisible()
    
    const descriptionField = dialog.locator('#albumDescription')
    await expect(descriptionField).toBeVisible()
  }

  static async testEscapeKeyClose(page: Page, dialog: Locator): Promise<void> {
    await expect(dialog).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).not.toBeVisible()
  }
}

/**
 * Visual Test Helpers
 * Utilities for visual regression and responsive testing
 */
export class VisualHelpers {
  static readonly VIEWPORT_SIZES = {
    mobile: { width: 375, height: 667 },    // iPhone SE
    tablet: { width: 768, height: 1024 },   // iPad
    desktop: { width: 1920, height: 1080 }, // Full HD
  }

  static async testResponsiveLayout(page: Page, dialog: Locator, viewportName: keyof typeof VisualHelpers.VIEWPORT_SIZES): Promise<void> {
    const viewport = this.VIEWPORT_SIZES[viewportName]
    await page.setViewportSize(viewport)
    
    // Verify dialog is still visible and usable
    await expect(dialog).toBeVisible()
    
    // Check that all key elements are visible
    await expect(dialog.locator('.modal-header')).toBeVisible()
    await expect(dialog.locator('.modal-body')).toBeVisible()
    await expect(dialog.locator('.modal-footer')).toBeVisible()
    
    // On mobile, buttons should stack vertically
    if (viewportName === 'mobile') {
      const footer = dialog.locator('.modal-footer')
      await expect(footer).toHaveCSS('flex-direction', 'column')
    }
  }

  static async takeDialogScreenshot(dialog: Locator, name: string): Promise<void> {
    await dialog.screenshot({ path: `test-results/screenshots/${name}.png` })
  }
}

/**
 * Performance Test Helpers
 * Utilities for testing performance characteristics
 */
export class PerformanceHelpers {
  static async measureDialogOpenTime(page: Page, triggerAction: () => Promise<void>): Promise<number> {
    const startTime = Date.now()
    await triggerAction()
    await page.locator('.modal-overlay').waitFor({ state: 'visible' })
    return Date.now() - startTime
  }

  static async measureApiResponseTime(page: Page, apiPath: string, action: () => Promise<void>): Promise<number> {
    const startTime = Date.now()
    
    const responsePromise = page.waitForResponse(response => 
      response.url().includes(apiPath) && response.status() === 200
    )
    
    await action()
    await responsePromise
    
    return Date.now() - startTime
  }
}

/**
 * Error Simulation Helpers
 * Utilities for testing error handling scenarios
 */
export class ErrorSimulationHelpers {
  static async simulateNetworkError(page: Page, apiPath: string): Promise<void> {
    await page.route(apiPath, route => route.abort())
  }

  static async simulateSlowNetwork(page: Page, apiPath: string, delayMs: number = 5000): Promise<void> {
    await page.route(apiPath, async route => {
      await new Promise(resolve => setTimeout(resolve, delayMs))
      await route.continue()
    })
  }

  static async simulateServerError(page: Page, apiPath: string, statusCode: number = 500): Promise<void> {
    await page.route(apiPath, route => {
      route.fulfill({
        status: statusCode,
        contentType: 'application/json',
        body: JSON.stringify(MockApiBuilder.errorResponse('Server error'))
      })
    })
  }
}