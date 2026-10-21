<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import CyberCard from '$lib/components/ui/CyberCard.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import {
    Server,
    Plus,
    RefreshCw,
    Key,
    Trash2,
    CheckCircle,
    XCircle,
    ExternalLink,
    Search,
    Cpu,
  } from 'lucide-svelte';

  let providers = $state<any[]>([]);
  let loading = $state<boolean>(true);
  let showCreateModal = $state<boolean>(false);
  let syncLoading = $state<Record<string, boolean>>({});
  let selectedProviderModels = $state<{ providerName: string; models: any[] } | null>(null);
  let modelSearch = $state<string>('');

  // Form State
  let formName = $state<string>('');
  let formType = $state<string>('openrouter');
  let formBaseUrl = $state<string>('https://openrouter.ai/api/v1');
  let formApiKey = $state<string>('');
  let formError = $state<string>('');
  let formSubmitting = $state<boolean>(false);

  async function loadProviders() {
    try {
      loading = true;
      providers = await api.getProviders();
    } catch (e: any) {
      console.error(e);
    } finally {
      loading = false;
    }
  }

  onMount(loadProviders);

  async function handleCreateProvider(e: SubmitEvent) {
    e.preventDefault();
    if (!formName.trim() || !formBaseUrl.trim()) {
      formError = 'Please fill in Name and Base URL.';
      return;
    }

    formSubmitting = true;
    formError = '';
    try {
      await api.createProvider({
        name: formName,
        provider_type: formType,
        base_url: formBaseUrl,
        api_key: formApiKey,
        default_headers: {},
        is_active: true,
      });
      showCreateModal = false;
      formName = '';
      formApiKey = '';
      await loadProviders();
    } catch (err: any) {
      formError = err.message || 'Failed to register provider';
    } finally {
      formSubmitting = false;
    }
  }

  async function handleDeleteProvider(id: string, name: string) {
    if (!confirm(`Are you sure you want to delete provider '${name}'?`)) return;
    try {
      await api.deleteProvider(id);
      await loadProviders();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  }

  async function handleSyncModels(provider: any) {
    syncLoading[provider.id] = true;
    try {
      const models = await api.getProviderModels(provider.id);
      selectedProviderModels = {
        providerName: provider.name,
        models,
      };
    } catch (err: any) {
      alert(`Failed to fetch models: ${err.message}`);
    } finally {
      syncLoading[provider.id] = false;
    }
  }

  const filteredModels = $derived(
    selectedProviderModels?.models.filter(m =>
      m.id.toLowerCase().includes(modelSearch.toLowerCase()) ||
      (m.name && m.name.toLowerCase().includes(modelSearch.toLowerCase()))
    ) || []
  );
</script>

<div class="space-y-6">
  <!-- Header Bar -->
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[var(--border-color)] pb-4">
    <div>
      <div class="text-[11px] font-code text-[var(--accent-primary)] uppercase tracking-wider">
        MODULE // 02
      </div>
      <h1 class="text-xl md:text-2xl font-hud font-black text-[var(--text-primary)]">
        OMNIROUTER & LLM PROVIDER VAULT
      </h1>
      <p class="text-xs text-[var(--text-muted)] mt-1">
        Manage unified LLM gateways with hardware AES API key encryption and dynamic model discovery.
      </p>
    </div>

    <CyberButton variant="primary" onclick={() => showCreateModal = true}>
      <Plus class="w-4 h-4" />
      <span>REGISTER PROVIDER</span>
    </CyberButton>
  </div>

  <!-- Provider List -->
  {#if loading}
    <div class="text-center py-12 font-code text-xs text-[var(--text-muted)] animate-pulse">
      SCANNING LLM GATEWAY VAULTS...
    </div>
  {:else if providers.length === 0}
    <div class="border border-dashed border-[var(--border-color)] p-8 text-center chamfer space-y-3">
      <Server class="w-10 h-10 mx-auto text-[var(--text-muted)] opacity-50" />
      <div class="font-hud font-bold text-sm text-[var(--text-primary)]">NO PROVIDERS REGISTERED</div>
      <p class="text-xs text-[var(--text-muted)] max-w-md mx-auto">
        Add your first provider (OpenRouter, LiteLLM, OpenAI, or local Ollama) to start powering dynamic agents.
      </p>
      <CyberButton variant="primary" size="sm" onclick={() => showCreateModal = true}>
        REGISTER NEW PROVIDER
      </CyberButton>
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      {#each providers as prov (prov.id)}
        <CyberCard code={`VAULT.${prov.provider_type.toUpperCase()}`} title={prov.name}>
          <div class="space-y-3">
            <div class="flex items-center justify-between text-xs">
              <span class="text-[var(--text-muted)]">Type:</span>
              <span class="font-code font-bold uppercase text-[var(--accent-primary)]">
                {prov.provider_type}
              </span>
            </div>

            <div class="flex items-center justify-between text-xs">
              <span class="text-[var(--text-muted)]">Base URL:</span>
              <span class="font-code text-[var(--text-primary)] truncate max-w-[220px]" title={prov.base_url}>
                {prov.base_url}
              </span>
            </div>

            <div class="flex items-center justify-between text-xs">
              <span class="text-[var(--text-muted)]">Key Status:</span>
              <span class="flex items-center gap-1 font-code {prov.has_api_key ? 'text-[var(--status-success)]' : 'text-[var(--text-muted)]'}">
                <Key class="w-3.5 h-3.5" />
                {prov.has_api_key ? 'ENCRYPTED (AES-256)' : 'EMPTY / LOCAL'}
              </span>
            </div>

            <div class="pt-3 border-t border-[var(--border-color)]/40 flex items-center justify-between gap-2">
              <button
                type="button"
                disabled={syncLoading[prov.id]}
                onclick={() => handleSyncModels(prov)}
                class="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-hud text-[var(--accent-primary)] border border-[var(--accent-primary)]/40 hover:bg-[var(--accent-primary)]/10 chamfer-sm transition-colors cursor-pointer disabled:opacity-50"
              >
                <RefreshCw class="w-3.5 h-3.5 {syncLoading[prov.id] ? 'animate-spin' : ''}" />
                <span>{syncLoading[prov.id] ? 'SYNCING...' : 'SYNC MODELS'}</span>
              </button>

              <button
                type="button"
                onclick={() => handleDeleteProvider(prov.id, prov.name)}
                class="p-1.5 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 rounded transition-colors cursor-pointer"
                title="Delete provider"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>
        </CyberCard>
      {/each}
    </div>
  {/if}

  <!-- Create Modal -->
  {#if showCreateModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div class="w-full max-w-lg border border-[var(--accent-primary)] bg-[var(--bg-surface)] p-6 chamfer shadow-[var(--border-glow)] space-y-4">
        <div class="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
          <div class="font-hud font-bold text-sm text-[var(--text-primary)]">
            REGISTER NEW LLM GATEWAY
          </div>
          <button
            type="button"
            onclick={() => showCreateModal = false}
            class="text-[var(--text-muted)] hover:text-white text-xs font-hud"
          >
            [CLOSE]
          </button>
        </div>

        {#if formError}
          <div class="p-2.5 text-xs font-code text-[var(--status-danger)] bg-[var(--status-danger)]/10 border border-[var(--status-danger)]">
            {formError}
          </div>
        {/if}

        <form onsubmit={handleCreateProvider} class="space-y-4 text-xs font-code">
          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Provider Label / Name</span>
              <input
                type="text"
                bind:value={formName}
                placeholder="e.g. OpenRouter Gateway"
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              />
            </label>
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Provider Type</span>
              <select
                bind:value={formType}
                onchange={() => {
                  if (formType === 'openrouter') formBaseUrl = 'https://openrouter.ai/api/v1';
                  else if (formType === 'ollama') formBaseUrl = 'http://localhost:11434';
                  else if (formType === 'openai') formBaseUrl = 'https://api.openai.com/v1';
                }}
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
              >
                <option value="openrouter">OpenRouter (Omnigateway)</option>
                <option value="litellm">LiteLLM Proxy</option>
                <option value="openai">OpenAI Official</option>
                <option value="ollama">Local Ollama / vLLM</option>
                <option value="custom">Custom Compatible API</option>
              </select>
            </label>
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Base URL</span>
              <input
                type="text"
                bind:value={formBaseUrl}
                placeholder="e.g. https://openrouter.ai/api/v1"
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              />
            </label>
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>API Key (Encrypted in DB)</span>
              <input
                type="password"
                bind:value={formApiKey}
                placeholder="sk-..."
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
              />
            </label>
            <span class="text-[10px] text-[var(--text-muted)] mt-1 block">
              Leave blank if running local Ollama without auth.
            </span>
          </div>

          <div class="pt-3 border-t border-[var(--border-color)] flex justify-end gap-2">
            <CyberButton variant="ghost" size="sm" type="button" onclick={() => showCreateModal = false}>
              CANCEL
            </CyberButton>
            <CyberButton variant="primary" size="sm" type="submit" disabled={formSubmitting}>
              {formSubmitting ? 'SAVING...' : 'ENCRYPT & SAVE'}
            </CyberButton>
          </div>
        </form>
      </div>
    </div>
  {/if}

  <!-- Models List Modal / Drawer -->
  {#if selectedProviderModels}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div class="w-full max-w-2xl max-h-[80vh] flex flex-col border border-[var(--accent-primary)] bg-[var(--bg-surface)] chamfer shadow-[var(--border-glow)] overflow-hidden">
        <div class="flex items-center justify-between p-4 border-b border-[var(--border-color)] bg-[var(--bg-elevated)]/60">
          <div>
            <div class="font-hud font-bold text-sm text-[var(--text-primary)]">
              AVAILABLE MODELS // {selectedProviderModels.providerName}
            </div>
            <div class="text-[10px] text-[var(--text-muted)] font-code">
              {selectedProviderModels.models.length} models discovered via /models endpoint
            </div>
          </div>
          <button
            type="button"
            onclick={() => selectedProviderModels = null}
            class="text-xs font-hud text-[var(--text-muted)] hover:text-white"
          >
            [CLOSE]
          </button>
        </div>

        <!-- Search Bar -->
        <div class="p-3 border-b border-[var(--border-color)] bg-[var(--bg-surface)]">
          <div class="relative">
            <Search class="w-4 h-4 absolute left-3 top-2.5 text-[var(--text-muted)]" />
            <input
              type="text"
              bind:value={modelSearch}
              placeholder="Filter models by id or name..."
              class="w-full pl-9 pr-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-xs font-code text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
            />
          </div>
        </div>

        <div class="flex-1 p-4 overflow-y-auto space-y-2">
          {#each filteredModels as model}
            <div class="border border-[var(--border-color)]/60 bg-[var(--bg-elevated)]/40 p-2.5 rounded-sm flex items-center justify-between font-code text-xs">
              <div>
                <div class="font-bold text-[var(--text-primary)]">{model.id}</div>
                {#if model.name && model.name !== model.id}
                  <div class="text-[10px] text-[var(--text-muted)]">{model.name}</div>
                {/if}
              </div>
              {#if model.context_length}
                <span class="text-[10px] text-[var(--accent-primary)] px-2 py-0.5 rounded bg-[var(--accent-primary)]/10">
                  {Math.round(model.context_length / 1000)}k ctx
                </span>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}
</div>
