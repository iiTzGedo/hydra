# Hydra Web - Accessibility Testing Checklist

This comprehensive checklist ensures WCAG 2.2 Level AA compliance for the Hydra web application.

## 📋 Table of Contents

1. [Automated Testing](#automated-testing)
2. [Keyboard Navigation](#keyboard-navigation)
3. [Screen Reader Testing](#screen-reader-testing)
4. [Visual & Color](#visual--color)
5. [Forms & Inputs](#forms--inputs)
6. [Images & Media](#images--media)
7. [Semantic HTML & ARIA](#semantic-html--aria)
8. [Responsive & Mobile](#responsive--mobile)
9. [Dynamic Content](#dynamic-content)
10. [Testing Tools](#testing-tools)

---

## Automated Testing

### Setup

```bash
# Install dependencies
npm install

# Run all accessibility tests
npm run a11y:all

# Run individual tests
npm run a11y:audit        # Full axe-core audit
npm run a11y:keyboard     # Keyboard navigation
npm run a11y:contrast     # Color contrast
npm run a11y:aria         # ARIA and semantic HTML
```

### Automated Test Coverage

- [ ] All automated tests pass with score ≥ 90/100
- [ ] Zero critical violations
- [ ] Zero serious violations
- [ ] Review and address all moderate violations
- [ ] Document any minor violations with justification

---

## Keyboard Navigation

### Tab Navigation

- [ ] **Tab** key moves focus forward through all interactive elements
- [ ] **Shift+Tab** moves focus backward
- [ ] Tab order follows logical visual flow (left-to-right, top-to-bottom)
- [ ] Focus indicator is always visible and has sufficient contrast (3:1 minimum)
- [ ] No keyboard traps (user can always tab away)
- [ ] Skip navigation link provided (to main content)

### Activation

- [ ] **Enter** activates links and buttons
- [ ] **Space** activates buttons (but not links)
- [ ] Custom interactive elements respond to both Enter and Space
- [ ] Form submission works with Enter key

### Modal Dialogs

- [ ] **Escape** key closes modal dialogs
- [ ] Focus is trapped within open modal
- [ ] Focus returns to trigger element when modal closes
- [ ] First focusable element receives focus when modal opens

### Custom Components

- [ ] **Arrow keys** navigate through tabs, select options, menus
- [ ] **Home/End** keys work in appropriate contexts
- [ ] Dropdown menus can be navigated with arrow keys
- [ ] Date pickers are keyboard accessible

### Sidebar & Navigation

- [ ] Sidebar can be collapsed/expanded with keyboard
- [ ] All navigation items are keyboard accessible
- [ ] Tooltip triggers work with keyboard focus
- [ ] Mobile menu can be opened/closed with keyboard

---

## Screen Reader Testing

### Browsers & Screen Readers

Test with at least two combinations:

- [ ] **NVDA** + Firefox (Windows)
- [ ] **JAWS** + Chrome (Windows)
- [ ] **VoiceOver** + Safari (macOS/iOS)
- [ ] **TalkBack** + Chrome (Android)

### Page Structure

- [ ] Page title is descriptive and unique
- [ ] Main heading (h1) describes the page purpose
- [ ] Headings create logical document outline
- [ ] Landmarks are properly announced (main, navigation, banner, contentinfo)
- [ ] Landmark labels distinguish multiple instances (e.g., "Main navigation" vs "Footer navigation")

### Content

- [ ] All text content is announced correctly
- [ ] Reading order matches visual order
- [ ] Lists are properly announced as lists
- [ ] Tables have proper headers and captions
- [ ] Charts/graphs have text alternatives or descriptions

### Interactive Elements

- [ ] All buttons announce their purpose
- [ ] Links announce where they lead
- [ ] Form labels are announced with inputs
- [ ] Error messages are associated with inputs
- [ ] Current page/section is announced in navigation
- [ ] Loading states are announced

### Dynamic Content

- [ ] ARIA live regions announce updates
- [ ] Toast notifications are announced
- [ ] Auto-complete suggestions are announced
- [ ] Modal dialogs are announced when opened
- [ ] Error and success messages are announced

---

## Visual & Color

### Color Contrast

- [ ] **Normal text** (< 18pt) has 4.5:1 contrast minimum
- [ ] **Large text** (≥ 18pt or ≥ 14pt bold) has 3:1 contrast minimum
- [ ] **UI components** have 3:1 contrast against adjacent colors
- [ ] **Focus indicators** have 3:1 contrast
- [ ] Contrast maintained in dark mode
- [ ] High contrast mode is supported

### Color Independence

- [ ] Information is not conveyed by color alone
- [ ] Error states use icon + text, not just red color
- [ ] Success states use icon + text, not just green color
- [ ] Charts include patterns or labels, not just colors
- [ ] Links are underlined or have sufficient contrast
- [ ] Required fields marked with * and "(required)" text

### Visual Clarity

- [ ] Text can be resized to 200% without loss of content or functionality
- [ ] Content reflows at 320px width (mobile)
- [ ] No horizontal scrolling at 1280px width (desktop)
- [ ] Line height is at least 1.5x font size
- [ ] Paragraph spacing is at least 1.5x line height
- [ ] Touch targets are at least 44x44 pixels

### Motion & Animation

- [ ] Animations respect `prefers-reduced-motion`
- [ ] Animations can be paused
- [ ] No auto-playing videos with sound
- [ ] Parallax/scroll effects can be disabled
- [ ] No content flashes more than 3 times per second

---

## Forms & Inputs

### Labels

- [ ] All inputs have associated labels
- [ ] Labels are visible (not just placeholder)
- [ ] Labels use `<label for="id">` or wrap inputs
- [ ] Icon-only inputs have `aria-label`
- [ ] Group related inputs with `<fieldset>` and `<legend>`

### Error Handling

- [ ] Errors identified with text, not just color
- [ ] Error messages associated with inputs (`aria-describedby`)
- [ ] Errors announced to screen readers
- [ ] Inline validation provides helpful messages
- [ ] Required fields marked clearly

### Input Types

- [ ] Correct HTML5 input types used (email, tel, number, etc.)
- [ ] Autocomplete attributes provided where appropriate
- [ ] Search inputs have `type="search"` and `role="search"`
- [ ] Date inputs are accessible (not just calendar widget)

### Form Submission

- [ ] Submit button has clear label
- [ ] Loading state announced during submission
- [ ] Success/error outcome announced
- [ ] Focus managed after submission
- [ ] Form can be submitted with Enter key

---

## Images & Media

### Images

- [ ] All informative images have descriptive alt text
- [ ] Decorative images have empty alt (`alt=""`)
- [ ] Complex images have long descriptions
- [ ] SVG icons have `role="img"` and `aria-label`
- [ ] Icon-only buttons have text alternatives
- [ ] Image buttons have descriptive alt text

### Charts & Graphs

- [ ] Charts have text alternative (table or description)
- [ ] Data points can be accessed via keyboard
- [ ] Color is not the only means of understanding data
- [ ] Tooltips are keyboard accessible

### Media

- [ ] Videos have captions
- [ ] Audio has transcripts
- [ ] Media controls are keyboard accessible
- [ ] Auto-play is avoided or can be stopped
- [ ] Volume controls are accessible

---

## Semantic HTML & ARIA

### Semantic Elements

- [ ] Use semantic HTML5 elements (`<nav>`, `<main>`, `<article>`, `<aside>`, `<header>`, `<footer>`)
- [ ] Heading levels are logical (no skipped levels)
- [ ] Lists use `<ul>`, `<ol>`, `<dl>` appropriately
- [ ] Tables use `<table>`, `<thead>`, `<tbody>`, `<th>`
- [ ] Forms use `<form>`, `<label>`, `<fieldset>`

### ARIA Usage

- [ ] ARIA used to enhance, not replace, semantic HTML
- [ ] `role` attributes are valid and appropriate
- [ ] `aria-label` provides accessible names where needed
- [ ] `aria-labelledby` references valid IDs
- [ ] `aria-describedby` provides additional context
- [ ] `aria-hidden="true"` on decorative elements only
- [ ] `aria-live` regions for dynamic content
- [ ] `aria-current` indicates current page/step
- [ ] `aria-expanded` indicates collapsed/expanded state
- [ ] `aria-pressed` indicates toggle button state

### Landmark Regions

- [ ] One `<main>` or `role="main"` per page
- [ ] Navigation in `<nav>` or `role="navigation"`
- [ ] Page header in `<header>` or `role="banner"`
- [ ] Page footer in `<footer>` or `role="contentinfo"`
- [ ] Multiple landmarks of same type have labels

### Interactive Patterns

- [ ] Tabs follow ARIA tabs pattern
- [ ] Accordions follow ARIA accordion pattern
- [ ] Modals follow ARIA dialog pattern
- [ ] Menus follow ARIA menu pattern (or avoid role="menu" for navigation)
- [ ] Tooltips follow ARIA tooltip pattern

---

## Responsive & Mobile

### Mobile Experience

- [ ] All functionality available on touch devices
- [ ] Touch targets are at least 44x44 pixels
- [ ] No hover-only functionality
- [ ] Pinch-to-zoom is not disabled
- [ ] Viewport meta tag is properly configured
- [ ] Content is readable without horizontal scrolling

### Orientation

- [ ] App works in both portrait and landscape
- [ ] Orientation is not locked (unless essential)
- [ ] Content adapts to orientation changes

### Mobile Screen Readers

- [ ] VoiceOver (iOS) can navigate app
- [ ] TalkBack (Android) can navigate app
- [ ] Swipe gestures work correctly
- [ ] Mobile-specific components are accessible

---

## Dynamic Content

### Loading States

- [ ] Loading indicators have accessible names
- [ ] `aria-busy` used during loading
- [ ] Loading announced to screen readers
- [ ] Skeleton loaders don't interfere with screen readers

### AJAX Updates

- [ ] Dynamic updates announced via `aria-live`
- [ ] `aria-live="polite"` for non-urgent updates
- [ ] `aria-live="assertive"` for urgent updates
- [ ] Focus management after content change

### Infinite Scroll

- [ ] Infinite scroll is keyboard accessible
- [ ] Load more button available as alternative
- [ ] Loading announced to screen readers
- [ ] User can reach footer content

### Toasts & Notifications

- [ ] Toasts announced via `role="status"` or `aria-live`
- [ ] Toasts don't steal focus
- [ ] Toasts can be dismissed with keyboard
- [ ] Toasts don't time out too quickly
- [ ] Multiple toasts are queued properly

---

## Testing Tools

### Browser Extensions

- [ ] [axe DevTools](https://www.deque.com/axe/devtools/) - Automated testing
- [ ] [WAVE](https://wave.webaim.org/extension/) - Visual accessibility evaluation
- [ ] [Accessibility Insights](https://accessibilityinsights.io/) - Microsoft's testing tools
- [ ] [Lighthouse](https://developers.google.com/web/tools/lighthouse) - Chrome DevTools

### Desktop Tools

- [ ] [NVDA](https://www.nvaccess.org/) - Free screen reader (Windows)
- [ ] [JAWS](https://www.freedomscientific.com/products/software/jaws/) - Popular screen reader (Windows, trial available)
- [ ] VoiceOver - Built-in screen reader (macOS)
- [ ] [Colour Contrast Analyser](https://www.tpgi.com/color-contrast-checker/) - Color testing tool

### Online Tools

- [ ] [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- [ ] [ARIA Practices Guide](https://www.w3.org/WAI/ARIA/apg/)
- [ ] [HTML5 Validator](https://validator.w3.org/)
- [ ] [AChecker](https://achecker.achecks.ca/checker/index.php)

### Automated Tests (Built-in)

```bash
# Run all automated tests
npm run a11y:all

# Individual test suites
npm run a11y:audit      # axe-core full audit
npm run a11y:keyboard   # Keyboard navigation
npm run a11y:contrast   # Color contrast
npm run a11y:aria       # ARIA and semantics
```

---

## Page-Specific Checklists

### Login Page (`/login`)

- [ ] Username and password fields have labels
- [ ] "Show password" toggle is keyboard accessible
- [ ] Error messages are announced
- [ ] "Remember me" checkbox has label
- [ ] "Forgot password" link is descriptive

### Dashboard (`/`)

- [ ] Stats cards have descriptive headings
- [ ] Charts have text alternatives
- [ ] Mini topology is keyboard navigable
- [ ] Activity feed updates are announced
- [ ] Node status grid is accessible

### Nodes List (`/nodes`)

- [ ] Filters are keyboard accessible
- [ ] Table has proper headers
- [ ] Sort controls are keyboard accessible
- [ ] Pagination is keyboard accessible
- [ ] Search results are announced

### Node Detail (`/nodes/:id`)

- [ ] Profile tabs are keyboard accessible
- [ ] Profile comparison is accessible
- [ ] Services list is navigable
- [ ] Action buttons have clear labels

### Topology (`/topology`)

- [ ] SVG topology has text alternative
- [ ] Nodes can be focused with keyboard
- [ ] Zoom controls are keyboard accessible
- [ ] Detail panel is accessible
- [ ] Legend is screen reader friendly

### Time Machine (`/timemachine`)

- [ ] Timeline scrubber is keyboard accessible
- [ ] Date picker is accessible
- [ ] Event stream updates are announced
- [ ] Historical state changes are clear

### Chat/MCP (`/chat`)

- [ ] Chat input has label
- [ ] Messages are in semantic list
- [ ] New messages are announced
- [ ] Code blocks have language labels
- [ ] Message actions are keyboard accessible

### Admin Pages

- [ ] User table is accessible
- [ ] Forms have proper labels
- [ ] Confirmation dialogs are accessible
- [ ] Bulk actions are keyboard accessible
- [ ] Audit log is screen reader friendly

---

## Remediation Priority

### Critical (Fix Immediately)

- Missing alt text on informative images
- Form inputs without labels
- Insufficient color contrast (< 3:1)
- Keyboard traps
- Missing page title or h1
- ARIA errors (invalid roles, broken references)

### High (Fix Soon)

- Skipped heading levels
- Missing landmark regions
- Focus indicators too subtle
- Incorrect ARIA usage
- Non-semantic interactive elements

### Medium (Plan to Fix)

- Missing ARIA labels on icon buttons
- Insufficient contrast on secondary text
- Missing live region announcements
- Complex components need better ARIA

### Low (Nice to Have)

- Additional descriptive text
- Enhanced keyboard shortcuts
- Better screen reader descriptions
- Improved loading states

---

## Continuous Monitoring

### CI/CD Integration

Add accessibility tests to your CI pipeline:

```yaml
# .github/workflows/accessibility.yml
name: Accessibility Tests

on: [push, pull_request]

jobs:
  a11y:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npm run build
      - run: npm start &
      - run: npm run a11y:all
```

### Regular Testing Schedule

- [ ] Run automated tests before every deployment
- [ ] Manual keyboard testing weekly
- [ ] Screen reader testing monthly
- [ ] User testing with assistive technology quarterly

---

## Resources

### WCAG Guidelines

- [WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/)
- [Understanding WCAG 2.2](https://www.w3.org/WAI/WCAG22/Understanding/)
- [How to Meet WCAG (Customizable Quick Reference)](https://www.w3.org/WAI/WCAG22/quickref/)

### Best Practices

- [ARIA Authoring Practices Guide (APG)](https://www.w3.org/WAI/ARIA/apg/)
- [Inclusive Components](https://inclusive-components.design/)
- [A11y Project Checklist](https://www.a11yproject.com/checklist/)
- [WebAIM Resources](https://webaim.org/resources/)

### Hydra-Specific

- [Component Documentation](./docs/components.md)
- [Accessibility Reports](./accessibility-reports/)
- [Known Issues](./ACCESSIBILITY_ISSUES.md)

---

**Last Updated**: 2026-01-09

**Maintained By**: Hydra Development Team

**Questions?** Contact the accessibility team or file an issue.
