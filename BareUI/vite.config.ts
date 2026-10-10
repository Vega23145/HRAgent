import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), '')
	const apiTarget = env.VITE_API_URL || 'http://localhost:8000'

	return {
		plugins: [tailwindcss(), svelte()],
		server: {
			allowedHosts: ['frontend.1shhub.com'],
			proxy: {
				'/api': {
					target: apiTarget,
					changeOrigin: true,
				},
			},
		},
	}
})
