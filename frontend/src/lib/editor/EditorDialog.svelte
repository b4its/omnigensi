<script lang="ts">
  /**
   * EditorDialog — the one modal shell every editor dialog uses (find &
   * replace, insert link, insert image, font, paragraph, page setup,
   * captions, citations, watermark, equation, macro…). Centralising the
   * markup keeps the focus trap, the escape key and the chamfered HUD styling
   * consistent across the ~20 dialogs the ribbon can open.
   */
  import type { Snippet } from 'svelte';
  import { X } from 'lucide-svelte';

  interface Props {
    title: string;
    subtitle?: string;
    width?: string;
    onexit: () => void;
    children: Snippet;
    footer?: Snippet;
  }
  let { title, subtitle, width = 'max-w-md', onexit, children, footer }: Props = $props();

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      onexit();
    }
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="presentation" onpointerdown={onexit}>
  <div
    class="w-full {width} border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer p-4 shadow-2xl max-h-[90vh] overflow-y-auto"
    onpointerdown={(e) => e.stopPropagation()}
    role="dialog"
    aria-modal="true"
    aria-label={title}
    tabindex="-1"
  >
    <div class="flex items-start justify-between mb-3 gap-3">
      <div>
        <h3 class="font-hud text-sm text-[var(--text-primary)]">{title}</h3>
        {#if subtitle}<p class="text-[10px] font-code text-[var(--text-muted)] mt-0.5">{subtitle}</p>{/if}
      </div>
      <button type="button" onclick={onexit} class="text-[var(--text-muted)] hover:text-[var(--text-primary)]" aria-label="Tutup">
        <X class="w-4 h-4" />
      </button>
    </div>
    {@render children()}
    {#if footer}
      <div class="mt-4">{@render footer()}</div>
    {/if}
  </div>
</div>
