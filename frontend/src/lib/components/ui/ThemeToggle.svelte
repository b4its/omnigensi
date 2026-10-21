<script lang="ts">
  import { themeStore } from '$lib/stores/theme.svelte';
  import { Sun, Moon, Monitor, Tv } from 'lucide-svelte';
</script>

<div class="flex items-center gap-2">
  <!-- Theme Mode Toggle -->
  <button
    type="button"
    onclick={() => themeStore.toggleTheme()}
    class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-hud rounded-sm border border-[var(--border-color)] bg-[var(--bg-surface)] hover:border-[var(--accent-primary)] text-[var(--text-primary)] transition-colors cursor-pointer"
    title="Switch Optical Mode (Cyber-Abyss / Mecha-Lab)"
  >
    {#if themeStore.mode === 'dark'}
      <Moon class="w-3.5 h-3.5 text-[var(--accent-primary)]" />
      <span class="tracking-wider">ABYSS [DARK]</span>
    {:else}
      <Sun class="w-3.5 h-3.5 text-[var(--accent-primary)]" />
      <span class="tracking-wider">MECHA [LIGHT]</span>
    {/if}
  </button>

  <!-- CRT Scanline Toggle -->
  <button
    type="button"
    onclick={() => themeStore.toggleCrt()}
    class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-code rounded-sm border transition-colors cursor-pointer {themeStore.crtScanlines ? 'border-[var(--status-success)] text-[var(--status-success)] bg-[var(--status-success)]/10' : 'border-[var(--border-color)] text-[var(--text-muted)] bg-[var(--bg-surface)]'}"
    title="Toggle CRT Scanline Overlay"
  >
    <Tv class="w-3.5 h-3.5" />
    <span class="text-[10px] font-bold">CRT: {themeStore.crtScanlines ? 'ON' : 'OFF'}</span>
  </button>
</div>
