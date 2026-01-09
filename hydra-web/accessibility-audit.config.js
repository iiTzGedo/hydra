/**
 * Accessibility Audit Configuration
 * Defines test targets, WCAG compliance levels, and audit parameters
 */

export const auditConfig = {
  // WCAG compliance level
  wcagLevel: 'AA', // AA or AAA
  wcagVersion: '2.2',

  // Pages to audit
  pages: [
    { name: 'Login', path: '/login', priority: 'high' },
    { name: 'Register', path: '/register', priority: 'high' },
    { name: 'Dashboard', path: '/', auth: true, priority: 'high' },
    { name: 'Nodes List', path: '/nodes', auth: true, priority: 'high' },
    { name: 'Node Detail', path: '/nodes/test-node-01', auth: true, priority: 'medium' },
    { name: 'Services', path: '/services', auth: true, priority: 'high' },
    { name: 'Networks', path: '/networks', auth: true, priority: 'medium' },
    { name: 'Groups', path: '/groups', auth: true, priority: 'medium' },
    { name: 'Topology', path: '/topology', auth: true, priority: 'high' },
    { name: 'Time Machine', path: '/timemachine', auth: true, priority: 'medium' },
    { name: 'Chat', path: '/chat', auth: true, priority: 'medium' },
    { name: 'Settings', path: '/settings', auth: true, priority: 'medium' },
    { name: 'Admin - Users', path: '/admin/users', auth: true, admin: true, priority: 'low' },
  ],

  // Test viewport sizes
  viewports: [
    { name: 'Mobile', width: 375, height: 667 },
    { name: 'Tablet', width: 768, height: 1024 },
    { name: 'Desktop', width: 1920, height: 1080 },
  ],

  // axe-core rules configuration
  axeRules: {
    // WCAG 2.2 Level AA tags
    tags: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'],

    // Exclude certain selectors from testing (e.g., third-party widgets)
    exclude: [
      '.no-a11y-check',
      '[data-test-ignore-a11y]',
    ],
  },

  // Color contrast thresholds
  colorContrast: {
    normal: {
      AA: 4.5,
      AAA: 7.0,
    },
    large: {
      AA: 3.0,
      AAA: 4.5,
    },
  },

  // Lighthouse performance budgets
  lighthouse: {
    accessibility: 90, // Minimum score
    bestPractices: 85,
    seo: 85,
  },

  // Output configuration
  output: {
    format: 'html', // html, json, csv
    directory: './accessibility-reports',
    includeScreenshots: true,
  },
};

export default auditConfig;
