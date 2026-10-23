<script lang="ts">
  /**
   * RibbonButton — the atomic tool control used across every ribbon tab.
   *
   * Commands run on `mousedown` (not `click`) and prevent the default so the
   * editor canvas keeps its text selection; a plain button steals focus and
   * collapses the caret before the command fires.
   */
  import type { Snippet, Component } from 'svelte';

  interface Props {
    title: string;
    active?: boolean;
    disabled?: boolean;
    onclick: () => void;
    children: Snippet;
    icon?: Component;
    label?: string;
    /** Lateral hint under the icon, Word-style. */
    hint?: string;
  }

  let {
    title,
    active = false,
    disabled = false,
    onclick,
    children,
    icon: Icon,
    label,
    hint,
  }: Props = $props();

  function handle(e: MouseEvent) {
    e.preventDefault();
    if (!disabled) onclick();
  }
</script>

<button
  type="button"
  title={title}
  aria-label={title}
  aria-pressed={active}
  {disabled}
  onmousedown={handle}
  class="group flex items-center justify-center gap-1.5 rounded-sm border transition-all duration-100 min-h-7 px-2 py-1 text-[var(--text-primary)]
    {active
      ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/20 text-[var(--accent-primary)] shadow-[0_0_8px_rgba(0,240,255,0.25)]'
      : 'border-transparent hover:border-[var(--border-color)] hover:bg-[var(--bg-elevated)]'}
    {disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}"
>
  {#if Icon}<Icon class="w-4 h-4 shrink-0" />{/if}
  {@render children()}
  {#if label}<span class="text-[11px] font-code">{label}</span>{/if}
  {#if hint}<span class="sr-only">{hint}</span>{/if}
</button>
