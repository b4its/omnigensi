<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title?: string;
    code?: string;
    variant?: 'default' | 'elevated' | 'active' | 'danger';
    class?: string;
    headerAction?: Snippet;
    children?: Snippet;
  }

  let {
    title,
    code,
    variant = 'default',
    class: customClass = '',
    headerAction,
    children,
  }: Props = $props();

  const variantBorder = {
    default: 'border-[var(--border-color)] bg-[var(--bg-surface)]',
    elevated: 'border-[var(--accent-secondary)]/50 bg-[var(--bg-elevated)]',
    active: 'border-[var(--accent-primary)] bg-[var(--bg-surface)] shadow-[var(--border-glow)]',
    danger: 'border-[var(--status-danger)] bg-[var(--bg-surface)] shadow-[0_0_12px_rgba(255,0,85,0.3)]',
  };
</script>

<div class="relative border transition-all duration-200 chamfer {variantBorder[variant]} {customClass}">
  <!-- Corner Accent Markers -->
  <div class="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-[var(--accent-primary)] pointer-events-none"></div>
  <div class="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-[var(--accent-primary)] pointer-events-none"></div>

  {#if title || code || headerAction}
    <div class="flex items-center justify-between px-4 py-2.5 border-b border-[var(--border-color)] bg-[var(--bg-elevated)]/40 text-xs">
      <div class="flex items-center gap-2">
        {#if code}
          <span class="font-code text-[var(--accent-primary)] font-semibold tracking-wider">[{code}]</span>
        {/if}
        {#if title}
          <span class="font-hud text-[var(--text-primary)] font-bold">{title}</span>
        {/if}
      </div>
      {#if headerAction}
        <div>
          {@render headerAction()}
        </div>
      {/if}
    </div>
  {/if}

  <div class="p-4">
    {@render children?.()}
  </div>
</div>
