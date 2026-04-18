/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./app/**/*.{js,ts,jsx,tsx}', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Semantic colors from CSS variables
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        // Hydra status colors
        success: {
          DEFAULT: 'hsl(var(--success))',
          foreground: 'hsl(var(--success-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          foreground: 'hsl(var(--warning-foreground))',
        },
        info: {
          DEFAULT: 'hsl(var(--info))',
          foreground: 'hsl(var(--info-foreground))',
        },
        // Node class colors
        compute: {
          DEFAULT: 'hsl(var(--compute))',
          foreground: 'hsl(var(--compute-foreground))',
        },
        network: {
          DEFAULT: 'hsl(var(--network))',
          foreground: 'hsl(var(--network-foreground))',
        },
        iot: {
          DEFAULT: 'hsl(var(--iot))',
          foreground: 'hsl(var(--iot-foreground))',
        },
        // Chart colors
        chart: {
          1: 'hsl(var(--chart-1))',
          2: 'hsl(var(--chart-2))',
          3: 'hsl(var(--chart-3))',
          4: 'hsl(var(--chart-4))',
          5: 'hsl(var(--chart-5))',
        },
        // Event-type palette - Time Machine / audit events
        event: {
          profile: {
            DEFAULT: 'hsl(var(--event-profile))',
            foreground: 'hsl(var(--event-profile-foreground))',
          },
          'service-added': {
            DEFAULT: 'hsl(var(--event-service-added))',
            foreground: 'hsl(var(--event-service-added-foreground))',
          },
          'service-removed': {
            DEFAULT: 'hsl(var(--event-service-removed))',
            foreground: 'hsl(var(--event-service-removed-foreground))',
          },
          topology: {
            DEFAULT: 'hsl(var(--event-topology))',
            foreground: 'hsl(var(--event-topology-foreground))',
          },
          'node-added': {
            DEFAULT: 'hsl(var(--event-node-added))',
            foreground: 'hsl(var(--event-node-added-foreground))',
          },
          'node-removed': {
            DEFAULT: 'hsl(var(--event-node-removed))',
            foreground: 'hsl(var(--event-node-removed-foreground))',
          },
          network: {
            DEFAULT: 'hsl(var(--event-network))',
            foreground: 'hsl(var(--event-network-foreground))',
          },
          group: {
            DEFAULT: 'hsl(var(--event-group))',
            foreground: 'hsl(var(--event-group-foreground))',
          },
        },
        // Severity palette - notification tiers
        severity: {
          critical: {
            DEFAULT: 'hsl(var(--severity-critical))',
            foreground: 'hsl(var(--severity-critical-foreground))',
          },
          high: {
            DEFAULT: 'hsl(var(--severity-high))',
            foreground: 'hsl(var(--severity-high-foreground))',
          },
          medium: {
            DEFAULT: 'hsl(var(--severity-medium))',
            foreground: 'hsl(var(--severity-medium-foreground))',
          },
          low: {
            DEFAULT: 'hsl(var(--severity-low))',
            foreground: 'hsl(var(--severity-low-foreground))',
          },
        },
        // Surface elevation layers
        surface: {
          1: 'hsl(var(--surface-1))',
          2: 'hsl(var(--surface-2))',
          3: 'hsl(var(--surface-3))',
          4: 'hsl(var(--surface-4))',
        },
        // Sidebar
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['Geist Mono', 'monospace'],
        mono: ['Geist Mono', 'monospace'],
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'fade-out': {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' },
        },
        'slide-in-from-right': {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        'slide-in-from-left': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        'slide-in-from-top': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(0)' },
        },
        'slide-in-from-bottom': {
          '0%': { transform: 'translateY(100%)' },
          '100%': { transform: 'translateY(0)' },
        },
        'slide-out-to-right': {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(100%)' },
        },
        'slide-out-to-left': {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-100%)' },
        },
        'zoom-in': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'zoom-out': {
          '0%': { opacity: '1', transform: 'scale(1)' },
          '100%': { opacity: '0', transform: 'scale(0.95)' },
        },
        pulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        spin: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        shimmer: 'shimmer 2s infinite linear',
        'fade-in': 'fade-in 0.2s ease-out',
        'fade-out': 'fade-out 0.2s ease-out',
        'slide-in-from-right': 'slide-in-from-right 0.3s ease-out',
        'slide-in-from-left': 'slide-in-from-left 0.3s ease-out',
        'slide-in-from-top': 'slide-in-from-top 0.3s ease-out',
        'slide-in-from-bottom': 'slide-in-from-bottom 0.3s ease-out',
        'slide-out-to-right': 'slide-out-to-right 0.3s ease-out',
        'slide-out-to-left': 'slide-out-to-left 0.3s ease-out',
        'zoom-in': 'zoom-in 0.2s ease-out',
        'zoom-out': 'zoom-out 0.2s ease-out',
        pulse: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        spin: 'spin 1s linear infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
