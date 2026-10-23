<script lang="ts">
  /**
   * StylesPane — Word's floating Styles pane: every style in the document plus
   * the built-in gallery, with a live preview of each style's formatting.
   */
  import { applyStyle, BUILTIN_STYLES, loadCustomStyles } from './styles';
  import type { DocStyle } from './styles';
  import { X } from 'lucide-svelte';

  interface Props {
    activeStyle: string;
    onexit: () => void;
  }
  let { activeStyle, onexit }: Props = $props();
  const all = $derived([...BUILTIN_STYLES, ...loadCustomStyles()]);

  function previewCss(s: DocStyle): string {
    return Object.entries(s.css)
      .map(([k, v]) => `${k}:${v}`)
      .join(';');
  }
</script>

<aside
  class="w-64 shrink-0 border-l border-[var(--border-color)] bg-[var(--bg-surface)] flex flex-col"
  aria-label="Panel gaya"
>
  <div class="flex items-center justify-between px-3 py-2 border-b border-[var(--border-color)]">
    <span class="text-[10px] font-hud tracking-wider text-[var(--text-muted)]">PANEL GAYA</span>
    <button type="button" onclick={onexit} class="text-[var(--text-muted)] hover:text-[var(--text-primary)]" aria-label="Tutup panel gaya">
      <X class="w-3.5 h-3.5" />
    </button>
  </div>
  <div class="overflow-y-auto flex-1 p-2 space-y-1">
    {#each all as style (style.name)}
      <button
        type="button"
        onclick={() => {
          applyStyle(style);
          activeStyle = style.name;
        }}
        class="w-full text-left px-2 py-1.5 rounded-sm border transition-colors
          {activeStyle === style.name
            ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/10'
            : 'border-transparent hover:bg-[var(--bg-elevated)]'}"
      >
        <div class="text-[11px] font-code text-[var(--text-primary)]">{style.name}</div>
        <div class="text-[12px] truncate" style={previewCss(style)}>{style.preview}</div>
      </button>
    {/each}
  </div>
</aside>
