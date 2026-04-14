module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
    'plugin:jsx-a11y/recommended',
  ],
  ignorePatterns: ['dist', '.next', 'node_modules', '*.config.*', 'e2e', 'next-env.d.ts'],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  plugins: ['jsx-a11y'],
  rules: {
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    'jsx-a11y/no-autofocus': 'off',
  },
  overrides: [
    {
      files: ['src/**/*.{ts,tsx}'],
      excludedFiles: ['src/__tests__/**/*.{ts,tsx}'],
      rules: {
        '@typescript-eslint/no-explicit-any': 'error',
      },
    },
    {
      files: ['src/__tests__/**/*.{ts,tsx}'],
      rules: {
        '@typescript-eslint/no-explicit-any': 'off',
      },
    },
  ],
};
