<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import { auth } from '$lib/stores/auth.svelte';
  import { notify } from '$lib/stores/notify.svelte';
  import { goto } from '$app/navigation';
  import CyberCard from '$lib/components/ui/CyberCard.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import LoadError from '$lib/components/ui/LoadError.svelte';
  import {
    KeyRound,
    ShieldCheck,
    Loader2,
    AlertTriangle,
    Server,
    Database,
    Cpu
  } from 'lucide-svelte';

  let currentPassword = $state('');
  let newPassword = $state('');
  let confirmPassword = $state('');
  let submitting = $state(false);
  let formError = $state<string | null>(null);

  let health = $state<{
    status: string;
    version: string;
    dependencies?: Record<string, string>;
  } | null>(null);
  let stats = $state<{ providers: number; agents: number; workflows: number } | null>(null);
  let loadError = $state<string | null>(null);
  let loadingInfo = $state(true);

  const MIN_LENGTH = 8;
  let revoking = $state(false);

  /** Invalidates every outstanding token without changing the password. */
  async function handleRevokeSessions() {
    const confirmed = await notify.confirm({
      title: 'SIGN OUT EVERYWHERE',
      message:
        'Every active session will be invalidated immediately, including this one. Continue?',
      confirmLabel: 'REVOKE ALL'
    });
    if (!confirmed) return;

    revoking = true;
    try {
      await api.revokeSessions();
      notify.success('All sessions revoked. Sign in again.');
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('omnigensi_session_token');
      }
      auth.token = null;
      auth.authenticated = false;
      goto('/login', { replaceState: true });
    } catch (err) {
      notify.fromError(err, 'Could not revoke sessions');
    } finally {
      revoking = false;
    }
  }

  const canSubmit = $derived(
    !submitting &&
      currentPassword.length > 0 &&
      newPassword.length >= MIN_LENGTH &&
      newPassword === confirmPassword &&
      newPassword !== currentPassword
  );

  async function loadInfo() {
    loadingInfo = true;
    loadError = null;
    try {
      const [h, s] = await Promise.all([api.checkHealth(), api.getStats()]);
      health = h as typeof health;
      stats = s;
    } catch (err) {
      loadError = err instanceof Error ? err.message : 'Unable to load system info';
    } finally {
      loadingInfo = false;
    }
  }

  async function handleChangePassword(event: SubmitEvent) {
    event.preventDefault();
    if (!canSubmit) return;

    submitting = true;
    formError = null;
    try {
      await api.changePassword(currentPassword, newPassword);
      notify.success('Password changed. Sign in again with the new password.');
      // The backend clears the cookie and invalidates the session.
      auth.token = null;
      auth.authenticated = false;
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('omnigensi_session_token');
      }
      goto('/login', { replaceState: true });
    } catch (err) {
      formError = err instanceof Error ? err.message : 'Could not change the password';
    } finally {
      submitting = false;
    }
  }

  onMount(loadInfo);
</script>

<div class="space-y-6">
  <div class="border-b border-[var(--border-color)] pb-4">
    <div class="text-[11px] font-code text-[var(--accent-primary)] uppercase tracking-wider">
      MODULE // 07
    </div>
    <h1 class="text-xl md:text-2xl font-hud font-black text-[var(--text-primary)]">
      SETTINGS & SYSTEM STATUS
    </h1>
    <p class="text-xs text-[var(--text-muted)] mt-1">
      Rotate the operator password and inspect dependency health.
    </p>
  </div>

  {#if loadError}
    <LoadError message={loadError} onRetry={loadInfo} retrying={loadingInfo} />
  {/if}

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <!-- Password rotation -->
    <CyberCard code="SECURITY.01" title="OPERATOR PASSWORD">
      <div class="space-y-3 font-code text-xs">
        {#if !auth.authEnabled}
          <div class="flex items-start gap-2 border border-[var(--status-warning)]/50 bg-[var(--status-warning)]/10 px-2.5 py-2 text-[11px] text-[var(--status-warning)]">
            <AlertTriangle class="w-4 h-4 shrink-0 mt-0.5" />
            <span>Authentication is disabled, so there is no password to change.</span>
          </div>
        {:else}
          <p class="text-[11px] text-[var(--text-muted)] leading-relaxed">
            A single password protects the whole instance. Changing it signs you out
            everywhere, so keep it somewhere safe.
          </p>

          {#if formError}
            <div
              class="flex items-start gap-2 border border-[var(--status-danger)]/60 bg-[var(--status-danger)]/10 px-2.5 py-2 text-[11px] text-[var(--status-danger)]"
              role="alert"
            >
              <AlertTriangle class="w-4 h-4 shrink-0 mt-0.5" />
              <span class="break-words">{formError}</span>
            </div>
          {/if}

          <form onsubmit={handleChangePassword} class="space-y-3">
            <label class="block">
              <span class="block text-[10px] uppercase text-[var(--text-muted)] mb-1">
                Current password
              </span>
              <input
                type="password"
                bind:value={currentPassword}
                autocomplete="current-password"
                class="w-full px-3 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              />
            </label>

            <label class="block">
              <span class="block text-[10px] uppercase text-[var(--text-muted)] mb-1">
                New password (min {MIN_LENGTH} characters)
              </span>
              <input
                type="password"
                bind:value={newPassword}
                autocomplete="new-password"
                class="w-full px-3 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              />
            </label>

            <label class="block">
              <span class="block text-[10px] uppercase text-[var(--text-muted)] mb-1">
                Confirm new password
              </span>
              <input
                type="password"
                bind:value={confirmPassword}
                autocomplete="new-password"
                class="w-full px-3 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              />
            </label>

            {#if newPassword && newPassword.length < MIN_LENGTH}
              <p class="text-[10px] text-[var(--status-warning)]">
                Too short: {newPassword.length}/{MIN_LENGTH}.
              </p>
            {:else if confirmPassword && newPassword !== confirmPassword}
              <p class="text-[10px] text-[var(--status-danger)]">Passwords do not match.</p>
            {:else if newPassword && newPassword === currentPassword}
              <p class="text-[10px] text-[var(--status-warning)]">
                The new password must differ from the current one.
              </p>
            {/if}

            <CyberButton variant="primary" type="submit" disabled={!canSubmit} class="w-full py-3">
              {#if submitting}
                <Loader2 class="w-4 h-4 animate-spin" />
                <span>UPDATING...</span>
              {:else}
                <KeyRound class="w-4 h-4" />
                <span>CHANGE PASSWORD</span>
              {/if}
            </CyberButton>
          </form>
        {/if}
      </div>
    </CyberCard>

    <!-- System status -->
    <CyberCard code="SYSTEM.02" title="SYSTEM STATUS">
      <div class="space-y-3 font-code text-xs">
        {#if loadingInfo}
          <div class="flex items-center gap-2 py-6 text-[var(--text-muted)]">
            <Loader2 class="w-4 h-4 animate-spin" />
            <span>READING SYSTEM STATE...</span>
          </div>
        {:else}
          <div class="flex items-center justify-between">
            <span class="flex items-center gap-1.5 text-[var(--text-muted)]">
              <ShieldCheck class="w-3.5 h-3.5" /> Backend
            </span>
            <span
              class="font-bold {health?.status === 'healthy'
                ? 'text-[var(--status-success)]'
                : 'text-[var(--status-danger)]'}"
            >
              {health?.status?.toUpperCase() ?? 'UNKNOWN'}
            </span>
          </div>

          <div class="flex items-center justify-between">
            <span class="text-[var(--text-muted)]">Version</span>
            <span class="text-[var(--text-primary)]">{health?.version ?? '—'}</span>
          </div>

          <div class="pt-2 border-t border-[var(--border-color)]/50 space-y-1.5">
            <div class="text-[10px] uppercase text-[var(--text-muted)]">Dependencies</div>
            {#each Object.entries(health?.dependencies ?? {}) as [name, state]}
              <div class="flex items-center justify-between">
                <span class="flex items-center gap-1.5 text-[var(--text-muted)]">
                  {#if name === 'database'}<Database class="w-3.5 h-3.5" />{:else}<Cpu class="w-3.5 h-3.5" />{/if}
                  {name}
                </span>
                <span
                  class="font-bold {state === 'ok'
                    ? 'text-[var(--status-success)]'
                    : 'text-[var(--status-danger)]'}"
                >
                  {state === 'ok' ? 'OK' : state}
                </span>
              </div>
            {/each}
          </div>

          {#if stats}
            <div class="pt-2 border-t border-[var(--border-color)]/50 grid grid-cols-3 gap-2 text-center">
              <div>
                <div class="text-lg font-hud font-black text-[var(--accent-primary)]">{stats.providers}</div>
                <div class="text-[10px] text-[var(--text-muted)]">PROVIDERS</div>
              </div>
              <div>
                <div class="text-lg font-hud font-black text-[var(--accent-primary)]">{stats.agents}</div>
                <div class="text-[10px] text-[var(--text-muted)]">AGENTS</div>
              </div>
              <div>
                <div class="text-lg font-hud font-black text-[var(--accent-primary)]">{stats.workflows}</div>
                <div class="text-[10px] text-[var(--text-muted)]">WORKFLOWS</div>
              </div>
            </div>
          {/if}

          <div class="pt-2 border-t border-[var(--border-color)]/50 space-y-2">
            <div class="text-[10px] uppercase text-[var(--text-muted)]">Sessions</div>
            <p class="text-[10px] text-[var(--text-muted)] leading-relaxed">
              Signing out already revokes tokens on the server. Use this if a device
              was lost and you want to kill every session at once.
            </p>
            <button
              type="button"
              onclick={handleRevokeSessions}
              disabled={revoking}
              class="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2.5 text-[10px] font-hud font-bold border border-[var(--status-danger)]/50 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 chamfer-sm disabled:opacity-40"
            >
              {#if revoking}
                <Loader2 class="w-3.5 h-3.5 animate-spin" />
                <span>REVOKING...</span>
              {:else}
                <span>SIGN OUT EVERYWHERE</span>
              {/if}
            </button>
          </div>

          <div class="flex items-center gap-1.5 pt-2 border-t border-[var(--border-color)]/50 text-[10px] text-[var(--text-muted)]">
            <Server class="w-3.5 h-3.5" />
            <span>Single-operator instance · no users or roles</span>
          </div>
        {/if}
      </div>
    </CyberCard>
  </div>
</div>
