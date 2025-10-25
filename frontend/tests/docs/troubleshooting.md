# Troubleshooting Guide - Album Cover Dialog Tests

## 🚨 **Common Issues and Solutions**

### **1. Server Connection Issues**

#### **Error: `Error: connect ECONNREFUSED 127.0.0.1:5173`**

**Symptoms**:
```
browserType.launch: Host validation error
× Failed to connect to http://localhost:5173
× Connection refused
```

**Solutions**:

**Option A: Manual Server Start** ⭐ **Recommended**
```bash
# Terminal 1: Start frontend server
cd frontend
npm run dev
# Wait for "Local: http://localhost:5173/" message

# Terminal 2: Run tests
npx playwright test --config=playwright.config.local.ts
```

**Option B: Use CI Config** (Automatic server)
```bash
npx playwright test --config=playwright.config.ts
```

**Option C: Force Port Configuration**
```bash
# Check if port 5173 is in use
netstat -ano | findstr :5173

# Kill process if needed
taskkill /PID <process_id> /F

# Start with specific port
npm run dev -- --port 5174
```

---

### **2. Port Conflicts**

#### **Error: `Port 5173 is already in use`**

**Symptoms**:
- Server won't start on expected port
- Tests connect to wrong application
- Multiple instances running

**Solutions**:

**Check Port Usage**:
```bash
# Windows PowerShell
Get-NetTCPConnection -LocalPort 5173 -State Listen
netstat -ano | findstr :5173
```

**Kill Conflicting Processes**:
```bash
# Find and kill Node.js processes
taskkill /F /IM node.exe
taskkill /F /IM npm.cmd

# Or kill specific PID
taskkill /PID <process_id> /F
```

**Alternative Port Strategy**:
```bash
# Start on different port
npm run dev -- --port 5174

# Update test config temporarily
# In playwright.config.local.ts, change baseURL to http://localhost:5174
```

---

### **3. Playwright Browser Issues**

#### **Error: `browserType.launch: Executable doesn't exist`**

**Symptoms**:
```
Error: browserType.launch: Executable doesn't exist at /path/to/chromium
× Browser not found
```

**Solutions**:

**Install Browsers**:
```bash
# Install all browsers
npx playwright install

# Install specific browser
npx playwright install chromium

# Install with system dependencies
npx playwright install --with-deps
```

**Force Reinstall**:
```bash
# Clear browser cache and reinstall
npx playwright install --force
```

**Check Installation**:
```bash
# Verify installation
npx playwright install --dry-run
```

---

### **4. Test Timeout Issues**

#### **Error: `Test timeout of 30000ms exceeded`**

**Symptoms**:
- Tests hang during execution
- Dialog doesn't appear in time
- API calls take too long

**Solutions**:

**Increase Timeouts**:
```typescript
// In test file
test('should generate album cover', async ({ page }) => {
  test.setTimeout(60000); // Increase to 60 seconds
  // ... test code
});
```

**Check Element Visibility**:
```typescript
// Wait for element with longer timeout
await page.waitForSelector('[data-testid="generate-dialog"]', { 
  timeout: 10000 
});
```

**Debug Timeout Issues**:
```bash
# Run with visual debugging
npx playwright test --debug --headed

# Use slow motion
npx playwright test --headed --slow-mo=1000
```

---

### **5. Element Not Found Errors**

#### **Error: `Error: locator.click: No such element`**

**Symptoms**:
- Selectors not finding elements
- Elements not visible/interactive
- Dynamic content not loaded

**Solutions**:

**Wait for Elements**:
```typescript
// Wait for element to be visible
await page.waitForSelector('[data-testid="album-cover-button"]', {
  state: 'visible'
});

// Wait for network idle
await page.waitForLoadState('networkidle');
```

**Debug Selectors**:
```bash
# Use Playwright inspector
npx playwright test --debug

# Generate selectors interactively
npx playwright codegen http://localhost:5173
```

**Verify Selectors**:
```typescript
// Check if element exists
const element = await page.locator('[data-testid="generate-dialog"]');
console.log('Element count:', await element.count());
```

---

### **6. API Mock Issues**

#### **Error: API calls failing in tests**

**Symptoms**:
- Real API calls during tests
- Network errors in test environment
- Inconsistent test results

**Solutions**:

**Setup API Mocking**:
```typescript
import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Mock album generation API
  await page.route('**/api/ai/generate-album-cover', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        albumCover: 'data:image/png;base64,mock-image-data'
      })
    });
  });
});
```

**Debug API Calls**:
```typescript
// Log network activity
page.on('request', request => {
  console.log('Request:', request.url(), request.method());
});

page.on('response', response => {
  console.log('Response:', response.url(), response.status());
});
```

---

### **7. Translation/i18n Issues**

#### **Error: Translation keys not found**

**Symptoms**:
- Missing text in components
- Translation keys showing instead of text
- Language switching not working

**Solutions**:

**Verify Translation Files**:
```bash
# Check if translation files exist
ls frontend/src/locales/
```

**Test Different Languages**:
```typescript
// Test with specific language
await page.evaluate(() => {
  localStorage.setItem('language', 'nl');
  window.location.reload();
});
```

**Debug Missing Translations**:
```typescript
// Check for missing translation keys in console
page.on('console', msg => {
  if (msg.text().includes('translation key')) {
    console.log('Missing translation:', msg.text());
  }
});
```

---

### **8. State Management Issues**

#### **Error: Pinia store not accessible**

**Symptoms**:
- Store data not available
- State changes not reflected
- Component props undefined

**Solutions**:

**Reset Store State**:
```typescript
test.beforeEach(async ({ page }) => {
  // Reset application state
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
});
```

**Mock Store Data**:
```typescript
// Inject mock data into store
await page.evaluate(() => {
  window.__MOCK_AUDIO_STORE__ = {
    currentProject: { /* mock project data */ }
  };
});
```

---

### **9. File System Issues**

#### **Error: Permission denied or file access issues**

**Symptoms**:
- Cannot write test results
- Screenshots not saved
- Trace files not generated

**Solutions**:

**Check Permissions**:
```bash
# Windows PowerShell - check directory permissions
Get-Acl frontend/test-results

# Create directories manually if needed
mkdir -p frontend/test-results
mkdir -p frontend/playwright-report
```

**Clear Test Artifacts**:
```bash
# Remove old test results
Remove-Item -Recurse -Force frontend/test-results
Remove-Item -Recurse -Force frontend/playwright-report

# Clear npm cache
npm cache clean --force
```

---

### **10. Configuration Issues**

#### **Error: Config file not found or invalid**

**Symptoms**:
- Playwright config errors
- Tests not finding configuration
- Environment variables not loaded

**Solutions**:

**Verify Config Files**:
```bash
# Check if config files exist
ls frontend/playwright.config*.ts
```

**Validate Configuration**:
```bash
# Test config syntax
npx playwright test --list
```

**Environment Variables**:
```bash
# Set required environment variables
$env:NODE_ENV = "test"
$env:CI = "false"

# For cross-platform compatibility
npm run test:e2e
```

---

## 🔧 **Debugging Techniques**

### **1. Visual Debugging**

```bash
# Run tests with browser visible
npx playwright test --headed

# Slow motion execution
npx playwright test --headed --slow-mo=1000

# Interactive debugging
npx playwright test --debug
```

### **2. Trace Analysis**

```bash
# Collect traces
npx playwright test --trace=on

# View traces
npx playwright show-trace test-results/trace.zip
```

### **3. Screenshots and Videos**

```bash
# Always capture screenshots
npx playwright test --screenshot=on

# Record videos for failures
npx playwright test --video=retain-on-failure
```

### **4. Console Logging**

```typescript
// Add debug logging in tests
test('debug example', async ({ page }) => {
  page.on('console', msg => console.log('Browser:', msg.text()));
  page.on('pageerror', error => console.log('Page error:', error));
  
  // Add custom logging
  await page.evaluate(() => {
    console.log('Current URL:', window.location.href);
    console.log('Local storage:', localStorage);
  });
});
```

---

## 📊 **Performance Debugging**

### **Slow Test Execution**

**Check System Resources**:
```bash
# Monitor CPU and memory usage
Get-Process | Where-Object {$_.ProcessName -like "*node*" -or $_.ProcessName -like "*chrome*"}
```

**Optimize Test Configuration**:
```typescript
// Reduce parallel workers for slower systems
// In playwright.config.ts
workers: process.env.CI ? 2 : 1,

// Increase timeouts for slower systems
timeout: 60000,
```

**Network Optimization**:
```typescript
// Disable unnecessary resources
await page.route('**/*.{png,jpg,jpeg,svg}', route => {
  if (!route.request().url().includes('album-cover')) {
    route.abort();
  } else {
    route.continue();
  }
});
```

---

## 🏥 **Health Checks**

### **Pre-Test Validation**

```bash
# Check if all dependencies are installed
npm list @playwright/test

# Verify server can start
npm run dev &
curl http://localhost:5173 || echo "Server not accessible"

# Test browser installation
npx playwright install --dry-run
```

### **Environment Validation**

```typescript
// Add to test setup
test('environment health check', async ({ page }) => {
  // Check if server is responsive
  const response = await page.goto('http://localhost:5173');
  expect(response?.status()).toBe(200);
  
  // Verify required elements exist
  await expect(page.locator('#app')).toBeVisible();
  
  // Check for JavaScript errors
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.waitForTimeout(1000);
  expect(errors).toEqual([]);
});
```

---

## 📞 **Getting Help**

### **Error Reporting Template**

When reporting issues, include:

```
**Environment:**
- OS: Windows 10/11
- Node.js version: `node --version`
- npm version: `npm --version`
- Playwright version: `npx playwright --version`

**Issue:**
- What were you trying to do?
- What command did you run?
- What error occurred?

**Error Output:**
```
[Paste full error message here]
```

**Steps to Reproduce:**
1. Step 1
2. Step 2
3. Step 3

**Additional Context:**
- Screenshots if UI-related
- Console output
- Network tab information
```

### **Useful Resources**

- 📖 [Playwright Documentation](https://playwright.dev/)
- 🐛 [Vue.js Testing Guide](https://vuejs.org/guide/scaling-up/testing.html)
- 💬 [Project README](../../../README.md)
- 🔍 [Test Scenarios Documentation](./test-scenarios.md)

Remember: Most issues are environment-related. Start with the basics: ensure the server is running, ports are available, and browsers are installed.