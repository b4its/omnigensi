<script lang="ts">
  /**
   * CommandSearch — the "Tell Me what you want to do" box. Mirrors Wordcraft's
   * command search: every ribbon action is searchable by name, tab or keyword
   * and runs the same code path the ribbon button does.
   */
  import { commandRegistry } from './commandRegistry';
  import type { Command } from './commandRegistry';
  import { Search, CornerDownLeft, X } from 'lucide-svelte';

  interface Props {
    open: boolean;
    onexit: () => void;
  }
  let { open, onexit }: Props = $props();

  let query = $state('');
  let cursor = $state(0);
  const results = $derived(commandRegistry.search(query));

  $effect(() => {
    if (open) {
      query = '';
      cursor = 0;
    }
  });

  function run(cmd: Command) {
    onexit();
    // Defer so the dialog closes before the command mutates the selection.
    setTimeout(() => cmd.run(), 0);
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      cursor = Math.min(results.length - 1, cursor + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      cursor = Math.max(0, cursor - 1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const target = results[cursor];
      if (target) run(target);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onexit();
    }
  }
</script>

{#if open}
  <div class="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-[12vh]" role="presentation" onpointerdown={onexit}>
    <div
      class="w-full max-w-xl border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer shadow-2xl"
      onpointerdown={(e) => e.stopPropagation()}
      role="dialog"
      aria-modal="true"
      aria-label="Cari perintah"
      tabindex="-1"
    >
      <div class="flex items-center gap-2 px-3 py-2 border-b border-[var(--border-color)]">
        <Search class="w-4 h-4 text-[var(--accent-primary)]" />
        <input
          bind:value={query}
          onkeydown={onKey}
          oninput={() => (cursor = 0)}
          placeholder="Ketik perintah — mis. 'tebal', 'daftar isi', 'margin'…"
          class="flex-1 bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
          aria-label="Cari perintah"
        />
        <button type="button" onclick={onexit} class="text-[var(--text-muted)] hover:text-[var(--text-primary)]" aria-label="Tutup pencarian">
          <X class="w-4 h-4" />
        </button>
      </div>
      <div class="max-h-[50vh] overflow-y-auto py-1">
        {#if results.length === 0}
          <p class="px-3 py-4 text-[11px] font-code text-[var(--text-muted)]">Tidak ada perintah yang cocok.</p>
        {:else}
          {#each results.slice(0, 40) as cmd, i (cmd.id)}
            <button
              type="button"
              onclick={() => run(cmd)}
              onmouseenter={() => (cursor = i)}
              class="w-full flex items-center justify-between gap-3 px-3 py-1.5 text-left transition-colors
                {i === cursor ? 'bg-[var(--accent-primary)]/15' : 'hover:bg-[var(--bg-elevated)]'}"
            >
              <span class="flex items-center gap-2 min-w-0">
                <span class="text-[10px] font-code text-[var(--accent-primary)] shrink-0">{cmd.tab}</span>
                <span class="text-[12px] text-[var(--text-primary)] truncate">{cmd.label}</span>
              </span>
              <span class="flex items-center gap-2 shrink-0">
                {#if cmd.shortcut}<kbd class="text-[9px] font-code px-1 border border-[var(--border-color)] rounded-sm text-[var(--text-muted)]">{cmd.shortcut}</kbd>{/if}
                {#if i === cursor}<CornerDownLeft class="w-3 h-3 text-[var(--accent-primary)]" />{/if}
              </span>
            </button>
          {/each}
        {/if}
      </div>
      <div class="px-3 py-1.5 border-t border-[var(--border-color)] text-[9px] font-code text-[var(--text-muted)]">
        {results.length} perintah · ↑↓ pilih · Enter jalankan · Esc tutup
      </div>
    </div>
  </div>
{/if}
