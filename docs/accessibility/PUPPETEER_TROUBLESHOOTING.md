# Puppeteer Troubleshooting Guide

## Error: Failed to launch the browser process

This error occurs when Puppeteer cannot find or launch Chromium. Here are solutions for different scenarios:

---

## Solution 1: Install System Dependencies (Linux)

**For Debian/Ubuntu/Proxmox VE:**

```bash
sudo apt-get update
sudo apt-get install -y \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    wget \
    xdg-utils
```

**For RHEL/CentOS/Fedora:**

```bash
sudo yum install -y \
    alsa-lib.x86_64 \
    atk.x86_64 \
    cups-libs.x86_64 \
    gtk3.x86_64 \
    libXcomposite.x86_64 \
    libXcursor.x86_64 \
    libXdamage.x86_64 \
    libXext.x86_64 \
    libXi.x86_64 \
    libXrandr.x86_64 \
    libXScrnSaver.x86_64 \
    libXtst.x86_64 \
    pango.x86_64 \
    xorg-x11-fonts-100dpi \
    xorg-x11-fonts-75dpi \
    xorg-x11-fonts-cyrillic \
    xorg-x11-fonts-misc \
    xorg-x11-fonts-Type1 \
    xorg-x11-utils
```

---

## Solution 2: Reinstall Puppeteer

```bash
cd hydra-web

# Remove node_modules and package-lock.json
rm -rf node_modules package-lock.json

# Reinstall all dependencies
npm install
```

---

## Solution 3: Use Existing Chrome/Chromium

If you have Chrome or Chromium already installed:

```bash
# Find your Chrome/Chromium executable
which google-chrome
which chromium
which chromium-browser

# Example output: /usr/bin/chromium-browser
```

Then update the test scripts to use it. I've already configured the scripts to work without sandbox, but if you want to use your own Chrome:

Create `hydra-web/puppeteer.config.js`:

```javascript
export default {
  executablePath: '/usr/bin/chromium-browser', // Your Chrome path
};
```

---

## Solution 4: Skip Chromium Download, Use System Chrome

```bash
cd hydra-web

# Set environment variable to skip Chromium download
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Install Puppeteer
npm install puppeteer

# Install system Chrome/Chromium
sudo apt-get install chromium-browser
```

---

## Solution 5: Scripts Already Updated (Try This First!)

I've already updated all the accessibility testing scripts with better Puppeteer configuration:

- Disabled sandbox (for Docker/Linux containers)
- Added `--disable-dev-shm-usage` (for limited memory)
- Disabled GPU acceleration
- Added proper window size

**Just try running the tests again:**

```bash
npm run a11y:audit
```

---

## Verify Puppeteer Installation

Check if Puppeteer is working:

```bash
cd hydra-web

# Create test file
cat > test-puppeteer.js << 'EOF'
import puppeteer from 'puppeteer';

(async () => {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu'
    ],
  });
  console.log('✅ Browser launched successfully!');

  const page = await browser.newPage();
  await page.goto('https://example.com');
  console.log('✅ Page loaded successfully!');

  await browser.close();
  console.log('✅ Test complete!');
})();
EOF

# Run test
node test-puppeteer.js

# Clean up
rm test-puppeteer.js
```

If this works, your accessibility tests should work too!

---

## Common Errors and Solutions

### Error: `Could not find Chrome`

**Solution**: Install Chrome/Chromium or set `PUPPETEER_EXECUTABLE_PATH`

```bash
# Install Chromium
sudo apt-get install chromium-browser

# Or set path to existing Chrome
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
```

### Error: `Failed to launch chrome! spawn EACCES`

**Solution**: Fix permissions

```bash
# Make Chrome executable
sudo chmod +x /usr/bin/chromium-browser

# Or fix Puppeteer downloaded Chrome
chmod +x node_modules/puppeteer/.local-chromium/*/chrome-linux/chrome
```

### Error: `Running as root without --no-sandbox`

**Solution**: Already handled in the scripts! The `--no-sandbox` flag is now included.

### Error: `Error: Failed to connect to chrome`

**Solution**: Increase timeout or check if port is blocked

Update script timeout in `accessibility-audit.config.js`:

```javascript
// Increase timeout
timeout: 60000, // 60 seconds instead of 30
```

---

## Docker/Container Environments

If running in Docker or LXC container:

```dockerfile
# Add to Dockerfile
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-sandbox \
    fonts-liberation \
    libappindicator3-1 \
    libnss3 \
    libxss1

# Set environment variables
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
```

---

## Headless Display Issues

If you need X11 display (usually not needed with headless):

```bash
# Install Xvfb
sudo apt-get install xvfb

# Run with virtual display
xvfb-run -a npm run a11y:audit
```

---

## Alternative: Use Playwright Instead

If Puppeteer continues to cause issues, we can switch to Playwright (Microsoft's alternative):

```bash
npm install -D @playwright/test
npx playwright install chromium
```

Playwright generally has better Linux support and handles dependencies automatically.

---

## Environment-Specific Notes

### Proxmox VE LXC Containers

You're running on Proxmox VE (Linux 6.8.12-17-pve). For LXC containers:

1. **Ensure container has enough resources**: 2GB RAM minimum
2. **Check /dev/shm size**: Should be at least 64MB

```bash
# Check /dev/shm
df -h /dev/shm

# If too small, increase in container config:
# On Proxmox host:
pct set <container-id> -mp0 /dev/shm,mp=/dev/shm,size=128M
```

3. **Nested virtualization**: Not needed for Puppeteer, but if using other tools
4. **Capabilities**: Container needs `cap_sys_admin` for sandbox, but we're disabling it anyway

### SSH/Remote Development

If developing over SSH without X11:

```bash
# Ensure headless mode (already configured)
# Tests will run without display
npm run a11y:audit
```

---

## Quick Diagnostic

Run this to diagnose your environment:

```bash
cat > diagnose.sh << 'EOF'
#!/bin/bash

echo "=== Puppeteer Diagnostic ==="
echo ""

echo "1. Node.js version:"
node --version

echo ""
echo "2. NPM version:"
npm --version

echo ""
echo "3. Chrome/Chromium installed:"
which google-chrome chromium chromium-browser || echo "Not found in PATH"

echo ""
echo "4. /dev/shm size:"
df -h /dev/shm

echo ""
echo "5. Puppeteer installed:"
npm list puppeteer 2>/dev/null || echo "Not installed"

echo ""
echo "6. System architecture:"
uname -m

echo ""
echo "7. OS info:"
cat /etc/os-release | head -n 2

echo ""
echo "8. Missing libraries check (common dependencies):"
libs=(
    "libatk-1.0.so.0"
    "libatk-bridge-2.0.so.0"
    "libcups.so.2"
    "libgbm.so.1"
    "libnss3.so"
    "libxcomposite.so.1"
)

for lib in "${libs[@]}"; do
    if ldconfig -p | grep -q "$lib"; then
        echo "✓ $lib"
    else
        echo "✗ $lib (missing)"
    fi
done
EOF

chmod +x diagnose.sh
./diagnose.sh
```

---

## Still Having Issues?

1. **Share the full error message** from the terminal
2. **Run the diagnostic script** above and share output
3. **Check if running in container** (Docker, LXC, etc.)
4. **Try the test-puppeteer.js** script above

The scripts have been updated with better defaults, so try running:

```bash
npm run a11y:audit
```

again and it should work! If not, the diagnostic output will help identify the specific issue.

---

## Success Verification

You'll know it's working when you see:

```
🔍 Starting Accessibility Audit...

WCAG Level: AA
Pages to audit: 13
Viewports: Mobile, Tablet, Desktop

  Auditing: Login (Mobile)
  URL: http://localhost:5173/login
  Score: 95/100
  Violations: 2
```

And reports will be generated in `accessibility-reports/`.

---

**Last Updated**: 2026-01-09
**Platform**: Linux (Proxmox VE)
