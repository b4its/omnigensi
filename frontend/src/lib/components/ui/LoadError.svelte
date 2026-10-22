<script lang="ts">
  /**
   * Consistent load-failure surface.
   *
   * Pages used to swallow fetch errors into `console.error`, which made an
   * outage indistinguishable from an empty system ("no agents yet"). Every
   * page now renders this instead so the user sees the real reason and can
   * retry.
   */
  import { AlertTriangle, RefreshCw } from 'lucide-svelte';

  interface Props {
    message: string;
    title?: string;
    retrying?: boolean;
    onRetry?: () => void;
  }

  let {
    message,
    title = 'FAILED TO LOAD DATA',
    retrying = false,
    onRetry
  }: Props = $props();
</script>

<div
  class="flex flex-wrap items-center justify-between gap-3 border border-[var(--status-danger)]/60 bg-[var(--status-danger)]/10 chamfer-sm px-3 py-3 font-code text-xs text-[var(--status-danger)]"
  role="alert"
>
  <span class="flex items-start gap-2 min-w-0">
    <AlertTriangle class="w-4 h-4 shrink-0 mt-0.5" />
    <span class="min-w-0">
      <span class="block font-hud font-bold text-[11px]">{title}</span>
      <span class="block break-words opacity-90 mt-0.5">{message}</span>
    </span>
  </span>

  {#if onRetry}
    <button
      type="button"
      onclick={onRetry}
      disabled={retrying}
      class="shrink-0 inline-flex items-center gap-1.5 px-3 py-2.5 font-hud font-bold border border-current chamfer-sm disabled:opacity-50"
    >
      <RefreshCw class="w-3.5 h-3.5 {retrying ? 'animate-spin' : ''}" />
      <span>{retrying ? 'RETRYING...' : 'RETRY'}</span>
    </button>
  {/if}
</div>
