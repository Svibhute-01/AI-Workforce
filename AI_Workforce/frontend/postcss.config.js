import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))

export default {
  plugins: {
    tailwindcss: { config: path.join(frontendRoot, 'tailwind.config.js') },
    autoprefixer: {}
  }
}
