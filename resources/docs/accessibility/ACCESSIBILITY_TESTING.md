# Accessibility Testing Guide

Complete guide to running and interpreting accessibility tests for the Hydra web application.

---

## Quick Start

```bash
# 1. Install dependencies (includes Puppeteer, axe-core, etc.)
npm install

# 2. Start the development server
npm run dev

# 3. In another terminal, run all accessibility tests
npm run a11y:all
```

Reports will be generated in `./accessibility-reports/`

---

## Available Commands

### Run All Tests
```bash
npm run a11y:all
```
Runs all accessibility test suites in sequence. This is the recommended command for comprehensive testing.

### Individual Test Suites

#### 1. Full Accessibility Audit (axe-core)
```bash
npm run a11y:audit
```

**What it does:**
- Runs axe-core accessibility engine on all pages
- Checks WCAG 2.2 Level AA compliance
- Tests across multiple viewports (mobile, tablet, desktop)
- Captures screenshots of pages with violations

**Output:**
- `accessibility-reports/accessibility-report.json` - Detailed JSON results
- `accessibility-reports/accessibility-report.html` - Interactive HTML report
- `accessibility-reports/screenshots/` - Screenshots of flagged pages

**Typical runtime:** 2-5 minutes (depending on number of pages)

#### 2. Keyboard Navigation Testing
```bash
npm run a11y:keyboard
```

**What it does:**
- Tests tab order through all interactive elements
- Checks for visible focus indicators
- Detects keyboard traps
- Validates logical tab flow

**Output:**
- `accessibility-reports/keyboard-navigation-results.json`
- `accessibility-reports/keyboard-navigation-report.md`

**Typical runtime:** 1-2 minutes

#### 3. Color Contrast Analysis
```bash
npm run a11y:contrast
```

**What it does:**
- Analyzes all text elements for color contrast
- Validates against WCAG AA (4.5:1) and AAA (7:1) standards
- Distinguishes between normal and large text
- Identifies failing color combinations

**Output:**
- `accessibility-reports/color-contrast-results.json`
- `accessibility-reports/color-contrast-report.html`
- `accessibility-reports/color-contrast-report.md`

**Typical runtime:** 1-2 minutes

#### 4. ARIA & Semantic HTML Audit
```bash
npm run a11y:aria
```

**What it does:**
- Validates ARIA attributes and roles
- Checks heading hierarchy
- Verifies landmark regions
- Audits form labels and accessible names

**Output:**
- `accessibility-reports/aria-semantic-results.json`
- `accessibility-reports/aria-semantic-report.md`

**Typical runtime:** 1-2 minutes

---

## Understanding Reports

### HTML Report (Main Accessibility Audit)

The HTML report (`accessibility-report.html`) provides:

1. **Summary Dashboard**
   - Overall accessibility score (0-100)
   - Total violation count
   - Breakdown by severity (critical, serious, moderate, minor)

2. **Page-by-Page Results**
   - Score for each page
   - List of violations with:
     - Impact level
     - Number of instances
     - Description and help text
     - Link to documentation

3. **Violation Details**
   - Specific HTML elements affected
   - WCAG success criteria violated
   - Remediation guidance

### JSON Reports

All test suites generate JSON output for:
- CI/CD integration
- Custom reporting
- Historical comparison
- Programmatic analysis

### Markdown Reports

Markdown reports provide:
- Human-readable summaries
- Remediation guides
- Best practices
- Code examples

---

## Interpreting Scores

### Overall Accessibility Score

| Score | Rating | Action |
|-------|--------|--------|
| 90-100 | Excellent | Minor improvements only |
| 70-89 | Good | Address moderate issues |
| 50-69 | Fair | Significant work needed |
| < 50 | Poor | Major accessibility gaps |

**Target**: ≥ 90 for production deployment

### Violation Severity Levels

#### Critical
- **Impact**: Blocks access for users with disabilities
- **Examples**: Missing alt text, form inputs without labels, keyboard traps
- **Action**: Fix immediately before deployment

#### Serious
- **Impact**: Significantly hampers accessibility
- **Examples**: Insufficient color contrast, improper ARIA usage
- **Action**: Fix before release

#### Moderate
- **Impact**: Some difficulty for users with disabilities
- **Examples**: Skipped heading levels, missing landmark labels
- **Action**: Plan to fix in next sprint

#### Minor
- **Impact**: Minimal impact, best practice violation
- **Examples**: Missing descriptive text, suboptimal ARIA
- **Action**: Address when time permits

---

## Configuration

### Test Configuration

Edit `accessibility-audit.config.js` to customize:

```javascript
export const auditConfig = {
  // WCAG compliance level
  wcagLevel: 'AA', // or 'AAA'
  wcagVersion: '2.2',

  // Pages to test
  pages: [
    { name: 'Login', path: '/login', priority: 'high' },
    { name: 'Dashboard', path: '/', auth: true, priority: 'high' },
    // Add more pages...
  ],

  // Viewports to test
  viewports: [
    { name: 'Mobile', width: 375, height: 667 },
    { name: 'Tablet', width: 768, height: 1024 },
    { name: 'Desktop', width: 1920, height: 1080 },
  ],

  // Output settings
  output: {
    format: 'html',
    directory: './accessibility-reports',
    includeScreenshots: true,
  },
};
```

### Authentication

For testing authenticated pages:

1. Update test credentials in scripts
2. Or use registration tokens
3. Or mock authentication state

```javascript
// In accessibility-audit.js
async login(page) {
  await page.goto('http://localhost:5173/login');
  await page.type('#username', 'test-user');
  await page.type('#password', 'test-password');
  await page.click('button[type="submit"]');
  await page.waitForNavigation();
}
```

---

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/accessibility.yml`:

```yaml
name: Accessibility Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  accessibility:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
        cache: 'npm'

    - name: Install dependencies
      run: npm ci

    - name: Build application
      run: npm run build

    - name: Start application
      run: |
        npm run preview &
        npx wait-on http://localhost:5173

    - name: Run accessibility tests
      run: npm run a11y:all

    - name: Upload reports
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: accessibility-reports
        path: accessibility-reports/

    - name: Comment PR with results
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v6
      with:
        script: |
          const fs = require('fs');
          const results = JSON.parse(fs.readFileSync('accessibility-reports/accessibility-report.json', 'utf8'));
          const comment = `## Accessibility Test Results\n\n` +
            `**Score**: ${results.summary.overallScore}/100\n` +
            `**Violations**: ${results.summary.totalViolations}\n` +
            `- Critical: ${results.summary.criticalCount}\n` +
            `- Serious: ${results.summary.seriousCount}\n\n` +
            `[View detailed report](https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }})`;

          github.rest.issues.createComment({
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: comment
          });

    - name: Fail if score below threshold
      run: |
        SCORE=$(node -p "require('./accessibility-reports/accessibility-report.json').summary.overallScore")
        if [ "$SCORE" -lt 90 ]; then
          echo "Accessibility score ($SCORE) is below threshold (90)"
          exit 1
        fi
```

### Pre-commit Hook

Create `.husky/pre-commit`:

```bash
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"

# Run quick accessibility check on staged files
npm run lint
```

For more thorough checking, run tests in pre-push hook instead.

---

## Troubleshooting

### Tests Fail to Connect

**Problem**: `Error: Failed to connect to http://localhost:5173`

**Solution**:
1. Ensure dev server is running: `npm run dev`
2. Wait for server to be fully ready
3. Check port isn't already in use
4. Update URLs in test config if using different port

### Puppeteer Installation Issues

**Problem**: Puppeteer fails to install or Chrome binary missing

**Solution**:
```bash
# Linux
sudo apt-get install -y chromium-browser

# macOS
brew install chromium

# Or skip download and use existing Chrome
npm install puppeteer --ignore-scripts
```

Set executable path in test scripts:
```javascript
const browser = await puppeteer.launch({
  executablePath: '/path/to/chrome',
});
```

### Authentication Fails

**Problem**: Tests can't access authenticated pages

**Solution**:
1. Check test credentials are correct
2. Verify login flow hasn't changed
3. Use registration tokens instead of credentials
4. Mock authentication in test environment

### Reports Not Generated

**Problem**: Report directory is empty

**Solution**:
1. Check console for errors
2. Verify write permissions on directory
3. Ensure all tests completed (check exit codes)
4. Look for error logs in test output

---

## Manual Testing Checklist

While automated tests catch many issues, manual testing is essential for:

### Keyboard Navigation
- [ ] Tab through entire page
- [ ] Verify logical tab order
- [ ] Check focus indicators are visible
- [ ] Test all keyboard shortcuts
- [ ] Verify Escape closes modals

### Screen Reader Testing

**NVDA (Windows):**
```
1. Install NVDA (free)
2. Open app in Firefox
3. Start NVDA (Ctrl+Alt+N)
4. Navigate with arrow keys
5. Verify all content is announced
```

**VoiceOver (macOS):**
```
1. Enable in System Preferences
2. Open app in Safari
3. Start VoiceOver (Cmd+F5)
4. Navigate with VO keys
5. Verify all content is announced
```

### Browser Testing
- [ ] Chrome + NVDA/VoiceOver
- [ ] Firefox + NVDA
- [ ] Safari + VoiceOver
- [ ] Edge + JAWS (if available)

### Responsive Testing
- [ ] Mobile (320px - 480px)
- [ ] Tablet (768px - 1024px)
- [ ] Desktop (1280px+)
- [ ] Portrait and landscape orientations

---

## Best Practices

### 1. Test Early and Often
- Run automated tests during development
- Don't wait until the end to test
- Include accessibility in code review

### 2. Fix Issues Immediately
- Address violations as you find them
- Don't accumulate accessibility debt
- Prioritize by severity

### 3. Manual Testing is Essential
- Automated tests catch ~40% of issues
- Screen reader testing is irreplaceable
- Real user testing is invaluable

### 4. Document Exceptions
- If you can't fix an issue, document why
- Explain workarounds or alternatives
- Plan to address in future iterations

### 5. Continuous Improvement
- Set accessibility targets
- Track progress over time
- Celebrate improvements

---

## Resources

### Internal Documentation
- [Accessibility Checklist](./ACCESSIBILITY_CHECKLIST.md) - Manual testing guide
- [Audit Summary](./ACCESSIBILITY_AUDIT_SUMMARY.md) - Current state and recommendations
- Component docs - Accessibility notes per component

### External Resources
- [WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/)
- [axe-core Rule Descriptions](https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [WebAIM Articles](https://webaim.org/articles/)

### Tools
- [axe DevTools Browser Extension](https://www.deque.com/axe/devtools/)
- [WAVE Browser Extension](https://wave.webaim.org/extension/)
- [Lighthouse (built into Chrome DevTools)](https://developers.google.com/web/tools/lighthouse)

---

## Getting Help

- **Questions about test results?** Check the [Audit Summary](./ACCESSIBILITY_AUDIT_SUMMARY.md)
- **Need to understand a violation?** Click the "Learn more" link in reports
- **Screen reader testing?** See [Accessibility Checklist](./ACCESSIBILITY_CHECKLIST.md)
- **Tool issues?** Check the Troubleshooting section above

---

## Changelog

### 2026-01-09
- Initial accessibility testing setup
- Created automated test scripts
- Configured package.json scripts
- Generated documentation

---

**Maintained by**: Hydra Development Team
**Last updated**: 2026-01-09
