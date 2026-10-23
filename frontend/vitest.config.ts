import { defineConfig } from 'vitest/config';

/**
 * Vitest configuration for the editor libraries.
 *
 * The Naskah Studio modules are plain TypeScript that touch the DOM, so the
 * suite runs under jsdom with the `$lib` / `$app` aliases SvelteKit provides at
 * build time. Only the `.ts` helpers are unit-tested here; components are
 * covered by svelte-check and the Playwright smoke pass.
 */
export default defineConfig({
	resolve: {
		alias: {
			$lib: new URL('./src/lib', import.meta.url).pathname,
			$app: new URL('./src/app', import.meta.url).pathname,
		},
	},
	test: {
		environment: 'jsdom',
		include: ['src/**/*.test.ts'],
		globals: false,
	},
});
