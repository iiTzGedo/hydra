/**
 * Comprehensive Accessibility Audit Script
 * Runs automated accessibility tests using axe-core and Puppeteer
 */

import puppeteer from 'puppeteer';
import { AxePuppeteer } from '@axe-core/puppeteer';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';
import { auditConfig } from '../accessibility-audit.config.js';

class AccessibilityAuditor {
  constructor(config) {
    this.config = config;
    this.results = {
      summary: {
        totalPages: 0,
        totalViolations: 0,
        criticalCount: 0,
        seriousCount: 0,
        moderateCount: 0,
        minorCount: 0,
        overallScore: 0,
        timestamp: new Date().toISOString(),
      },
      pages: [],
    };
    this.browser = null;
  }

  async init() {
    this.browser = await puppeteer.launch({
      headless: 'new',
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--disable-gpu',
        '--window-size=1920,1080'
      ],
      ignoreHTTPSErrors: true,
    });
  }

  async close() {
    if (this.browser) {
      await this.browser.close();
    }
  }

  async login(page) {
    console.log('  → Logging in...');
    await page.goto('http://localhost:5173/login', { waitUntil: 'networkidle0' });

    // Fill login form
    await page.type('#username', 'admin');
    await page.type('#password', 'admin'); // Replace with actual test credentials

    // Submit form
    await page.click('button[type="submit"]');

    // Wait for navigation
    await page.waitForNavigation({ waitUntil: 'networkidle0' });

    console.log('  ✓ Logged in successfully');
  }

  async auditPage(pageConfig, viewport) {
    const page = await this.browser.newPage();

    try {
      // Set viewport
      await page.setViewport({ width: viewport.width, height: viewport.height });

      // Handle authentication if required
      if (pageConfig.auth && !this.isAuthenticated) {
        await this.login(page);
        this.isAuthenticated = true;
      }

      const url = `http://localhost:5173${pageConfig.path}`;
      console.log(`\n  Auditing: ${pageConfig.name} (${viewport.name})`);
      console.log(`  URL: ${url}`);

      await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });

      // Run axe audit
      const axeResults = await new AxePuppeteer(page)
        .withTags(this.config.axeRules.tags)
        .exclude(this.config.axeRules.exclude)
        .analyze();

      // Calculate page score
      const pageScore = this.calculatePageScore(axeResults);

      // Take screenshot if violations exist
      let screenshotPath = null;
      if (this.config.output.includeScreenshots && axeResults.violations.length > 0) {
        screenshotPath = await this.takeScreenshot(page, pageConfig.name, viewport.name);
      }

      const result = {
        page: pageConfig.name,
        path: pageConfig.path,
        viewport: viewport.name,
        score: pageScore,
        violations: this.formatViolations(axeResults.violations),
        violationCount: axeResults.violations.length,
        impactBreakdown: this.getImpactBreakdown(axeResults.violations),
        screenshot: screenshotPath,
        timestamp: new Date().toISOString(),
      };

      console.log(`  Score: ${pageScore}/100`);
      console.log(`  Violations: ${axeResults.violations.length}`);

      return result;

    } catch (error) {
      console.error(`  ✗ Error auditing ${pageConfig.name}:`, error.message);
      return {
        page: pageConfig.name,
        path: pageConfig.path,
        viewport: viewport.name,
        error: error.message,
        score: 0,
      };
    } finally {
      await page.close();
    }
  }

  formatViolations(violations) {
    return violations.map(v => ({
      id: v.id,
      impact: v.impact,
      description: v.description,
      help: v.help,
      helpUrl: v.helpUrl,
      tags: v.tags,
      nodes: v.nodes.map(n => ({
        html: n.html,
        target: n.target,
        failureSummary: n.failureSummary,
        impact: n.impact,
      })),
    }));
  }

  getImpactBreakdown(violations) {
    const breakdown = { critical: 0, serious: 0, moderate: 0, minor: 0 };
    violations.forEach(v => {
      if (breakdown[v.impact] !== undefined) {
        breakdown[v.impact]++;
      }
    });
    return breakdown;
  }

  calculatePageScore(axeResults) {
    // Weighted scoring based on impact
    const weights = {
      critical: 20,
      serious: 10,
      moderate: 5,
      minor: 2,
    };

    let totalDeductions = 0;
    axeResults.violations.forEach(v => {
      const weight = weights[v.impact] || 1;
      totalDeductions += weight * v.nodes.length;
    });

    return Math.max(0, 100 - totalDeductions);
  }

  async takeScreenshot(page, pageName, viewportName) {
    const screenshotDir = join(this.config.output.directory, 'screenshots');
    if (!existsSync(screenshotDir)) {
      mkdirSync(screenshotDir, { recursive: true });
    }

    const filename = `${pageName.replace(/\s+/g, '-').toLowerCase()}-${viewportName.toLowerCase()}.png`;
    const filepath = join(screenshotDir, filename);

    await page.screenshot({ path: filepath, fullPage: true });
    return filepath;
  }

  async runFullAudit() {
    console.log('🔍 Starting Accessibility Audit...\n');
    console.log(`WCAG Level: ${this.config.wcagLevel}`);
    console.log(`Pages to audit: ${this.config.pages.length}`);
    console.log(`Viewports: ${this.config.viewports.map(v => v.name).join(', ')}\n`);

    await this.init();

    // Audit each page on each viewport
    for (const pageConfig of this.config.pages) {
      for (const viewport of this.config.viewports) {
        const result = await this.auditPage(pageConfig, viewport);
        this.results.pages.push(result);

        // Update summary
        this.results.summary.totalPages++;
        this.results.summary.totalViolations += result.violationCount || 0;

        if (result.impactBreakdown) {
          this.results.summary.criticalCount += result.impactBreakdown.critical || 0;
          this.results.summary.seriousCount += result.impactBreakdown.serious || 0;
          this.results.summary.moderateCount += result.impactBreakdown.moderate || 0;
          this.results.summary.minorCount += result.impactBreakdown.minor || 0;
        }
      }
    }

    // Calculate overall score
    const avgScore = this.results.pages.reduce((sum, p) => sum + (p.score || 0), 0) / this.results.pages.length;
    this.results.summary.overallScore = Math.round(avgScore);

    await this.close();

    console.log('\n✅ Audit Complete!');
    console.log(`Overall Score: ${this.results.summary.overallScore}/100`);
    console.log(`Total Violations: ${this.results.summary.totalViolations}`);

    return this.results;
  }

  generateHTMLReport(results) {
    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hydra Accessibility Audit Report</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 { font-size: 36px; margin-bottom: 10px; }
        .header p { opacity: 0.9; }
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
        .summary-card h3 { font-size: 14px; color: #666; margin-bottom: 8px; text-transform: uppercase; }
        .summary-card .value { font-size: 32px; font-weight: bold; }
        .summary-card .value.score { color: ${results.summary.overallScore >= 90 ? '#10b981' : results.summary.overallScore >= 70 ? '#f59e0b' : '#ef4444'}; }
        .summary-card .value.critical { color: #dc2626; }
        .summary-card .value.serious { color: #ea580c; }
        .summary-card .value.moderate { color: #f59e0b; }
        .summary-card .value.minor { color: #84cc16; }

        .page-results {
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        .page-results h2 { margin-bottom: 20px; color: #1f2937; }

        .page-card {
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .page-card:last-child { margin-bottom: 0; }
        .page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f3f4f6;
        }
        .page-title { font-size: 18px; font-weight: 600; color: #1f2937; }
        .page-path { color: #6b7280; font-size: 14px; }
        .page-score {
            font-size: 24px;
            font-weight: bold;
            padding: 8px 16px;
            border-radius: 6px;
        }
        .score-excellent { background: #d1fae5; color: #065f46; }
        .score-good { background: #fef3c7; color: #92400e; }
        .score-poor { background: #fee2e2; color: #991b1b; }

        .violations-list { margin-top: 20px; }
        .violation {
            border-left: 4px solid #e5e7eb;
            padding: 15px;
            margin-bottom: 15px;
            background: #f9fafb;
            border-radius: 4px;
        }
        .violation.critical { border-left-color: #dc2626; background: #fef2f2; }
        .violation.serious { border-left-color: #ea580c; background: #fff7ed; }
        .violation.moderate { border-left-color: #f59e0b; background: #fffbeb; }
        .violation.minor { border-left-color: #84cc16; background: #f7fee7; }

        .violation-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 10px;
        }
        .violation-title { font-weight: 600; color: #1f2937; margin-bottom: 5px; }
        .violation-impact {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .impact-critical { background: #dc2626; color: white; }
        .impact-serious { background: #ea580c; color: white; }
        .impact-moderate { background: #f59e0b; color: white; }
        .impact-minor { background: #84cc16; color: white; }

        .violation-description { color: #4b5563; margin-bottom: 10px; }
        .violation-help { color: #6b7280; font-size: 14px; }
        .violation-help a { color: #667eea; text-decoration: none; }
        .violation-help a:hover { text-decoration: underline; }

        .node-count {
            display: inline-block;
            background: #e5e7eb;
            color: #374151;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            margin-top: 8px;
        }

        .footer {
            text-align: center;
            color: #6b7280;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
        }

        .no-violations {
            text-align: center;
            padding: 40px;
            color: #10b981;
        }
        .no-violations svg {
            width: 64px;
            height: 64px;
            margin-bottom: 16px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Hydra Accessibility Audit Report</h1>
            <p>Generated on ${new Date(results.summary.timestamp).toLocaleString()}</p>
            <p>WCAG ${this.config.wcagVersion} Level ${this.config.wcagLevel} Compliance Check</p>
        </div>

        <div class="summary">
            <div class="summary-card">
                <h3>Overall Score</h3>
                <div class="value score">${results.summary.overallScore}/100</div>
            </div>
            <div class="summary-card">
                <h3>Total Violations</h3>
                <div class="value">${results.summary.totalViolations}</div>
            </div>
            <div class="summary-card">
                <h3>Critical</h3>
                <div class="value critical">${results.summary.criticalCount}</div>
            </div>
            <div class="summary-card">
                <h3>Serious</h3>
                <div class="value serious">${results.summary.seriousCount}</div>
            </div>
            <div class="summary-card">
                <h3>Moderate</h3>
                <div class="value moderate">${results.summary.moderateCount}</div>
            </div>
            <div class="summary-card">
                <h3>Minor</h3>
                <div class="value minor">${results.summary.minorCount}</div>
            </div>
        </div>

        <div class="page-results">
            <h2>Page-by-Page Results</h2>
            ${results.pages.map(page => this.generatePageSection(page)).join('')}
        </div>

        <div class="footer">
            <p>Generated by Hydra Accessibility Auditor</p>
            <p>Powered by axe-core and Puppeteer</p>
        </div>
    </div>
</body>
</html>
    `;
    return html;
  }

  generatePageSection(page) {
    const scoreClass = page.score >= 90 ? 'score-excellent' : page.score >= 70 ? 'score-good' : 'score-poor';

    return `
      <div class="page-card">
        <div class="page-header">
          <div>
            <div class="page-title">${page.page} - ${page.viewport}</div>
            <div class="page-path">${page.path}</div>
          </div>
          <div class="page-score ${scoreClass}">${page.score}/100</div>
        </div>

        ${page.violations && page.violations.length > 0 ? `
          <div class="violations-list">
            ${page.violations.map(v => `
              <div class="violation ${v.impact}">
                <div class="violation-header">
                  <div>
                    <div class="violation-title">${v.help}</div>
                    <span class="node-count">${v.nodes.length} instance${v.nodes.length > 1 ? 's' : ''}</span>
                  </div>
                  <span class="violation-impact impact-${v.impact}">${v.impact}</span>
                </div>
                <div class="violation-description">${v.description}</div>
                <div class="violation-help">
                  <a href="${v.helpUrl}" target="_blank" rel="noopener">Learn more →</a>
                </div>
              </div>
            `).join('')}
          </div>
        ` : `
          <div class="no-violations">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>No accessibility violations detected! ✨</div>
          </div>
        `}
      </div>
    `;
  }

  saveResults(results) {
    // Create output directory
    if (!existsSync(this.config.output.directory)) {
      mkdirSync(this.config.output.directory, { recursive: true });
    }

    // Save JSON results
    const jsonPath = join(this.config.output.directory, 'accessibility-report.json');
    writeFileSync(jsonPath, JSON.stringify(results, null, 2));
    console.log(`\n📄 JSON report saved: ${jsonPath}`);

    // Generate and save HTML report
    if (this.config.output.format === 'html') {
      const htmlPath = join(this.config.output.directory, 'accessibility-report.html');
      const html = this.generateHTMLReport(results);
      writeFileSync(htmlPath, html);
      console.log(`📄 HTML report saved: ${htmlPath}`);
    }
  }
}

// Run audit if called directly
async function main() {
  const auditor = new AccessibilityAuditor(auditConfig);

  try {
    const results = await auditor.runFullAudit();
    auditor.saveResults(results);

    // Exit with error code if score is below threshold
    if (results.summary.overallScore < auditConfig.lighthouse.accessibility) {
      console.error(`\n❌ Accessibility score (${results.summary.overallScore}) is below threshold (${auditConfig.lighthouse.accessibility})`);
      process.exit(1);
    }

    process.exit(0);
  } catch (error) {
    console.error('Error running accessibility audit:', error);
    process.exit(1);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { AccessibilityAuditor };
