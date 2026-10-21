<script lang="ts">
  import { fly } from 'svelte/transition';
  import { notify } from '$lib/stores/notify.svelte';
  import { CheckCircle, AlertTriangle, Info, XCircle, X } from 'lucide-svelte';

  const icons = {
    success: CheckCircle,
    error: XCircle,
    warning: AlertTriangle,
    info: Info
  };

  const styles: Record<string, string> = {
    success: 'border-[var(--status-success)]/60 bg-[var(--status-success)]/10 text-[var(--status-success)]',
    error: 'border-[var(--status-danger)]/60 bg-[var(--status-danger)]/10 text-[var(--status-danger)]',
    warning: 'border-[var(--status-warning)]/60 bg-[var(--status-warning)]/10 text-[var(--status-warning)]',
    info: 'border-[var(--accent-primary)]/60 bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]'
  };
</script>

<!-- Toasts: top-anchored on mobile so they clear the bottom nav area. -->
<div
  class="fixed inset-x-3 top-3 sm:inset-x-auto sm:right-4 sm:top-4 z-[100] flex flex-col gap-2 pointer-events-none"
  aria-live="polite"
  aria-atomic="false"
>
  {#each notify.toasts as toast (toast.id)}
    {@const Icon = icons[toast.kind]}
    <div
      class="pointer-events-auto flex items-start gap-2 border chamfer-sm px-3 py-2.5 shadow-lg backdrop-blur-md bg-[var(--bg-surface)] {styles[toast.kind]}"
      role="status"
      transition:fly={{ y: -12, duration: 180 }}
    >
      <Icon class="w-4 h-4 shrink-0 mt-0.5" />
      <p class="flex-1 text-xs font-code leading-snug text-[var(--text-primary)] break-words">
        {toast.message}
      </p>
      <button
        type="button"
        onclick={() => notify.dismiss(toast.id)}
        class="p-1 -m-1 shrink-0 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
        aria-label="Dismiss notification"
      >
        <X class="w-3.5 h-3.5" />
      </button>
    </div>
  {/each}
</div>

<!-- Confirmation dialog (non-blocking replacement for window.confirm). -->
{#if notify.confirmRequest}
  {@const req = notify.confirmRequest}
  <div class="fixed inset-0 z-[110] flex items-end sm:items-center justify-center p-0 sm:p-4">
    <button
      type="button"
      class="absolute inset-0 bg-black/70 backdrop-blur-sm cursor-default"
      aria-label="Cancel"
      onclick={() => notify.settle(false)}
    ></button>

    <div
      class="relative w-full sm:max-w-md border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer p-4 sm:p-5 space-y-3 shadow-2xl"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      <h2 id="confirm-title" class="font-hud font-bold text-sm text-[var(--text-primary)]">
        {req.title}
      </h2>
      <p class="text-xs font-code text-[var(--text-muted)] leading-relaxed break-words">
        {req.message}
      </p>
      <div class="flex justify-end gap-2 pt-2">
        <button
          type="button"
          onclick={() => notify.settle(false)}
          class="px-3 py-2.5 text-xs font-hud border border-[var(--border-color)] text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] chamfer-sm"
        >
          {req.cancelLabel}
        </button>
        <button
          type="button"
          onclick={() => notify.settle(true)}
          class="px-3 py-2.5 text-xs font-hud font-bold border chamfer-sm {req.destructive
            ? 'border-[var(--status-danger)] text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10'
            : 'border-[var(--accent-primary)] text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10'}"
        >
          {req.confirmLabel}
        </button>
      </div>
    </div>
  </div>
{/if}
