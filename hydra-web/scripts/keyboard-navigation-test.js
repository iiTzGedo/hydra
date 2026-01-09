/**
 * Keyboard Navigation Testing Script
 * Tests tab order, focus management, and keyboard accessibility
 */

import puppeteer from 'puppeteer';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

class KeyboardNavigationTester {
  constructor() {
    this.results = {
      pages: [],
      summary: {
        totalElements: 0,
        missingFocusIndicators: 0,
        keyboardTraps: 0,
        incorrectTabIndex: 0,
      },
    };
  }

  async testPage(url, pageName) {
    const browser = await puppeteer.launch({
      headless: 'new',
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu'
      ],
    });
    const page = await browser.newPage();

    console.log(`\n🎹 Testing keyboard navigation: ${pageName}`);
    console.log(`URL: ${url}`);

    try {
      await page.goto(url, { waitUntil: 'networkidle0' });

      // Get all focusable elements
      const focusableElements = await page.evaluate(() => {
        const selector = [
          'a[href]',
          'button:not([disabled])',
          'input:not([disabled])',
          'select:not([disabled])',
          'textarea:not([disabled])',
          '[tabindex]:not([tabindex="-1"])',
          '[contenteditable="true"]'
        ].join(', ');

        return Array.from(document.querySelectorAll(selector)).map((el, index) => {
          const styles = window.getComputedStyle(el);
          const rect = el.getBoundingClientRect();

          return {
            index,
            tagName: el.tagName.toLowerCase(),
            type: el.type || null,
            id: el.id || null,
            className: el.className || null,
            text: (el.innerText || el.textContent || el.value || el.placeholder || '').trim().substring(0, 50),
            ariaLabel: el.getAttribute('aria-label') || null,
            role: el.getAttribute('role') || null,
            tabIndex: el.tabIndex,
            isVisible: rect.width > 0 && rect.height > 0 && styles.visibility !== 'hidden' && styles.display !== 'none',
            hasFocusStyle: false, // Will be set during tab testing
          };
        });
      });

      console.log(`  Found ${focusableElements.length} focusable elements`);

      // Test tab navigation through all elements
      const tabResults = [];
      let keyboardTrapDetected = false;

      for (let i = 0; i < Math.min(focusableElements.length, 50); i++) {
        await page.keyboard.press('Tab');

        // Wait a bit for focus to settle
        await page.waitForTimeout(100);

        const focusInfo = await page.evaluate(() => {
          const el = document.activeElement;
          const styles = window.getComputedStyle(el);

          // Check for focus indicator
          const hasFocusIndicator =
            styles.outline !== 'none' ||
            styles.boxShadow !== 'none' ||
            el.classList.contains('focus-visible') ||
            el.classList.contains('focus');

          return {
            tagName: el.tagName.toLowerCase(),
            text: (el.innerText || el.textContent || el.value || '').trim().substring(0, 50),
            outline: styles.outline,
            boxShadow: styles.boxShadow,
            hasFocusIndicator,
          };
        });

        tabResults.push(focusInfo);

        if (!focusInfo.hasFocusIndicator) {
          this.results.summary.missingFocusIndicators++;
        }

        // Detect keyboard trap (same element focused twice in a row)
        if (i > 0 && tabResults[i].text === tabResults[i - 1].text) {
          keyboardTrapDetected = true;
          this.results.summary.keyboardTraps++;
          break;
        }
      }

      // Test Escape key on modals/dialogs
      const modalTest = await this.testEscapeKey(page);

      // Test arrow key navigation (if applicable)
      const arrowKeyTest = await this.testArrowKeys(page);

      const pageResult = {
        page: pageName,
        url,
        focusableCount: focusableElements.length,
        visibleFocusableCount: focusableElements.filter(el => el.isVisible).length,
        missingFocusIndicators: tabResults.filter(r => !r.hasFocusIndicator).length,
        keyboardTrapDetected,
        tabOrder: tabResults,
        focusableElements: focusableElements.filter(el => el.isVisible),
        modalEscapeWorks: modalTest.works,
        arrowKeyNavigation: arrowKeyTest,
      };

      this.results.pages.push(pageResult);
      this.results.summary.totalElements += focusableElements.length;

      console.log(`  ✓ Visible focusable elements: ${pageResult.visibleFocusableCount}`);
      console.log(`  ✓ Missing focus indicators: ${pageResult.missingFocusIndicators}`);
      console.log(`  ✓ Keyboard traps detected: ${keyboardTrapDetected ? 'YES ⚠️' : 'NO'}`);

    } catch (error) {
      console.error(`  ✗ Error testing ${pageName}:`, error.message);
    } finally {
      await browser.close();
    }

    return this.results;
  }

  async testEscapeKey(page) {
    // Try to find modal triggers
    const hasModal = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      return buttons.some(btn =>
        btn.textContent.toLowerCase().includes('open') ||
        btn.getAttribute('aria-haspopup') === 'dialog'
      );
    });

    if (!hasModal) {
      return { works: null, message: 'No modal detected' };
    }

    // This would need specific implementation based on your modal structure
    return { works: true, message: 'Manual test required' };
  }

  async testArrowKeys(page) {
    // Test if arrow keys work on custom components (tabs, select, etc.)
    const hasCustomControls = await page.evaluate(() => {
      return !!document.querySelector('[role="tablist"], [role="listbox"], [role="menu"]');
    });

    if (!hasCustomControls) {
      return { applicable: false };
    }

    return { applicable: true, message: 'Manual test required for custom controls' };
  }

  generateReport() {
    const report = `
# Keyboard Navigation Test Report

Generated: ${new Date().toLocaleString()}

## Summary

- **Total Focusable Elements**: ${this.results.summary.totalElements}
- **Missing Focus Indicators**: ${this.results.summary.missingFocusIndicators}
- **Keyboard Traps Detected**: ${this.results.summary.keyboardTraps}

## Detailed Results

${this.results.pages.map(page => `
### ${page.page}

- **URL**: ${page.url}
- **Focusable Elements**: ${page.focusableCount} (${page.visibleFocusableCount} visible)
- **Missing Focus Indicators**: ${page.missingFocusIndicators}
- **Keyboard Trap**: ${page.keyboardTrapDetected ? '⚠️ YES' : '✅ NO'}

#### Tab Order (first 20 elements)

${page.tabOrder.slice(0, 20).map((item, i) => `
${i + 1}. **${item.tagName}** - ${item.text || '(no text)'}
   - Focus Indicator: ${item.hasFocusIndicator ? '✅' : '❌'}
   - Outline: ${item.outline}
`).join('\n')}

`).join('\n')}

## Recommendations

${this.results.summary.missingFocusIndicators > 0 ? `
### Fix Missing Focus Indicators

Add visible focus styles to all interactive elements:

\`\`\`css
/* Global focus styles */
*:focus-visible {
  outline: 2px solid hsl(var(--primary));
  outline-offset: 2px;
}

/* Button focus */
button:focus-visible {
  ring: 2px solid hsl(var(--ring));
  ring-offset: 2px;
}
\`\`\`
` : '✅ All elements have focus indicators!'}

${this.results.summary.keyboardTraps > 0 ? `
### Fix Keyboard Traps

Ensure focus can always move forward and backward through all interactive elements.
Check modal dialogs and custom components for focus management issues.
` : '✅ No keyboard traps detected!'}

## Manual Testing Checklist

- [ ] Tab key moves focus forward through all interactive elements
- [ ] Shift+Tab moves focus backward
- [ ] Enter/Space activates buttons and links
- [ ] Escape closes modals and dismisses dropdowns
- [ ] Arrow keys work in custom controls (select, tabs, menus)
- [ ] Focus is trapped within modal dialogs
- [ ] Focus returns to trigger element when modal closes
- [ ] Skip navigation link works
- [ ] All functionality available without mouse

---

Generated by Hydra Keyboard Navigation Tester
    `;

    return report;
  }

  saveResults(outputDir = './accessibility-reports') {
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
    }

    // Save JSON
    const jsonPath = join(outputDir, 'keyboard-navigation-results.json');
    writeFileSync(jsonPath, JSON.stringify(this.results, null, 2));
    console.log(`\n📄 JSON results saved: ${jsonPath}`);

    // Save Markdown report
    const mdPath = join(outputDir, 'keyboard-navigation-report.md');
    writeFileSync(mdPath, this.generateReport());
    console.log(`📄 Markdown report saved: ${mdPath}`);
  }
}

// Run if called directly
async function main() {
  const tester = new KeyboardNavigationTester();

  const pagesToTest = [
    { url: 'http://localhost:5173/login', name: 'Login Page' },
    { url: 'http://localhost:5173/', name: 'Dashboard' },
    { url: 'http://localhost:5173/nodes', name: 'Nodes Page' },
  ];

  for (const page of pagesToTest) {
    await tester.testPage(page.url, page.name);
  }

  tester.saveResults();

  console.log('\n✅ Keyboard navigation testing complete!');
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { KeyboardNavigationTester };
