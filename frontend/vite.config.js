import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  // Django sirve los assets bajo /static/, en desarrollo y en producción.
  base: "/static/",
  plugins: [tailwindcss()],
  server: {
    host: true, // escucha en 0.0.0.0 para que el puerto reenviado llegue al navegador
    port: 5173,
    strictPort: true,
  },
  build: {
    manifest: "manifest.json", // django-vite lee este archivo
    outDir: "../backend/frontend_dist",
    emptyOutDir: true,
    rollupOptions: {
      input: "src/main.js",
    },
  },
});