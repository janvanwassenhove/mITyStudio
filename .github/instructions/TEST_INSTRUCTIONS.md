# 🧪 Playwright Test Generation Guidelines

These instructions tell GitHub Copilot (and developers) how to create Playwright end-to-end (E2E) tests for this project.

---

## 🧩 Project Context

- **Frontend:** Vue 3 app using Vite (`frontend/src/…`)
- **Backend:** Python BCE exposing REST APIs (FastAPI/Flask)
- **Goal:** Write Playwright tests that simulate real user scenarios across the full stack.
- **Base URL:** `http://localhost:5173`
- **API URL:** `http://localhost:8000`

---

## 🗂 Folder Structure for Tests

```
frontend/
└── tests/
    ├── e2e/            # User-level scenario tests
    ├── fixtures/       # Shared setup utilities (e.g. login)
    ├── helpers/        # UI/API helper functions
    └── docs/           # scenario documentation
```

Each `.spec.ts` file represents **one user scenario** (e.g., `login.spec.ts`, `update-profile.spec.ts`).

---

## ✍️ Test Generation Rules

1. **Describe user behavior**, not technical details.  
   Example: “user can log in successfully”, not “button click works”.

2. **Selectors:**  
   Use `data-testid` attributes for stability.  
   Example:  
   ```html
   <button data-testid="login-button">Login</button>
   ```

3. **Structure every test as:**
   ```ts
   import { test, expect } from '@playwright/test';
   import { login } from '../helpers/ui-actions';

   test.describe('Feature: <feature name>', () => {
     test('Scenario: <describe user goal>', async ({ page }) => {
       // 🎬 Setup
       await page.goto('/');

       // 🎭 Actions
       // e.g. await login(page, 'jan', 'password123');

       // 🎯 Assertions
       // e.g. await expect(page.getByText('Welcome Jan')).toBeVisible();
     });
   });
   ```

4. **Avoid fragile waits.**  
   Use `await expect(...).toBeVisible()` instead of `waitForTimeout`.

5. **Reuse helpers & fixtures** instead of repeating login, navigation, or mock data.

---

## 🧱 Playwright Configuration (reference)

```ts
// frontend/tests/playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  webServer: [
    { command: 'npm run dev', port: 5173, reuseExistingServer: true },
    { command: 'python ../backend/main.py', port: 8000, reuseExistingServer: true },
  ],
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
});
```

---

## 🧠 Scenario Documentation

Maintain a living file at `frontend/tests/docs/scenarios.md` listing all user flows:
```markdown
## Auth
- [x] User can log in successfully
- [ ] Invalid login shows error message
- [ ] User can log out
```

---

## ⚙️ Commands

Local run:
```bash
npm run test:e2e
```

Interactive (debug UI):
```bash
npm run test:e2e:ui
```

Headed (visible browser):
```bash
npm run test:e2e:headed
```

---

## ✅ Copilot Generation Prompts

When generating a test:
- Follow this file’s conventions.
- Include comments for **Scenario / Preconditions / Steps / Expected Result**.
- Only use `data-testid` selectors.
- Place new tests under `frontend/tests/e2e/<feature>/`.
- Use helper imports where possible.
- Keep one scenario per `.spec.ts` file.

**Example prompt:**
> Generate a Playwright test following `.github/instructions/TEST_INSTRUCTIONS.md` for scenario:  
> “User updates profile information and sees a success message.”

---

## 🔍 Review Checklist

Before committing a generated test:
- [ ] Uses `data-testid` selectors  
- [ ] Clear scenario title  
- [ ] No hardcoded waits  
- [ ] Reuses helpers/fixtures  
- [ ] Added entry in `scenarios.md`  

---

_This file is read automatically by GitHub Copilot and other assistants to standardize test generation for Playwright._
