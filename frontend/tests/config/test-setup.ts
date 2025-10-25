import { test as baseTest, expect } from '@playwright/test'

// Extend the base test with custom fixtures if needed
export const test = baseTest.extend({
  // Add custom fixtures here if needed in the future
})

export { expect }