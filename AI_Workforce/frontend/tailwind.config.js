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
        'status-info': '#3b82f6'
      }
    }
  },
  plugins: []
}
