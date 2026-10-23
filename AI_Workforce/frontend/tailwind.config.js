import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))

export default {
  content: [
    path.join(frontendRoot, 'index.html'),
    path.join(frontendRoot, 'src/**/*.{js,jsx}'),
  ],
  theme: {
    extend: {
      colors: {
        primary: '#5B2DD8',
        'primary-light': '#f3e8ff',
        'primary-dark': '#4b1fa8',
        'bg-light': '#f8f7ff',
        'card-bg': '#ffffff',
        'text-primary': '#1a1a1a',
        'text-secondary': '#666666',
        'border-light': '#e5e0ff',
        'status-success': '#10b981',
        'status-warning': '#f59e0b',
        'status-danger': '#ef4444',
        'status-info': '#3b82f6',
        // Developer workspace palette. The values live in index.css so they follow the light/dark theme.
        ide: {
          'bg': 'rgb(var(--ide-bg) / <alpha-value>)',
          'panel': 'rgb(var(--ide-panel) / <alpha-value>)',
          'border': 'rgb(var(--ide-border) / <alpha-value>)',
          'hover': 'rgb(var(--ide-hover) / <alpha-value>)',
          'text': 'rgb(var(--ide-text) / <alpha-value>)',
          'text2': 'rgb(var(--ide-text2) / <alpha-value>)',
          'muted': 'rgb(var(--ide-muted) / <alpha-value>)',
          'faint': 'rgb(var(--ide-faint) / <alpha-value>)',
          'code': 'rgb(var(--ide-code) / <alpha-value>)',
          'accent': 'rgb(var(--ide-accent) / <alpha-value>)',
          'accent-hover': 'rgb(var(--ide-accent-hover) / <alpha-value>)',
          'info': 'rgb(var(--ide-info) / <alpha-value>)',
          'success': 'rgb(var(--ide-success) / <alpha-value>)',
          'danger': 'rgb(var(--ide-danger) / <alpha-value>)',
          'dangertext': 'rgb(var(--ide-dangertext) / <alpha-value>)',
          'warn': 'rgb(var(--ide-warn) / <alpha-value>)',
          'syn-keyword': 'rgb(var(--ide-syn-keyword) / <alpha-value>)',
          'syn-string': 'rgb(var(--ide-syn-string) / <alpha-value>)',
          'syn-comment': 'rgb(var(--ide-syn-comment) / <alpha-value>)',
          'syn-number': 'rgb(var(--ide-syn-number) / <alpha-value>)',
          'syn-decorator': 'rgb(var(--ide-syn-decorator) / <alpha-value>)',
          'syn-name': 'rgb(var(--ide-syn-name) / <alpha-value>)'
        }
      }
    }
  },
  plugins: []
}
