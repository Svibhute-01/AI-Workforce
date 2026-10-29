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
        primary: 'rgb(var(--c-primary) / <alpha-value>)',
        'primary-light': 'rgb(var(--c-primary-light) / <alpha-value>)',
        'primary-dark': 'rgb(var(--c-primary-dark) / <alpha-value>)',
        'bg-light': 'rgb(var(--c-bg) / <alpha-value>)',
        'card-bg': 'rgb(var(--c-card) / <alpha-value>)',
        'text-primary': 'rgb(var(--c-text) / <alpha-value>)',
        'text-secondary': 'rgb(var(--c-text-2) / <alpha-value>)',
        'border-light': 'rgb(var(--c-border) / <alpha-value>)',
        'status-success': 'rgb(var(--c-success) / <alpha-value>)',
        'status-warning': 'rgb(var(--c-warning) / <alpha-value>)',
        'status-danger': 'rgb(var(--c-danger) / <alpha-value>)',
        'status-info': 'rgb(var(--c-info) / <alpha-value>)',
        surface: 'rgb(var(--c-surface) / <alpha-value>)',
        brand: {
          cream: '#F4F8FF',
          soft: '#DCE7FF',
          lemon: '#EAF1FF',
          golden: '#7F97FF',
          custard: '#D4E0FA',
          deep: '#B7CBEE',
          ink: '#0B1E3B',
        },
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
