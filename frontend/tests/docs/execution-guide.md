# Test Execution Guide - Album Cover Dialog

## 🚀 **Quick Start**

### **1. Environment Setup**
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (if not done)
npm install

# Install Playwright browsers
npm run test:install
```

### **2. Start Development Server**
```bash
# Terminal 1 - Start frontend server
npm run dev
# Note the port (usually http://localhost:5173/)
```

### **3. Execute Tests**
```bash
# Terminal 2 - Run tests (basic)
npm run test:e2e

# Interactive mode
npm run test:e2e:ui

# Debug mode
npm run test:e2e:debug
```

---

## 📁 **Test Structure Overview**

```
tests/
├── e2e/                          # End-to-end tests
│   └── album-cover/              # Album cover feature tests
│       ├── smoke.spec.ts         # Quick validation tests
│       ├── integration.spec.ts   # Complete workflow tests
│       └── advanced.spec.ts      # Complex scenarios
├── utils/                        # Test utilities and helpers
│   ├── test-utils.ts            # Helper functions
│   └── page-objects.ts          # Page Object Models
├── fixtures/                     # Test data and fixtures
│   ├── test-data.json           # Static test data
│   └── mock-responses.json      # API mock responses
├── config/                       # Test configuration
│   ├── test-setup.ts            # Global test setup
│   └── environments.json        # Environment configs
└── docs/                         # Documentation
    ├── test-scenarios.md        # Detailed scenario docs
    ├── execution-guide.md       # This file
    └── troubleshooting.md       # Common issues guide
```

---

## 🎯 **Test Execution Strategies**

### **By Test Type**

#### **Smoke Tests** (Quick validation - ~30 seconds)
```bash
# Run only smoke tests
npx playwright test e2e/album-cover/smoke.spec.ts

# Run with visual feedback
npx playwright test e2e/album-cover/smoke.spec.ts --headed
```
**Purpose**: Validate basic functionality works
**When to run**: After each code change, before commits

#### **Integration Tests** (Complete workflows - ~2 minutes)
```bash
# Run integration tests
npx playwright test e2e/album-cover/integration.spec.ts

# Run with trace collection
npx playwright test e2e/album-cover/integration.spec.ts --trace=on
```
**Purpose**: Test complete user workflows
**When to run**: Before pull requests, daily CI

#### **Advanced Tests** (Complex scenarios - ~5 minutes)
```bash
# Run advanced tests
npx playwright test e2e/album-cover/advanced.spec.ts

# Run with full debugging
npx playwright test e2e/album-cover/advanced.spec.ts --debug
```
**Purpose**: Validate complex scenarios and edge cases
**When to run**: Weekly, before releases

### **By Browser**

#### **Single Browser Testing**
```bash
# Chrome only
npx playwright test --project=chromium

# Firefox only  
npx playwright test --project=firefox

# Safari only
npx playwright test --project=webkit
```

#### **Cross-Browser Testing**
```bash
# All desktop browsers
npx playwright test --project=chromium --project=firefox --project=webkit

# Mobile browsers
npx playwright test --project="Mobile Chrome" --project="Mobile Safari"
```

### **By Environment**

#### **Local Development**
```bash
# Use local config (assumes server running)
npx playwright test --config=playwright.config.local.ts
```

#### **CI/CD Pipeline**
```bash
# Use CI config (starts own server)
npx playwright test --config=playwright.config.ts
```

---

## 📊 **Test Reporting and Analysis**

### **HTML Reports**
```bash
# Generate and view HTML report
npx playwright show-report
```
**Includes**:
- Test results summary
- Screenshots of failures
- Video recordings
- Performance metrics
- Trace files for debugging

### **JSON Reports**
```bash
# Generate JSON report
npx playwright test --reporter=json --output-dir=test-results
```

### **Custom Reports**
```bash
# Multiple reporters
npx playwright test --reporter=html,json,junit
```

---

## 🔧 **Advanced Execution Options**

### **Parallel Execution**
```bash
# Run with specific number of workers
npx playwright test --workers=4

# Disable parallel execution
npx playwright test --workers=1
```

### **Test Filtering**
```bash
# Run tests by name pattern
npx playwright test --grep "dialog opens"

# Skip tests by pattern
npx playwright test --grep-invert "advanced"

# Run only failed tests from last run
npx playwright test --last-failed
```

### **Debugging Options**
```bash
# Step-by-step debugging
npx playwright test --debug

# Visual debugging with UI
npx playwright test --ui

# Headed mode (see browser)
npx playwright test --headed

# Slow motion execution
npx playwright test --headed --slow-mo=1000
```

### **Performance Testing**
```bash
# Collect traces for performance analysis
npx playwright test --trace=on

# Profile with timeline
npx playwright test --trace=retain-on-failure
```

---

## 🎪 **Interactive Testing**

### **Playwright UI Mode**
```bash
# Launch interactive test runner
npm run test:e2e:ui
```
**Features**:
- Visual test execution
- Real-time test editing  
- Step-by-step debugging
- Live browser preview
- Test result analysis

### **Codegen Mode**
```bash
# Generate test code interactively
npx playwright codegen http://localhost:5173
```
**Use cases**:
- Creating new test scenarios
- Exploring application behavior
- Generating selector queries

---

## 📱 **Mobile Testing**

### **Responsive Testing**
```bash
# Test mobile viewports
npx playwright test --project="Mobile Chrome"

# Custom viewport
npx playwright test --config=playwright.config.mobile.ts
```

### **Device Emulation**
```bash
# iPhone simulation
npx playwright test --device="iPhone 12"

# Android simulation  
npx playwright test --device="Pixel 5"
```

---

## 🔄 **Continuous Integration**

### **GitHub Actions Integration**
The repository includes `.github/workflows/e2e-tests.yml` for automated testing:

```yaml
# Triggered on:
- Push to main/dialog_album_image branches
- Pull requests to main
- Manual workflow dispatch

# Test matrix:
- Chrome, Firefox, Safari
- Desktop and Mobile
- Multiple Node.js versions
```

### **Local CI Simulation**
```bash
# Run tests as CI would
CI=true npx playwright test

# With retry logic
npx playwright test --retries=2
```

---

## 📈 **Performance Monitoring**

### **Performance Test Execution**
```bash
# Run with performance collection
npx playwright test --trace=on --video=retain-on-failure

# Custom performance config
npx playwright test --config=playwright.config.perf.ts
```

### **Metrics Collection**
- Dialog opening time
- Form interaction response time
- API request/response time
- Animation frame rates
- Memory usage patterns

---

## 🛡️ **Test Data Management**

### **Static Test Data**
```bash
# Tests use data from fixtures/test-data.json
npx playwright test --config=playwright.config.ts
```

### **Dynamic Test Data**
```bash
# Generate random test data
npx playwright test --grep "dynamic data"
```

### **API Mocking**
```bash
# Run with API mocks
npx playwright test --config=playwright.config.mock.ts
```

---

## 🎯 **Best Practices**

### **Before Running Tests**
1. ✅ Ensure frontend server is running
2. ✅ Verify no other tests are running
3. ✅ Check browser versions are up to date
4. ✅ Clear previous test artifacts

### **During Test Execution**
1. 🔍 Monitor test output for warnings
2. 📸 Check screenshots for visual regressions
3. ⏱️ Track execution times for performance issues
4. 🐛 Note any flaky test behavior

### **After Test Execution**
1. 📊 Review test reports
2. 🔧 Investigate any failures
3. 📝 Document issues found
4. 🔄 Update tests if needed

---

## 📞 **Support and Troubleshooting**

### **Common Commands**
```bash
# Clear test cache
npx playwright install --force

# Update browsers
npx playwright install

# Clear test results
rm -rf test-results playwright-report

# Reset test environment
npm run test:install && npx playwright install --deps
```

### **Getting Help**
- 📖 See `docs/troubleshooting.md` for common issues
- 🐛 Check existing test failures in reports
- 💬 Review test logs in `test-results/` directory
- 🔍 Use `--debug` flag for detailed investigation

This guide provides comprehensive instructions for executing Album Cover Dialog tests in various scenarios and environments.