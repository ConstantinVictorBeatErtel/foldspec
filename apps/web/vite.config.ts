import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: { rollupOptions: { output: { manualChunks: { 'three-engine': ['three'], 'three-react': ['@react-three/fiber', '@react-three/drei'] } } } },
})
