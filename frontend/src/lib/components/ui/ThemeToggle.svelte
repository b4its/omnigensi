<script lang="ts">
  import { themeStore } from '$lib/stores/theme.svelte';
  import { Sun, Moon, Tv } from 'lucide-svelte';
</script>

<!-- Compact on small screens (icon + short label), full labels from sm upwards. -->
<div class="flex items-center gap-1.5 sm:gap-2 shrink-0">
  <!-- Theme Mode Toggle -->
  <button
    type="button"
    onclick={() => themeStore.toggleTheme()}
    class="flex items-center gap-1.5 px-2 sm:px-3 py-1.5 text-xs font-hud rounded-sm border border-[var(--border-color)] bg-[var(--bg-surface)] hover:border-[var(--accent-primary)] text-[var(--text-primary)] transition-colors cursor-pointer"
    title="Switch Optical Mode (Cyber-Abyss / Mecha-Lab)"
    aria-label={themeStore.mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
  >
    {#if themeStore.mode === 'dark'}
      <Moon class="w-4 h-4 text-[var(--accent-primary)]" />
      <span class="hidden sm:inline tracking-wider">ABYSS [DARK]</span>
    {:else}
      <Sun class="w-4 h-4 text-[var(--accent-primary)]" />
      <span class="hidden sm:inline tracking-wider">MECHA [LIGHT]</span>
    {/if}
  </button>

  <!-- CRT Scanline Toggle -->
  <button
    type="button"
    onclick={() => themeStore.toggleCrt()}
    class="flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 text-xs font-code rounded-sm border transition-colors cursor-pointer {themeStore.crtScanlines ? 'border-[var(--status-success)] text-[var(--status-success)] bg-[var(--status-success)]/10' : 'border-[var(--border-color)] text-[var(--text-muted)] bg-[var(--bg-surface)]'}"
    title="Toggle CRT Scanline Overlay"
    aria-label="Toggle CRT scanline overlay"
  >
    <Tv class="w-4 h-4" />
    <span class="hidden sm:inline text-[10px] font-bold">CRT: {themeStore.crtScanlines ? 'ON' : 'OFF'}</span>
  </button>
</div>
