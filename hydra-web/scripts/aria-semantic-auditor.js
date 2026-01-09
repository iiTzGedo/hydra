/**
 * ARIA and Semantic HTML Auditor
 * Checks for proper use of ARIA attributes and semantic HTML elements
 */

import puppeteer from 'puppeteer';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

class AriaSemanticAuditor {
  constructor() {
    this.results = {
      pages: [],
      summary: {
        totalIssues: 0,
        missingLabels: 0,
        improperHeadings: 0,
        missingLandmarks: 0,
        invalidAria: 0,
      },
    };
  }

  async auditPage(url, pageName) {
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

    console.log(`\n🏷️  Auditing ARIA & Semantics: ${pageName}`);
    console.log(`URL: ${url}`);

    try {
      await page.goto(url, { waitUntil: 'networkidle0' });

      const audit = await page.evaluate(() => {
        const results = {
          headings: [],
          landmarks: [],
          forms: [],
          images: [],
          buttons: [],
          links: [],
          ariaUsage: [],
          semanticIssues: [],
        };

        // 1. Audit Heading Structure
        const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'));
        let previousLevel = 0;
        const headingIssues = [];

        headings.forEach((heading, index) => {
          const level = parseInt(heading.tagName[1]);
          const text = heading.textContent.trim();

          results.headings.push({
            level,
            text: text.substring(0, 100),
            isEmpty: !text,
            hasId: !!heading.id,
          });

          // Check for skipped levels
          if (level > previousLevel + 1 && previousLevel !== 0) {
            headingIssues.push({
              type: 'skipped-level',
              message: `Heading level ${level} skips from level ${previousLevel}`,
              element: heading.outerHTML.substring(0, 100),
            });
          }

          // Check for empty headings
          if (!text) {
            headingIssues.push({
              type: 'empty-heading',
              message: 'Heading element has no text content',
              element: heading.outerHTML.substring(0, 100),
            });
          }

          previousLevel = level;
        });

        // Check for missing h1
        if (!headings.some(h => h.tagName === 'H1')) {
          headingIssues.push({
            type: 'missing-h1',
            message: 'Page is missing an h1 element',
          });
        }

        results.semanticIssues.push(...headingIssues);

        // 2. Audit Landmark Regions
        const landmarks = Array.from(document.querySelectorAll('[role="main"], [role="navigation"], [role="banner"], [role="contentinfo"], [role="complementary"], [role="search"], main, nav, header, footer, aside'));

        results.landmarks = landmarks.map(el => ({
          role: el.getAttribute('role') || el.tagName.toLowerCase(),
          hasLabel: !!(el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')),
        }));

        // Check for missing main landmark
        const hasMain = landmarks.some(l => l.getAttribute('role') === 'main' || l.tagName === 'MAIN');
        if (!hasMain) {
          results.semanticIssues.push({
            type: 'missing-main',
            message: 'Page is missing a main landmark',
          });
        }

        // 3. Audit Forms and Inputs
        const inputs = Array.from(document.querySelectorAll('input, textarea, select'));

        results.forms = inputs.map(input => {
          const id = input.id;
          const hasLabel = id && !!document.querySelector(`label[for="${id}"]`);
          const hasAriaLabel = !!input.getAttribute('aria-label');
          const hasAriaLabelledby = !!input.getAttribute('aria-labelledby');
          const inFieldset = !!input.closest('fieldset');

          const issue = !hasLabel && !hasAriaLabel && !hasAriaLabelledby && !inFieldset;

          if (issue) {
            results.semanticIssues.push({
              type: 'missing-label',
              message: `Input element missing accessible label`,
              element: input.outerHTML.substring(0, 150),
            });
          }

          return {
            type: input.type || input.tagName.toLowerCase(),
            id,
            hasLabel,
            hasAriaLabel,
            hasAriaLabelledby,
            hasAccessibleName: hasLabel || hasAriaLabel || hasAriaLabelledby || inFieldset,
          };
        });

        // 4. Audit Images
        const images = Array.from(document.querySelectorAll('img, svg'));

        results.images = images.map(img => {
          const alt = img.getAttribute('alt');
          const ariaLabel = img.getAttribute('aria-label');
          const role = img.getAttribute('role');
          const isDecorative = role === 'presentation' || role === 'none' || alt === '';

          const issue = !isDecorative && !alt && !ariaLabel;

          if (issue) {
            results.semanticIssues.push({
              type: 'missing-alt',
              message: `Image missing alt text`,
              element: img.outerHTML.substring(0, 150),
            });
          }

          return {
            tagName: img.tagName.toLowerCase(),
            hasAlt: alt !== null,
            altText: alt,
            hasAriaLabel: !!ariaLabel,
            isDecorative,
            hasAccessibleName: isDecorative || !!alt || !!ariaLabel,
          };
        });

        // 5. Audit Buttons
        const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));

        results.buttons = buttons.map(btn => {
          const text = btn.textContent.trim();
          const ariaLabel = btn.getAttribute('aria-label');
          const ariaLabelledby = btn.getAttribute('aria-labelledby');
          const hasAccessibleName = text || ariaLabel || ariaLabelledby;

          if (!hasAccessibleName) {
            results.semanticIssues.push({
              type: 'button-no-text',
              message: 'Button has no accessible name',
              element: btn.outerHTML.substring(0, 150),
            });
          }

          return {
            text: text.substring(0, 50),
            hasAriaLabel: !!ariaLabel,
            hasAriaLabelledby: !!ariaLabelledby,
            hasAccessibleName,
          };
        });

        // 6. Audit Links
        const links = Array.from(document.querySelectorAll('a[href]'));

        results.links = links.map(link => {
          const text = link.textContent.trim();
          const ariaLabel = link.getAttribute('aria-label');
          const title = link.getAttribute('title');
          const hasAccessibleName = text || ariaLabel || title;

          if (!hasAccessibleName) {
            results.semanticIssues.push({
              type: 'link-no-text',
              message: 'Link has no accessible name',
              element: link.outerHTML.substring(0, 150),
            });
          }

          return {
            href: link.getAttribute('href'),
            text: text.substring(0, 50),
            hasAriaLabel: !!ariaLabel,
            hasAccessibleName,
          };
        });

        // 7. Audit ARIA Usage
        const ariaElements = Array.from(document.querySelectorAll('[aria-label], [aria-labelledby], [aria-describedby], [role]'));

        results.ariaUsage = ariaElements.slice(0, 50).map(el => ({
          tagName: el.tagName.toLowerCase(),
          role: el.getAttribute('role'),
          ariaLabel: el.getAttribute('aria-label'),
          ariaLabelledby: el.getAttribute('aria-labelledby'),
          ariaDescribedby: el.getAttribute('aria-describedby'),
        }));

        // 8. Check for interactive elements
        const divButtons = Array.from(document.querySelectorAll('div[onclick], span[onclick]'));
        divButtons.forEach(el => {
          if (!el.getAttribute('role') && !el.getAttribute('tabindex')) {
            results.semanticIssues.push({
              type: 'non-semantic-interactive',
              message: `${el.tagName} used for interaction without proper role/tabindex`,
              element: el.outerHTML.substring(0, 150),
            });
          }
        });

        return results;
      });

      const pageResult = {
        page: pageName,
        url,
        ...audit,
        issueCount: audit.semanticIssues.length,
      };

      this.results.pages.push(pageResult);
      this.results.summary.totalIssues += audit.semanticIssues.length;

      // Count specific issue types
      audit.semanticIssues.forEach(issue => {
        if (issue.type === 'missing-label') this.results.summary.missingLabels++;
        if (issue.type.includes('heading') || issue.type === 'missing-h1') this.results.summary.improperHeadings++;
        if (issue.type === 'missing-main') this.results.summary.missingLandmarks++;
      });

      console.log(`  ✓ Headings: ${audit.headings.length}`);
      console.log(`  ✓ Landmarks: ${audit.landmarks.length}`);
      console.log(`  ✓ Form inputs: ${audit.forms.length}`);
      console.log(`  ✓ Images: ${audit.images.length}`);
      console.log(`  ✓ Issues found: ${audit.semanticIssues.length}`);

    } catch (error) {
      console.error(`  ✗ Error auditing ${pageName}:`, error.message);
    } finally {
      await browser.close();
    }

    return this.results;
  }

  generateReport() {
    const report = `
# ARIA and Semantic HTML Audit Report

Generated: ${new Date().toLocaleString()}

## Summary

- **Total Issues**: ${this.results.summary.totalIssues}
- **Missing Labels**: ${this.results.summary.missingLabels}
- **Heading Issues**: ${this.results.summary.improperHeadings}
- **Missing Landmarks**: ${this.results.summary.missingLandmarks}

## Detailed Results

${this.results.pages.map(page => `
### ${page.page}

**URL**: ${page.url}
**Issues Found**: ${page.issueCount}

#### Heading Structure

${page.headings.length > 0 ? `
| Level | Text | Empty | Has ID |
|-------|------|-------|--------|
${page.headings.map(h => `| h${h.level} | ${h.text} | ${h.isEmpty ? '⚠️ YES' : 'No'} | ${h.hasId ? 'Yes' : 'No'} |`).join('\n')}
` : 'No headings found on this page.'}

#### Landmarks

${page.landmarks.length > 0 ? `
| Role | Has Label |
|------|-----------|
${page.landmarks.map(l => `| ${l.role} | ${l.hasLabel ? 'Yes' : 'No'} |`).join('\n')}
` : '⚠️ No landmark regions found.'}

#### Form Inputs

${page.forms.length > 0 ? `
- Total inputs: ${page.forms.length}
- With labels: ${page.forms.filter(f => f.hasLabel).length}
- With aria-label: ${page.forms.filter(f => f.hasAriaLabel).length}
- Missing accessible names: ${page.forms.filter(f => !f.hasAccessibleName).length}
` : 'No form inputs found.'}

#### Images

${page.images.length > 0 ? `
- Total images: ${page.images.length}
- With alt text: ${page.images.filter(i => i.hasAlt).length}
- Decorative: ${page.images.filter(i => i.isDecorative).length}
- Missing alt text: ${page.images.filter(i => !i.hasAccessibleName).length}
` : 'No images found.'}

#### Buttons

${page.buttons.length > 0 ? `
- Total buttons: ${page.buttons.length}
- Missing accessible names: ${page.buttons.filter(b => !b.hasAccessibleName).length}
` : 'No buttons found.'}

#### Semantic Issues

${page.semanticIssues.length > 0 ? `
${page.semanticIssues.map((issue, i) => `
${i + 1}. **${issue.type}**: ${issue.message}
   ${issue.element ? `\n   \`\`\`html\n   ${issue.element}\n   \`\`\`` : ''}
`).join('\n')}
` : '✅ No semantic issues found!'}

`).join('\n')}

## Remediation Guide

### 1. Fix Missing Labels

All form inputs must have accessible labels:

\`\`\`html
<!-- ✅ Good: Label with for attribute -->
<label for="email">Email</label>
<input id="email" type="email" />

<!-- ✅ Good: Wrapping label -->
<label>
  Email
  <input type="email" />
</label>

<!-- ✅ Good: aria-label -->
<input type="search" aria-label="Search" placeholder="Search..." />

<!-- ❌ Bad: No label -->
<input type="email" placeholder="Email" />
\`\`\`

### 2. Fix Heading Structure

Headings should follow a logical hierarchy without skipping levels:

\`\`\`html
<!-- ✅ Good: Logical hierarchy -->
<h1>Page Title</h1>
<h2>Section Title</h2>
<h3>Subsection Title</h3>

<!-- ❌ Bad: Skipped level -->
<h1>Page Title</h1>
<h3>Section Title</h3> <!-- Missing h2 -->
\`\`\`

### 3. Add Landmark Regions

Use semantic HTML5 elements or ARIA landmarks:

\`\`\`html
<!-- ✅ Good: Semantic HTML5 -->
<header>
  <nav aria-label="Main navigation">...</nav>
</header>
<main>
  <h1>Page Content</h1>
</main>
<footer>...</footer>

<!-- ✅ Good: ARIA roles (fallback) -->
<div role="banner">...</div>
<div role="main">...</div>
<div role="contentinfo">...</div>
\`\`\`

### 4. Fix Image Alt Text

All informative images must have alt text:

\`\`\`html
<!-- ✅ Good: Descriptive alt -->
<img src="chart.png" alt="Sales increased by 25% in Q4" />

<!-- ✅ Good: Decorative (empty alt) -->
<img src="decoration.png" alt="" role="presentation" />

<!-- ✅ Good: SVG with title -->
<svg role="img" aria-labelledby="icon-title">
  <title id="icon-title">Home Icon</title>
  ...
</svg>

<!-- ❌ Bad: Missing alt -->
<img src="important.png" />
\`\`\`

### 5. Add Button Labels

All buttons must have accessible names:

\`\`\`html
<!-- ✅ Good: Text content -->
<button>Submit</button>

<!-- ✅ Good: Icon button with aria-label -->
<button aria-label="Close dialog">
  <CloseIcon />
</button>

<!-- ✅ Good: Icon button with visually hidden text -->
<button>
  <CloseIcon />
  <span className="sr-only">Close</span>
</button>

<!-- ❌ Bad: Icon only, no label -->
<button>
  <CloseIcon />
</button>
\`\`\`

### 6. Use Semantic HTML for Interactive Elements

\`\`\`html
<!-- ✅ Good: Use button element -->
<button onClick={handleClick}>Click me</button>

<!-- ❌ Bad: div as button without proper ARIA -->
<div onClick={handleClick}>Click me</div>

<!-- ⚠️ Acceptable: div as button WITH proper ARIA -->
<div role="button" tabIndex={0} onClick={handleClick} onKeyDown={handleKeyDown}>
  Click me
</div>
\`\`\`

## Testing Checklist

- [ ] Every page has exactly one h1
- [ ] Heading levels don't skip (h1 → h2 → h3, not h1 → h3)
- [ ] Main landmark region exists on every page
- [ ] All form inputs have labels
- [ ] All images have alt text or are marked decorative
- [ ] All buttons have accessible names
- [ ] No div/span elements used as buttons without proper ARIA
- [ ] Landmark regions have labels when there are multiple of the same type

---

Generated by Hydra ARIA & Semantic HTML Auditor
    `;

    return report;
  }

  saveResults(outputDir = './accessibility-reports') {
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
    }

    // Save JSON
    const jsonPath = join(outputDir, 'aria-semantic-results.json');
    writeFileSync(jsonPath, JSON.stringify(this.results, null, 2));
    console.log(`\n📄 JSON results saved: ${jsonPath}`);

    // Save Markdown report
    const mdPath = join(outputDir, 'aria-semantic-report.md');
    writeFileSync(mdPath, this.generateReport());
    console.log(`📄 Markdown report saved: ${mdPath}`);
  }
}

// Run if called directly
async function main() {
  const auditor = new AriaSemanticAuditor();

  const pagesToAudit = [
    { url: 'http://localhost:5173/login', name: 'Login Page' },
    { url: 'http://localhost:5173/', name: 'Dashboard' },
    { url: 'http://localhost:5173/nodes', name: 'Nodes Page' },
  ];

  for (const page of pagesToAudit) {
    await auditor.auditPage(page.url, page.name);
  }

  auditor.saveResults();

  console.log('\n✅ ARIA and semantic HTML audit complete!');
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { AriaSemanticAuditor };
