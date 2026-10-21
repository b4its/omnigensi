<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { auth } from '$lib/stores/auth.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import { KeyRound, Loader2, ShieldCheck, AlertTriangle, Eye, EyeOff } from 'lucide-svelte';

  let password = $state('');
  let reveal = $state(false);
  let submitting = $state(false);
  let localError = $state<string | null>(null);

  const redirectTo = $derived(
    page.url.searchParams.get('redirect') || '/'
  );

  let passwordInput: HTMLInputElement | undefined = $state();

  onMount(async () => {
    // Focus explicitly rather than via the discouraged autofocus attribute.
    queueMicrotask(() => passwordInput?.focus());
    // Already signed in (valid cookie or stored token) -> skip the prompt.
    if (auth.authenticated === null) await auth.check();
    if (auth.authenticated) goto(redirectTo, { replaceState: true });
  });

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    if (!password.trim() || submitting) return;

    submitting = true;
    localError = null;
    const ok = await auth.login(password);
    submitting = false;

    if (ok) {
      password = '';
      goto(redirectTo, { replaceState: true });
    } else {
      localError = auth.error ?? 'Incorrect password';
      password = '';
    }
  }
</script>

<svelte:head>
  <title>Sign in // Omnigesi</title>
</svelte:head>

<div class="min-h-[70dvh] flex items-center justify-center px-4 py-8">
  <div class="w-full max-w-sm space-y-5">
    <!-- Brand -->
    <div class="text-center space-y-2">
      <div
        class="w-12 h-12 mx-auto chamfer-sm bg-[var(--accent-primary)] text-[var(--on-accent)] flex items-center justify-center font-hud font-black text-lg shadow-[var(--border-glow)]"
      >
        Ω
      </div>
      <h1 class="font-hud font-black text-lg tracking-widest text-[var(--text-primary)]">
        OMNIGENSI
      </h1>
      <p class="text-[10px] font-code tracking-wider text-[var(--accent-primary)]">
        AIaaS // OPERATOR AUTHENTICATION
      </p>
    </div>

    <div class="border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer p-5 space-y-4">
      {#if auth.loading && auth.authenticated === null}
        <div class="flex items-center justify-center gap-2 py-6 text-xs font-code text-[var(--text-muted)]">
          <Loader2 class="w-4 h-4 animate-spin" />
          <span>CHECKING SESSION...</span>
        </div>
      {:else if !auth.authEnabled}
        <div class="flex items-start gap-2 border border-[var(--status-warning)]/50 bg-[var(--status-warning)]/10 px-3 py-2.5 text-[11px] font-code text-[var(--status-warning)]">
          <AlertTriangle class="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            Authentication is disabled on this server (AUTH_ENABLED=false). No password is
            required.
          </span>
        </div>
        <CyberButton variant="primary" class="w-full py-3" onclick={() => goto(redirectTo, { replaceState: true })}>
          <ShieldCheck class="w-4 h-4" />
          <span>CONTINUE TO CONSOLE</span>
        </CyberButton>
      {:else}
        <p class="text-[11px] font-code text-[var(--text-muted)] leading-relaxed">
          This instance is protected by a single operator password.
        </p>

        {#if localError}
          <div
            class="flex items-start gap-2 border border-[var(--status-danger)]/60 bg-[var(--status-danger)]/10 px-2.5 py-2 text-[11px] font-code text-[var(--status-danger)]"
            role="alert"
          >
            <AlertTriangle class="w-4 h-4 shrink-0 mt-0.5" />
            <span class="break-words">{localError}</span>
          </div>
        {/if}

        <form onsubmit={handleSubmit} class="space-y-3">
          <label class="block font-code text-xs">
            <span class="block text-[10px] uppercase text-[var(--text-muted)] mb-1">Password</span>
            <span class="relative block">
              <KeyRound class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                type={reveal ? 'text' : 'password'}
                bind:value={password}
                bind:this={passwordInput}
                autocomplete="current-password"
                placeholder="Enter operator password"
                class="w-full pl-9 pr-10 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              />
              <button
                type="button"
                onclick={() => (reveal = !reveal)}
                class="absolute right-1 top-1/2 -translate-y-1/2 p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                aria-label={reveal ? 'Hide password' : 'Show password'}
              >
                {#if reveal}
                  <EyeOff class="w-4 h-4" />
                {:else}
                  <Eye class="w-4 h-4" />
                {/if}
              </button>
            </span>
          </label>

          <CyberButton
            variant="primary"
            type="submit"
            class="w-full py-3"
            disabled={submitting || !password.trim()}
          >
            {#if submitting}
              <Loader2 class="w-4 h-4 animate-spin" />
              <span>VERIFYING...</span>
            {:else}
              <ShieldCheck class="w-4 h-4" />
              <span>AUTHENTICATE</span>
            {/if}
          </CyberButton>
        </form>
      {/if}
    </div>

    <p class="text-center text-[10px] font-code text-[var(--text-muted)]">
      Session lasts 7 days. Sign out from the header when finished.
    </p>
  </div>
</div>
