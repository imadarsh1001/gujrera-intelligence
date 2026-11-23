import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    poolOptions: {
      threads: {
        execArgv: ['--no-experimental-webstorage'],
      },
      forks: {
        execArgv: ['--no-experimental-webstorage'],
      },
    },
  },
})
