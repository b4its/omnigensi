<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    variant?: 'primary' | 'cobalt' | 'danger' | 'ghost' | 'outline';
    size?: 'sm' | 'md' | 'lg';
    disabled?: boolean;
    type?: 'button' | 'submit' | 'reset';
    onclick?: (e: MouseEvent) => void;
    children?: Snippet;
    class?: string;
  }

  let {
    variant = 'primary',
    size = 'md',
    disabled = false,
    type = 'button',
    onclick,
    children,
    class: customClass = '',
  }: Props = $props();

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base font-semibold',
  };

  const variantClasses = {
    primary: 'bg-[var(--accent-primary)] text-[var(--on-accent)] font-bold hover:brightness-110 active:scale-[0.98] shadow-[0_0_12px_rgba(0,240,255,0.4)]',
    cobalt: 'bg-[var(--accent-secondary)] text-white font-medium hover:brightness-110 active:scale-[0.98] shadow-[0_0_10px_rgba(0,102,255,0.4)]',
    danger: 'bg-[var(--status-danger)] text-white font-bold hover:brightness-110 active:scale-[0.98]',
    outline: 'border border-[var(--accent-primary)] text-[var(--accent-primary)] bg-transparent hover:bg-[var(--accent-primary)]/10 active:scale-[0.98]',
    ghost: 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] bg-transparent',
  };
</script>

<button
  {type}
  {disabled}
  {onclick}
  class="font-hud tracking-wider transition-all duration-150 inline-flex items-center justify-center gap-2 chamfer-sm cursor-pointer select-none disabled:opacity-50 disabled:cursor-not-allowed {sizeClasses[size]} {variantClasses[variant]} {customClass}"
>
  {@render children?.()}
</button>
