<script lang="ts">
  /**
   * RibbonGroup — a labelled cluster inside a ribbon tab (Word's
   * "Clipboard", "Font", "Paragraph" boxes). Renders a header caption and a
   * row of controls, with a hairline separator between groups.
   */
  import type { Snippet } from 'svelte';

  interface Props {
    label: string;
    children: Snippet;
    /** Stack children vertically instead of a single row. */
    column?: boolean;
  }

  let { label, children, column = false }: Props = $props();
</script>

<div class="flex flex-col justify-between px-2.5 border-r border-[var(--border-color)]/60 last:border-r-0">
  <div class="flex {column ? 'flex-col' : 'flex-row'} items-center gap-0.5 flex-1">
    {@render children()}
  </div>
  <div class="text-center text-[9px] font-code uppercase tracking-wide text-[var(--text-muted)] pt-0.5">
    {label}
  </div>
</div>
