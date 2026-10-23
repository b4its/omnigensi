<script lang="ts">
  /**
   * NavigationPane — Word's left-hand outline. Lists every heading with its
   * indentation and jumps the canvas to it; a live search filters the list.
   */
  import { collectHeadings } from './headings';
  import type { Heading } from './headings';
  import { X, ListTree } from 'lucide-svelte';

  interface Props {
    /** Re-read the outline. The parent bumps this counter after edits. */
    revision: number;
    getRoot: () => HTMLElement | undefined;
    onexit: () => void;
  }
  let { revision, getRoot, onexit }: Props = $props();

  let query = $state('');
  const headings = $derived.by<Heading[]>(() => {
    void revision;
    const root = getRoot();
    return root ? collectHeadings(root) : [];
  });
  const filtered = $derived(
    query.trim()
      ? headings.filter((h) => h.text.toLowerCase().includes(query.trim().toLowerCase()))
      : headings
  );

  function jump(h: Heading) {
    h.el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    const range = document.createRange();
    range.selectNodeContents(h.el);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
  }
</script>

<aside class="w-56 shrink-0 border-r border-[var(--border-color)] bg-[var(--bg-surface)] flex flex-col" aria-label="Panel navigasi">
  <div class="flex items-center justify-between px-3 py-2 border-b border-[var(--border-color)]">
    <span class="text-[10px] font-hud tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
      <ListTree class="w-3.5 h-3.5" /> NAVIGASI
    </span>
    <button type="button" onclick={onexit} class="text-[var(--text-muted)] hover:text-[var(--text-primary)]" aria-label="Tutup panel navigasi">
      <X class="w-3.5 h-3.5" />
    </button>
  </div>
  <div class="p-2 border-b border-[var(--border-color)]/60">
    <input
      bind:value={query}
      placeholder="Cari judul…"
      class="w-full px-2 py-1 text-[11px] font-code bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
      aria-label="Cari judul"
    />
  </div>
  <div class="overflow-y-auto flex-1 p-1">
    {#if filtered.length === 0}
      <p class="px-2 py-3 text-[10px] font-code text-[var(--text-muted)]">
        {headings.length === 0 ? 'Belum ada judul. Terapkan gaya Heading.' : 'Tidak ada judul yang cocok.'}
      </p>
    {:else}
      {#each filtered as h (h.id)}
        <button
          type="button"
          onclick={() => jump(h)}
          class="block w-full text-left px-2 py-1 rounded-sm text-[11px] text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] truncate"
          style:padding-left="{4 + (h.level - 1) * 12}px"
        >
          {h.text}
        </button>
      {/each}
    {/if}
  </div>
</aside>
