<script lang="ts">
  /**
   * Model workspace for a provider: auto-add models, pick the default and
   * test an actual chat response.
   *
   * Used in two places with different capabilities:
   *   - during registration (draft mode): discovers models using the
   *     *unsaved* base URL + key, without persisting anything
   *   - after saving / when editing: talks to the provider by id, so the
   *     selection and tests are persisted
   */
  import { api } from '$lib/api';
  import { notify } from '$lib/stores/notify.svelte';
  import { RefreshCw, Check, FlaskConical, Loader2, AlertTriangle } from 'lucide-svelte';

  interface Props {
    /** Provider id once persisted; null while still a draft. */
    providerId: string | null;
    /** Draft connection details, used when providerId is null. */
    draftBaseUrl?: string;
    draftApiKey?: string;
    draftProviderType?: string;
    /** Invoked when the operator picks a model that should be persisted. */
    onDefaultModelChange?: (modelId: string) => void;
    /** Currently selected model id. */
    selectedModelId?: string | null;
  }

  let {
    providerId,
    draftBaseUrl = '',
    draftApiKey = '',
    draftProviderType = 'custom',
    onDefaultModelChange,
    selectedModelId = null
  }: Props = $props();

  interface ModelRow {
    model_id: string;
    display_name?: string | null;
    context_length?: number | null;
    is_default?: boolean;
    is_available?: boolean;
  }

  let models = $state<ModelRow[]>([]);
  let discovering = $state(false);
  let discoverError = $state<string | null>(null);
  let discoveredCount = $state<number | null>(null);
  let search = $state('');
  let testing = $state(false);
  let testResult = $state<{
    ok: boolean;
    model_id: string;
    response_text?: string | null;
    latency_ms: number;
    prompt_tokens?: number | null;
    completion_tokens?: number | null;
    error?: string | null;
  } | null>(null);
  let testPrompt = $state('Reply with the single word: OK');
  let savingDefault = $state<string | null>(null);

  const filtered = $derived(
    search.trim()
      ? models.filter(
          (m) =>
            m.model_id.toLowerCase().includes(search.toLowerCase()) ||
            (m.display_name ?? '').toLowerCase().includes(search.toLowerCase())
        )
      : models
  );

  const activeModelId = $derived(selectedModelId ?? models.find((m) => m.is_default)?.model_id ?? null);

  /** Loads models already stored for a saved provider. */
  async function loadStored() {
    if (!providerId) return;
    try {
      const rows = await api.getProviderModelRegistry(providerId);
      models = rows.map((r) => ({
        model_id: r.model_id,
        display_name: r.display_name,
        context_length: r.context_length,
        is_default: r.is_default,
        is_available: r.is_available
      }));
    } catch (err) {
      // A brand-new provider simply has no stored models yet.
      models = [];
    }
  }

  /**
   * Auto-adds models.
   * For a draft we call the live endpoint with the unsaved credentials; once
   * saved we use the sync endpoint so the results persist.
   */
  async function discoverModels() {
    discovering = true;
    discoverError = null;
    discoveredCount = null;
    testResult = null;
    try {
      if (providerId) {
        const res = await api.syncProviderModels(providerId);
        if (!res.ok) {
          discoverError = res.error ?? 'Could not reach the provider';
          notify.error(`Model discovery failed: ${discoverError}`);
          models = [];
          return;
        }
        discoveredCount = res.discovered;
        await loadStored();
        notify.success(
          `Models synced: ${res.added} added, ${res.updated} updated (${res.total_stored} total)`
        );
        const fallback = models.find((m) => m.is_default)?.model_id ?? models[0]?.model_id;
        if (fallback) onDefaultModelChange?.(fallback);
      } else {
        // Draft mode: probe without saving. Uses the public test endpoint on a
        // throwaway basis by asking the backend to list models for the URL.
        const res = await api.discoverDraftModels({
          base_url: draftBaseUrl,
          api_key: draftApiKey,
          provider_type: draftProviderType
        });
        if (!res.ok) {
          discoverError = res.error ?? 'Could not reach the provider';
          notify.error(`Model discovery failed: ${discoverError}`);
          models = [];
          return;
        }
        discoveredCount = res.models.length;
        models = res.models.map((m) => ({
          model_id: m.id,
          display_name: m.name,
          context_length: m.context_length,
          is_default: false,
          is_available: true
        }));
        if (models[0]) {
          models[0].is_default = true;
          onDefaultModelChange?.(models[0].model_id);
        }
        notify.success(`Discovered ${res.models.length} models`);
      }
    } catch (err) {
      discoverError = err instanceof Error ? err.message : 'Model discovery failed';
      notify.fromError(err, 'Model discovery failed');
      models = [];
    } finally {
      discovering = false;
    }
  }

  async function chooseModel(modelId: string) {
    if (!providerId) {
      models = models.map((m) => ({ ...m, is_default: m.model_id === modelId }));
      onDefaultModelChange?.(modelId);
      return;
    }
    savingDefault = modelId;
    try {
      await api.setDefaultProviderModel(providerId, modelId);
      models = models.map((m) => ({ ...m, is_default: m.model_id === modelId }));
      onDefaultModelChange?.(modelId);
      notify.success(`Default model set to ${modelId}`);
    } catch (err) {
      notify.fromError(err, 'Could not set the default model');
    } finally {
      savingDefault = null;
    }
  }

  async function runChatTest() {
    if (!activeModelId) {
      notify.warning('Select a model first.');
      return;
    }
    testing = true;
    testResult = null;
    try {
      if (providerId) {
        const res = await api.testProviderChat(providerId, activeModelId, testPrompt);
        testResult = res;
        if (res.ok) notify.success(`Model responded in ${res.latency_ms}ms`);
        else notify.error(`Test failed: ${res.error ?? 'unknown error'}`);
      } else {
        const res = await api.testDraftChat({
          base_url: draftBaseUrl,
          api_key: draftApiKey,
          provider_type: draftProviderType,
          model_id: activeModelId,
          prompt: testPrompt
        });
        testResult = res;
        if (res.ok) notify.success(`Model responded in ${res.latency_ms}ms`);
        else notify.error(`Test failed: ${res.error ?? 'unknown error'}`);
      }
    } catch (err) {
      notify.fromError(err, 'Model test failed');
    } finally {
      testing = false;
    }
  }

  $effect(() => {
    // Load stored models whenever the panel is bound to a saved provider.
    if (providerId) void loadStored();
  });
</script>

<div class="space-y-3 font-code text-xs">
  <div class="flex flex-wrap items-center justify-between gap-2">
    <span class="uppercase font-bold text-[var(--text-muted)]">Models</span>
    <button
      type="button"
      onclick={discoverModels}
      disabled={discovering || !draftBaseUrl && !providerId}
      class="inline-flex items-center gap-1.5 px-3 py-2 font-hud text-[11px] border border-[var(--accent-primary)] text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 chamfer-sm disabled:opacity-40 disabled:cursor-not-allowed"
    >
      {#if discovering}
        <Loader2 class="w-3.5 h-3.5 animate-spin" />
        <span>DISCOVERING...</span>
      {:else}
        <RefreshCw class="w-3.5 h-3.5" />
        <span>AUTO-ADD MODELS</span>
      {/if}
    </button>
  </div>

  {#if discoverError}
    <div class="flex items-start gap-2 border border-[var(--status-danger)]/60 bg-[var(--status-danger)]/10 px-2.5 py-2 text-[var(--status-danger)]">
      <AlertTriangle class="w-4 h-4 shrink-0 mt-0.5" />
      <span class="break-words">{discoverError}</span>
    </div>
  {/if}

  {#if discoveredCount !== null && !discoverError}
    <p class="text-[10px] text-[var(--text-muted)]">
      {discoveredCount} models available{providerId ? ' and stored' : ' (not saved yet)'}.
      Pick the one to use and test it below.
    </p>
  {/if}

  {#if models.length > 0}
    <input
      type="text"
      bind:value={search}
      placeholder={`Filter ${models.length} models...`}
      class="w-full px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
    />

    <div class="max-h-48 overflow-y-auto border border-[var(--border-color)] divided">
      {#each filtered as m (m.model_id)}
        <button
          type="button"
          onclick={() => chooseModel(m.model_id)}
          disabled={savingDefault === m.model_id}
          class="w-full flex items-center justify-between gap-2 px-2.5 py-2 text-left border-b border-[var(--border-color)]/40 last:border-b-0 transition-colors {m.model_id === activeModelId ? 'bg-[var(--accent-primary)]/15' : 'hover:bg-[var(--bg-elevated)]'}"
        >
          <span class="min-w-0 flex-1">
            <span class="block truncate text-[11px] {m.model_id === activeModelId ? 'text-[var(--accent-primary)] font-bold' : 'text-[var(--text-primary)]'}">
              {m.model_id}
            </span>
            <span class="block text-[10px] text-[var(--text-muted)] truncate">
              {m.display_name && m.display_name !== m.model_id ? m.display_name : ''}
              {#if m.context_length}· {(m.context_length / 1000).toFixed(0)}k ctx{/if}
              {#if m.is_available === false}· unavailable{/if}
            </span>
          </span>
          {#if m.model_id === activeModelId}
            <span class="shrink-0 flex items-center gap-1 text-[10px] font-bold text-[var(--accent-primary)]">
              {#if savingDefault === m.model_id}
                <Loader2 class="w-3 h-3 animate-spin" />
              {:else}
                <Check class="w-3.5 h-3.5" />
              {/if}
              SELECTED
            </span>
          {/if}
        </button>
      {/each}

      {#if filtered.length === 0}
        <p class="px-2.5 py-3 text-[10px] text-[var(--text-muted)] italic">
          No model matches "{search}".
        </p>
      {/if}
    </div>

    <!-- Response test -->
    <div class="pt-2 border-t border-[var(--border-color)]/50 space-y-2">
      <div class="flex items-center justify-between">
        <span class="uppercase font-bold text-[var(--text-muted)]">Test Response</span>
        {#if activeModelId}
          <span class="text-[10px] text-[var(--text-muted)] truncate max-w-[60%]">{activeModelId}</span>
        {/if}
      </div>
      <input
        type="text"
        bind:value={testPrompt}
        placeholder="Prompt to send"
        class="w-full px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
      />
      <button
        type="button"
        onclick={runChatTest}
        disabled={testing || !activeModelId}
        class="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2.5 font-hud text-[11px] font-bold border border-[var(--status-success)]/60 text-[var(--status-success)] hover:bg-[var(--status-success)]/10 chamfer-sm disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {#if testing}
          <Loader2 class="w-3.5 h-3.5 animate-spin" />
          <span>CALLING MODEL...</span>
        {:else}
          <FlaskConical class="w-3.5 h-3.5" />
          <span>SEND TEST REQUEST</span>
        {/if}
      </button>

      {#if testResult}
        <div
          class="border chamfer-sm px-2.5 py-2 space-y-1 {testResult.ok
            ? 'border-[var(--status-success)]/50 bg-[var(--status-success)]/10'
            : 'border-[var(--status-danger)]/50 bg-[var(--status-danger)]/10'}"
        >
          <div class="flex items-center justify-between text-[10px] font-bold">
            <span class={testResult.ok ? 'text-[var(--status-success)]' : 'text-[var(--status-danger)]'}>
              {testResult.ok ? 'RESPONSE OK' : 'REQUEST FAILED'}
            </span>
            <span class="text-[var(--text-muted)] font-normal">{testResult.latency_ms}ms</span>
          </div>

          {#if testResult.ok}
            <p class="text-[11px] text-[var(--text-primary)] whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
              {testResult.response_text}
            </p>
            {#if testResult.prompt_tokens != null}
              <p class="text-[10px] text-[var(--text-muted)]">
                tokens: {testResult.prompt_tokens} in / {testResult.completion_tokens ?? '?'} out
              </p>
            {/if}
          {:else}
            <p class="text-[11px] text-[var(--status-danger)] break-words">{testResult.error}</p>
          {/if}
        </div>
      {/if}
    </div>
  {:else if !discovering && discoveredCount === null}
    <p class="text-[10px] text-[var(--text-muted)] leading-relaxed">
      No models loaded. Use <span class="text-[var(--accent-primary)]">AUTO-ADD MODELS</span> to
      fetch this provider's model list, then select one and send a test request.
    </p>
  {/if}
</div>
