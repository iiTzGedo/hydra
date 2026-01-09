/**
 * Color Contrast Analyzer
 * Analyzes color contrast ratios for WCAG compliance
 */

import puppeteer from 'puppeteer';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

class ColorContrastAnalyzer {
  constructor() {
    this.wcagLevels = {
      AA: { normal: 4.5, large: 3.0 },
      AAA: { normal: 7.0, large: 4.5 },
    };
    this.results = {
      pages: [],
      summary: {
        totalChecks: 0,
        aaFailures: 0,
        aaaFailures: 0,
      },
    };
  }

  /**
   * Parse RGB color string to array
   */
  parseColor(colorString) {
    const match = colorString.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)/);
    if (!match) return [255, 255, 255]; // Default to white if parsing fails
    return [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
  }

  /**
   * Calculate relative luminance
   */
  relativeLuminance(rgb) {
    const [r, g, b] = rgb.map(val => {
      val = val / 255;
      return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  /**
   * Calculate contrast ratio
   */
  calculateContrast(fg, bg) {
    const l1 = this.relativeLuminance(this.parseColor(fg));
    const l2 = this.relativeLuminance(this.parseColor(bg));
    const lighter = Math.max(l1, l2);
    const darker = Math.min(l1, l2);
    return (lighter + 0.05) / (darker + 0.05);
  }

  /**
   * Check if text is considered "large" by WCAG standards
   */
  isLargeText(fontSize, fontWeight) {
    // Large text is 18pt (24px) or 14pt (18.66px) bold
    const isBold = parseInt(fontWeight) >= 700 || fontWeight === 'bold';
    return fontSize >= 24 || (fontSize >= 18.66 && isBold);
  }

  /**
   * Analyze page for color contrast issues
   */
  async analyzePage(url, pageName) {
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

    console.log(`\n🎨 Analyzing color contrast: ${pageName}`);
    console.log(`URL: ${url}`);

    try {
      await page.goto(url, { waitUntil: 'networkidle0' });

      const elements = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('*'))
          .filter(el => {
            const text = (el.innerText || el.textContent || '').trim();
            const rect = el.getBoundingClientRect();
            const styles = window.getComputedStyle(el);

            // Only check visible text elements
            return (
              text.length > 0 &&
              rect.width > 0 &&
              rect.height > 0 &&
              styles.visibility !== 'hidden' &&
              styles.display !== 'none'
            );
          })
          .map(el => {
            const styles = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();

            return {
              text: (el.innerText || el.textContent || '').trim().substring(0, 100),
              selector: el.tagName.toLowerCase() + (el.id ? `#${el.id}` : '') + (el.className ? `.${el.className.split(' ')[0]}` : ''),
              color: styles.color,
              backgroundColor: styles.backgroundColor,
              fontSize: parseFloat(styles.fontSize),
              fontWeight: styles.fontWeight,
              position: {
                top: Math.round(rect.top),
                left: Math.round(rect.left),
              },
            };
          });
      });

      console.log(`  Analyzing ${elements.length} text elements...`);

      const failures = [];
      let aaPass = 0;
      let aaaPass = 0;

      elements.forEach(el => {
        const contrast = this.calculateContrast(el.color, el.backgroundColor);
        const isLarge = this.isLargeText(el.fontSize, el.fontWeight);

        const aaRequired = isLarge ? this.wcagLevels.AA.large : this.wcagLevels.AA.normal;
        const aaaRequired = isLarge ? this.wcagLevels.AAA.large : this.wcagLevels.AAA.normal;

        const aaCompliant = contrast >= aaRequired;
        const aaaCompliant = contrast >= aaaRequired;

        if (aaCompliant) aaPass++;
        if (aaaCompliant) aaaPass++;

        if (!aaCompliant) {
          failures.push({
            text: el.text,
            selector: el.selector,
            currentContrast: contrast.toFixed(2),
            requiredAA: aaRequired,
            requiredAAA: aaaRequired,
            foreground: el.color,
            background: el.backgroundColor,
            fontSize: el.fontSize,
            isLarge,
            aaCompliant,
            aaaCompliant,
            severity: contrast < aaRequired ? 'critical' : 'moderate',
          });
        }
      });

      const pageResult = {
        page: pageName,
        url,
        totalElements: elements.length,
        aaPass,
        aaaPass,
        aaFailures: failures.filter(f => !f.aaCompliant).length,
        aaaFailures: failures.filter(f => !f.aaaCompliant).length,
        failures: failures.sort((a, b) => parseFloat(a.currentContrast) - parseFloat(b.currentContrast)),
      };

      this.results.pages.push(pageResult);
      this.results.summary.totalChecks += elements.length;
      this.results.summary.aaFailures += pageResult.aaFailures;
      this.results.summary.aaaFailures += pageResult.aaaFailures;

      console.log(`  ✓ WCAG AA Pass: ${aaPass}/${elements.length} (${((aaPass / elements.length) * 100).toFixed(1)}%)`);
      console.log(`  ✓ WCAG AAA Pass: ${aaaPass}/${elements.length} (${((aaaPass / elements.length) * 100).toFixed(1)}%)`);
      console.log(`  ✓ Failures: ${pageResult.aaFailures} critical`);

    } catch (error) {
      console.error(`  ✗ Error analyzing ${pageName}:`, error.message);
    } finally {
      await browser.close();
    }

    return this.results;
  }

  generateReport() {
    const aaPassRate = ((this.results.summary.totalChecks - this.results.summary.aaFailures) / this.results.summary.totalChecks * 100).toFixed(1);

    const report = `
# Color Contrast Analysis Report

Generated: ${new Date().toLocaleString()}

## Summary

- **Total Elements Checked**: ${this.results.summary.totalChecks}
- **WCAG AA Failures**: ${this.results.summary.aaFailures} (${(100 - parseFloat(aaPassRate)).toFixed(1)}%)
- **WCAG AAA Failures**: ${this.results.summary.aaaFailures}
- **WCAG AA Pass Rate**: ${aaPassRate}%

## WCAG Contrast Requirements

| Text Size | WCAG AA | WCAG AAA |
|-----------|---------|----------|
| Normal text | 4.5:1 | 7:1 |
| Large text (18pt+/14pt bold+) | 3:1 | 4.5:1 |

## Detailed Results

${this.results.pages.map(page => `
### ${page.page}

- **Total Elements**: ${page.totalElements}
- **WCAG AA Pass**: ${page.aaPass}/${page.totalElements} (${((page.aaPass / page.totalElements) * 100).toFixed(1)}%)
- **WCAG AAA Pass**: ${page.aaaPass}/${page.totalElements} (${((page.aaaPass / page.totalElements) * 100).toFixed(1)}%)
- **Failures**: ${page.aaFailures}

${page.failures.length > 0 ? `
#### Contrast Failures

${page.failures.slice(0, 20).map((failure, i) => `
${i + 1}. **${failure.text}** (${failure.selector})
   - Current Contrast: **${failure.currentContrast}:1** ${failure.aaCompliant ? '✅' : '❌'}
   - Required (AA): ${failure.requiredAA}:1
   - Required (AAA): ${failure.requiredAAA}:1
   - Foreground: \`${failure.foreground}\`
   - Background: \`${failure.background}\`
   - Font Size: ${failure.fontSize}px ${failure.isLarge ? '(large)' : '(normal)'}
   - Severity: ${failure.severity === 'critical' ? '🔴 Critical' : '🟡 Moderate'}
`).join('\n')}

${page.failures.length > 20 ? `\n_... and ${page.failures.length - 20} more failures_\n` : ''}
` : '✅ No contrast failures!'}

`).join('\n')}

## Remediation Guide

### Quick Fixes for Common Issues

1. **Insufficient text contrast**
   \`\`\`css
   /* Increase text color darkness or background lightness */
   .text-muted {
     color: hsl(var(--foreground) / 0.7); /* Instead of 0.5 */
   }
   \`\`\`

2. **Button text contrast**
   \`\`\`css
   .button-primary {
     background-color: #2563eb; /* Darker blue */
     color: #ffffff; /* White text */
   }
   \`\`\`

3. **Link contrast**
   \`\`\`css
   a {
     color: #0066cc; /* Darker blue for better contrast */
   }
   a:hover {
     color: #004499; /* Even darker on hover */
   }
   \`\`\`

### Tools for Testing

- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- [Colour Contrast Analyzer](https://www.tpgi.com/color-contrast-checker/)
- Browser DevTools > Accessibility > Contrast

### Testing in Different Modes

\`\`\`css
/* Test high contrast mode */
@media (prefers-contrast: high) {
  :root {
    --text-primary: #000;
    --bg-primary: #fff;
  }
}

/* Test dark mode */
@media (prefers-color-scheme: dark) {
  /* Ensure sufficient contrast in dark mode too */
}
\`\`\`

---

Generated by Hydra Color Contrast Analyzer
    `;

    return report;
  }

  generateHTMLReport() {
    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Color Contrast Analysis Report</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 20px;
            background: #f5f5f5;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: white;
            padding: 24px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .summary-card h3 { font-size: 14px; color: #666; margin-bottom: 8px; }
        .summary-card .value { font-size: 32px; font-weight: bold; color: #1f2937; }
        .failure-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #ef4444;
        }
        .failure-card.critical { border-left-color: #dc2626; }
        .failure-card.moderate { border-left-color: #f59e0b; }
        .color-swatch {
            display: inline-block;
            width: 30px;
            height: 30px;
            border-radius: 4px;
            border: 1px solid #ddd;
            vertical-align: middle;
            margin-right: 8px;
        }
        .contrast-value {
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }
        .pass { color: #10b981; }
        .fail { color: #ef4444; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎨 Color Contrast Analysis Report</h1>
            <p>Generated on ${new Date().toLocaleString()}</p>
        </div>

        <div class="summary">
            <div class="summary-card">
                <h3>Total Checks</h3>
                <div class="value">${this.results.summary.totalChecks}</div>
            </div>
            <div class="summary-card">
                <h3>AA Failures</h3>
                <div class="value">${this.results.summary.aaFailures}</div>
            </div>
            <div class="summary-card">
                <h3>AAA Failures</h3>
                <div class="value">${this.results.summary.aaaFailures}</div>
            </div>
        </div>

        ${this.results.pages.map(page => `
            <div style="background: white; padding: 30px; border-radius: 8px; margin-bottom: 30px;">
                <h2>${page.page}</h2>
                <p style="color: #666; margin-bottom: 20px;">${page.url}</p>

                ${page.failures.slice(0, 10).map(failure => `
                    <div class="failure-card ${failure.severity}">
                        <div>
                            <strong>${failure.text.substring(0, 100)}</strong>
                            <div style="color: #666; font-size: 14px; margin-top: 5px;">${failure.selector}</div>
                        </div>
                        <div class="contrast-value ${failure.aaCompliant ? 'pass' : 'fail'}">
                            ${failure.currentContrast}:1
                        </div>
                        <div>
                            <span class="color-swatch" style="background: ${failure.foreground};"></span>
                            <code>${failure.foreground}</code>
                            on
                            <span class="color-swatch" style="background: ${failure.background};"></span>
                            <code>${failure.background}</code>
                        </div>
                        <div style="margin-top: 10px; font-size: 14px; color: #666;">
                            Required: ${failure.requiredAA}:1 (AA) / ${failure.requiredAAA}:1 (AAA)
                        </div>
                    </div>
                `).join('')}
            </div>
        `).join('')}
    </div>
</body>
</html>
    `;

    return html;
  }

  saveResults(outputDir = './accessibility-reports') {
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
    }

    // Save JSON
    const jsonPath = join(outputDir, 'color-contrast-results.json');
    writeFileSync(jsonPath, JSON.stringify(this.results, null, 2));
    console.log(`\n📄 JSON results saved: ${jsonPath}`);

    // Save Markdown report
    const mdPath = join(outputDir, 'color-contrast-report.md');
    writeFileSync(mdPath, this.generateReport());
    console.log(`📄 Markdown report saved: ${mdPath}`);

    // Save HTML report
    const htmlPath = join(outputDir, 'color-contrast-report.html');
    writeFileSync(htmlPath, this.generateHTMLReport());
    console.log(`📄 HTML report saved: ${htmlPath}`);
  }
}

// Run if called directly
async function main() {
  const analyzer = new ColorContrastAnalyzer();

  const pagesToAnalyze = [
    { url: 'http://localhost:5173/login', name: 'Login Page' },
    { url: 'http://localhost:5173/', name: 'Dashboard' },
  ];

  for (const page of pagesToAnalyze) {
    await analyzer.analyzePage(page.url, page.name);
  }

  analyzer.saveResults();

  console.log('\n✅ Color contrast analysis complete!');
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { ColorContrastAnalyzer };
