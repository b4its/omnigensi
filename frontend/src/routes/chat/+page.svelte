<script lang="ts">
  /**
   * Interactive AI chat console.
   *
   * The operator picks a provider + model from the synced model registry, then
   * converses with it. Replies stream token-by-token over SSE so long answers
   * appear as they are generated. The model can be switched mid-conversation;
   * the transcript is preserved so context carries over.
   */
  import { onMount } from 'svelte';
  import { marked } from 'marked';
  import { sanitizeHtml } from '$lib/utils/sanitize';
  import { api, streamChatCompletion, type ChatModelOption, type ChatTurn } from '$lib/api';
  import { notify } from '$lib/stores/notify.svelte';
  import LoadError from '$lib/components/ui/LoadError.svelte';
  import {
    Send,
    Square,
    Loader2,
    Sparkles,
    RefreshCw,
    Trash2,
    User,
    Bot,
    AlertTriangle,
    ChevronDown,
    Check
  } from 'lucide-svelte';

  interface UIMessage {
    role: 'user' | 'assistant';
    content: string;
    error?: boolean;
    model_id?: string;
  }

  let models = $state<ChatModelOption[]>([]);
  let loadingModels = $state(true);
  let loadError = $state<string | null>(null);

  let selectedKey = $state<string>(''); // `${provider_id}::${model_id}`
  let messages = $state<UIMessage[]>([]);
  let input = $state('');
  let streaming = $state(false);
  let streamText = $state('');
  let temperature = $state(0.7);

  let abortHandle: { abort: () => void } | null = null;
  let scroller: HTMLDivElement | undefined = $state();
  let searchInput: HTMLInputElement | undefined = $state();
  let pickerWrap: HTMLDivElement | undefined = $state();

  const selectedModel = $derived(
    models.find((m) => `${m.provider_id}::${m.model_id}` === selectedKey) ?? null
  );

  /** Group options by provider so the picker can use optgroups. */
  const grouped = $derived.by(() => {
    const map = new Map<string, { name: string; items: ChatModelOption[] }>();
    for (const m of models) {
      const entry = map.get(m.provider_id) ?? { name: m.provider_name, items: [] };
      entry.items.push(m);
      map.set(m.provider_id, entry);
    }
    return [...map.entries()]
      .map(([id, v]) => ({ provider_id: id, provider_name: v.name, items: v.items }))
      .sort((a, b) => a.provider_name.localeCompare(b.provider_name));
  });

  // Searchable model picker state.
  let modelSearch = $state('');
  let pickerOpen = $state(false);
  let activeIndex = $state(0);

  /** Models matching the search text, grouped the same way as `grouped`. */
  const filteredGrouped = $derived.by(() => {
    const q = modelSearch.trim().toLowerCase();
    if (!q) return grouped;
    return grouped
      .map((g) => ({
        ...g,
        items: g.items.filter(
          (m) =>
            m.model_id.toLowerCase().includes(q) ||
            (m.display_name ?? '').toLowerCase().includes(q) ||
            m.provider_name.toLowerCase().includes(q)
        )
      }))
      .filter((g) => g.items.length > 0);
  });

  /** Flat list of matches, used for keyboard navigation. */
  const filteredFlat = $derived(filteredGrouped.flatMap((g) => g.items));

  /** Reset the highlight to the top whenever the query changes. */
  $effect(() => {
    modelSearch;
    activeIndex = 0;
  });

  function openPicker() {
    if (streaming) return;
    pickerOpen = true;
    modelSearch = '';
    activeIndex = 0;
    // Focus the search box once it is in the DOM.
    requestAnimationFrame(() => searchInput?.focus());
  }

  function chooseModel(m: ChatModelOption) {
    selectedKey = `${m.provider_id}::${m.model_id}`;
    pickerOpen = false;
    modelSearch = '';
  }

  /** Close the picker when the operator clicks anywhere outside it. */
  function handleDocumentPointerDown(e: PointerEvent) {
    if (!pickerOpen) return;
    const target = e.target as Node | null;
    if (pickerWrap && target && !pickerWrap.contains(target)) {
      pickerOpen = false;
    }
  }

  function handlePickerKeydown(e: KeyboardEvent) {
    if (!pickerOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        e.preventDefault();
        openPicker();
      }
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      pickerOpen = false;
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (filteredFlat.length) activeIndex = (activeIndex + 1) % filteredFlat.length;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (filteredFlat.length)
        activeIndex = (activeIndex - 1 + filteredFlat.length) % filteredFlat.length;
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const pick = filteredFlat[activeIndex];
      if (pick) chooseModel(pick);
    }
  }

  async function loadModels() {
    loadingModels = true;
    loadError = null;
    try {
      const res = await api.getChatModels();
      models = res.models;
      if (!selectedKey && models.length > 0) {
        const preferred = models.find((m) => m.is_default) ?? models[0];
        selectedKey = `${preferred.provider_id}::${preferred.model_id}`;
      }
    } catch (e) {
      loadError = e instanceof Error ? e.message : 'Unable to load models';
    } finally {
      loadingModels = false;
    }
  }

  onMount(loadModels);

  function scrollToBottom() {
    requestAnimationFrame(() => {
      if (scroller) scroller.scrollTop = scroller.scrollHeight;
    });
  }

  /** Escape closes an in-flight stream so the UI never deadlocks. */
  function handleKeydown(e: KeyboardEvent) {
    // The picker consumes Escape itself while it is open.
    if (e.key === 'Escape' && streaming && !pickerOpen) stopStream();
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || streaming) return;
    if (!selectedModel) {
      notify.warning('Pick a model first.');
      return;
    }

    messages = [...messages, { role: 'user', content: text }];
    input = '';
    streaming = true;
    streamText = '';
    scrollToBottom();

    // Full history (assistant turns included) keeps conversational context.
    const history: ChatTurn[] = messages.map((m) => ({ role: m.role, content: m.content }));

    let assembled = '';
    let failed: string | null = null;

    const handle = streamChatCompletion(
      {
        provider_id: selectedModel.provider_id,
        model_id: selectedModel.model_id,
        messages: history,
        temperature
      },
      {
        onToken: (chunk) => {
          streamText += chunk;
          scrollToBottom();
        },
        onDone: (info) => {
          assembled = info.content;
        },
        onError: (message) => {
          failed = message;
        }
      }
    );
    abortHandle = handle;
    await handle.done;
    abortHandle = null;

    streaming = false;
    const finalText = assembled || streamText;
    if (finalText.trim()) {
      messages = [
        ...messages,
        { role: 'assistant', content: finalText, model_id: selectedModel.model_id }
      ];
    }
    if (failed) {
      messages = [
        ...messages,
        {
          role: 'assistant',
          content: failed,
          error: true,
          model_id: selectedModel.model_id
        }
      ];
      notify.error(failed);
    }
    streamText = '';
    scrollToBottom();
  }

  function stopStream() {
    abortHandle?.abort();
  }

  function clearChat() {
    if (streaming) return;
    messages = [];
    streamText = '';
  }

  function renderMarkdown(text: string): string {
    return sanitizeHtml(marked.parse(text) as string);
  }
</script>

<svelte:window on:keydown={handleKeydown} on:pointerdown={handleDocumentPointerDown} />

<div class="space-y-4">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[var(--border-color)] pb-4">
    <div>
      <div class="text-[11px] font-code text-[var(--accent-primary)] uppercase tracking-wider">
        MODULE // 09
      </div>
      <h1 class="text-xl md:text-2xl font-hud font-black text-[var(--text-primary)]">
        AI CHAT CONSOLE
      </h1>
      <p class="text-xs text-[var(--text-muted)] mt-1">
        Converse with any synced model. Switch models mid-conversation without losing context.
      </p>
    </div>
    <button
      type="button"
      onclick={clearChat}
      disabled={streaming || messages.length === 0}
      class="inline-flex items-center gap-1.5 px-3 py-2 text-[11px] font-hud border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--status-danger)] hover:border-[var(--status-danger)]/50 chamfer-sm disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
    >
      <Trash2 class="w-3.5 h-3.5" />
      <span>CLEAR CHAT</span>
    </button>
  </div>

  {#if loadError}
    <LoadError message={loadError} onRetry={loadModels} retrying={loadingModels} />
  {:else if loadingModels}
    <div class="text-center py-12 font-code text-xs text-[var(--text-muted)] animate-pulse">
      LOADING MODEL REGISTRY...
    </div>
  {:else if models.length === 0}
    <div class="border border-dashed border-[var(--border-color)] p-8 text-center chamfer space-y-3">
      <Sparkles class="w-10 h-10 mx-auto text-[var(--text-muted)] opacity-50" />
      <div class="font-hud font-bold text-sm text-[var(--text-primary)]">NO MODELS AVAILABLE</div>
      <p class="text-xs text-[var(--text-muted)] max-w-md mx-auto">
        Register a provider and run <span class="text-[var(--accent-primary)]">SYNC MODELS</span>
        in the OmniRouter Vault so a model becomes selectable here.
      </p>
    </div>
  {:else}
    <!-- Model selector bar -->
    <div bind:this={pickerWrap} class="border border-[var(--border-color)] bg-[var(--bg-surface)] p-3 chamfer-sm">
      <div class="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end font-code text-xs">
        <div class="sm:col-span-7">
          <label for="chat-model" class="block text-[var(--text-muted)] mb-1 uppercase font-bold text-[10px]">
            Model
          </label>
          <div class="relative">
            <!-- Closed state: a button showing the current model. -->
            {#if !pickerOpen}
              <button
                type="button"
                id="chat-model"
                onclick={openPicker}
                disabled={streaming}
                aria-haspopup="listbox"
                aria-expanded={false}
                class="w-full flex items-center justify-between gap-2 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] text-left hover:border-[var(--accent-primary)] focus:outline-none focus:border-[var(--accent-primary)] disabled:opacity-60 disabled:cursor-not-allowed"
              >
                <span class="truncate">
                  {selectedModel?.model_id ?? 'Select a model'}
                  {#if selectedModel?.is_default}<span class="text-[var(--text-muted)]"> · default</span>{/if}
                </span>
                <ChevronDown class="w-4 h-4 shrink-0 text-[var(--text-muted)]" />
              </button>
            {:else}
              <!-- Open state: a search box that filters the list below. -->
              <input
                id="chat-model"
                type="text"
                bind:value={modelSearch}
                onkeydown={handlePickerKeydown}
                placeholder="Search models..."
                autocomplete="off"
                aria-controls="chat-model-list"
                class="w-full px-3 py-2 pr-9 bg-[var(--bg-elevated)] border border-[var(--accent-primary)] text-[var(--text-primary)] focus:outline-none"
                bind:this={searchInput}
              />
              <ChevronDown class="w-4 h-4 absolute right-3 top-2.5 text-[var(--accent-primary)] pointer-events-none rotate-180" />
            {/if}
          </div>
        </div>

        <!-- Dropdown list, only while searching -->
        {#if pickerOpen}
          <div class="sm:col-span-12 relative">
            <ul
              id="chat-model-list"
              role="listbox"
              class="max-h-64 overflow-y-auto border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer-sm font-code text-xs"
            >
              {#if filteredFlat.length === 0}
                <li class="px-3 py-3 text-[var(--text-muted)] italic">
                  No model matches "{modelSearch}".
                </li>
              {:else}
                {#each filteredGrouped as group (group.provider_id)}
                  <li class="px-3 py-1.5 text-[10px] uppercase font-bold text-[var(--text-muted)] bg-[var(--bg-elevated)]/60 border-b border-[var(--border-color)]/40 sticky top-0">
                    {group.provider_name}
                  </li>
                  {#each group.items as m (m.model_id)}
                    {@const flatIdx = filteredFlat.indexOf(m)}
                    <li
                      role="option"
                      aria-selected={`${m.provider_id}::${m.model_id}` === selectedKey}
                    >
                      <button
                        type="button"
                        onclick={() => chooseModel(m)}
                        onmouseenter={() => (activeIndex = flatIdx)}
                        class="w-full flex items-center justify-between gap-2 px-3 py-2 text-left border-b border-[var(--border-color)]/30 last:border-b-0 transition-colors {flatIdx === activeIndex
                          ? 'bg-[var(--accent-primary)]/15'
                          : 'hover:bg-[var(--bg-elevated)]'}"
                      >
                        <span class="min-w-0 truncate {`${m.provider_id}::${m.model_id}` === selectedKey ? 'text-[var(--accent-primary)] font-bold' : 'text-[var(--text-primary)]'}">
                          {m.model_id}
                          {#if m.is_default}<span class="text-[10px] text-[var(--text-muted)]"> · default</span>{/if}
                        </span>
                        <span class="shrink-0 flex items-center gap-2 text-[10px] text-[var(--text-muted)]">
                          {#if m.context_length}{Math.round(m.context_length / 1000)}k{/if}
                          {#if `${m.provider_id}::${m.model_id}` === selectedKey}
                            <Check class="w-3.5 h-3.5 text-[var(--accent-primary)]" />
                          {/if}
                        </span>
                      </button>
                    </li>
                  {/each}
                {/each}
              {/if}
            </ul>
            <p class="mt-1 text-[10px] font-code text-[var(--text-muted)]">
              {filteredFlat.length} of {models.length} models · ↑↓ to navigate · Enter to select · Esc to close
            </p>
          </div>
        {/if}
        <div class="sm:col-span-3">
          <label for="chat-temperature" class="block text-[var(--text-muted)] mb-1 uppercase font-bold text-[10px]">
            Temperature: <span class="text-[var(--accent-primary)]">{temperature.toFixed(1)}</span>
          </label>
          <input
            id="chat-temperature"
            type="range"
            min="0"
            max="2"
            step="0.1"
            bind:value={temperature}
            disabled={streaming}
            class="w-full accent-[var(--accent-primary)]"
          />
        </div>
        <div class="sm:col-span-2">
          <button
            type="button"
            onclick={loadModels}
            disabled={loadingModels || streaming}
            class="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 font-hud text-[11px] border border-[var(--accent-primary)]/50 text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 chamfer-sm disabled:opacity-40"
          >
            <RefreshCw class="w-3.5 h-3.5" />
            <span>REFRESH</span>
          </button>
        </div>
      </div>
      {#if selectedModel}
        <p class="mt-2 text-[10px] font-code text-[var(--text-muted)]">
          {selectedModel.provider_name} ·
          {#if selectedModel.context_length}{Math.round(selectedModel.context_length / 1000)}k ctx · {/if}
          {selectedModel.is_available ? 'ready' : 'unavailable'}
        </p>
      {/if}
    </div>

    <!-- Transcript -->
    <div
      bind:this={scroller}
      class="border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer-sm h-[52dvh] min-h-[320px] overflow-y-auto p-4 space-y-4"
    >
      {#if messages.length === 0 && !streamText}
        <div class="h-full flex flex-col items-center justify-center text-center gap-2 text-[var(--text-muted)]">
          <Sparkles class="w-8 h-8 opacity-40" />
          <p class="font-code text-xs">
            Start the conversation with <span class="text-[var(--accent-primary)]">{selectedModel?.model_id}</span>.
          </p>
        </div>
      {/if}

      {#each messages as msg, i (i)}
        <div class="flex gap-2.5 {msg.role === 'user' ? 'flex-row-reverse' : ''}">
          <div class="shrink-0 w-7 h-7 flex items-center justify-center chamfer-sm border {msg.role === 'user'
            ? 'border-[var(--accent-primary)]/50 text-[var(--accent-primary)] bg-[var(--accent-primary)]/10'
            : msg.error
              ? 'border-[var(--status-danger)]/50 text-[var(--status-danger)] bg-[var(--status-danger)]/10'
              : 'border-[var(--border-color)] text-[var(--text-primary)] bg-[var(--bg-elevated)]'}">
            {#if msg.role === 'user'}
              <User class="w-4 h-4" />
            {:else if msg.error}
              <AlertTriangle class="w-4 h-4" />
            {:else}
              <Bot class="w-4 h-4" />
            {/if}
          </div>
          <div class="min-w-0 max-w-[85%] {msg.role === 'user' ? 'text-right' : ''}">
            {#if msg.role === 'user'}
              <div class="inline-block text-left px-3 py-2 chamfer-sm bg-[var(--accent-primary)]/10 border border-[var(--accent-primary)]/30 text-xs font-code text-[var(--text-primary)] whitespace-pre-wrap break-words">
                {msg.content}
              </div>
            {:else if msg.error}
              <div class="px-3 py-2 chamfer-sm bg-[var(--status-danger)]/10 border border-[var(--status-danger)]/40 text-xs font-code text-[var(--status-danger)] break-words">
                {msg.content}
              </div>
            {:else}
              <div class="prose prose-xs dark-prose max-w-none text-xs font-code text-[var(--text-primary)] px-3 py-2 chamfer-sm bg-[var(--bg-elevated)]/60 border border-[var(--border-color)]/60">
                {@html renderMarkdown(msg.content)}
              </div>
              {#if msg.model_id}
                <span class="block mt-1 text-[9px] font-code text-[var(--text-muted)]">{msg.model_id}</span>
              {/if}
            {/if}
          </div>
        </div>
      {/each}

      {#if streaming}
        <div class="flex gap-2.5">
          <div class="shrink-0 w-7 h-7 flex items-center justify-center chamfer-sm border border-[var(--accent-primary)]/50 text-[var(--accent-primary)] bg-[var(--accent-primary)]/10">
            <Loader2 class="w-4 h-4 animate-spin" />
          </div>
          <div class="min-w-0 max-w-[85%]">
            {#if streamText}
              <div class="prose prose-xs dark-prose max-w-none text-xs font-code text-[var(--text-primary)] px-3 py-2 chamfer-sm bg-[var(--bg-elevated)]/60 border border-[var(--border-color)]/60">
                {@html renderMarkdown(streamText)}
              </div>
            {:else}
              <div class="px-3 py-2 text-xs font-code text-[var(--text-muted)] italic">
                waiting for the model...
              </div>
            {/if}
          </div>
        </div>
      {/if}
    </div>

    <!-- Composer -->
    <form
      onsubmit={(e) => {
        e.preventDefault();
        sendMessage();
      }}
      class="border border-[var(--border-color)] bg-[var(--bg-surface)] p-2 chamfer-sm"
    >
      <div class="flex items-end gap-2">
        <textarea
          bind:value={input}
          onkeydown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
          rows="2"
          disabled={streaming}
          placeholder="Type a message... (Enter to send, Shift+Enter for newline)"
          class="flex-1 resize-none px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-xs font-code text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] disabled:opacity-60"
        ></textarea>
        {#if streaming}
          <button
            type="button"
            onclick={stopStream}
            class="shrink-0 inline-flex items-center gap-1.5 px-4 py-2.5 font-hud text-[11px] font-bold border border-[var(--status-danger)]/60 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 chamfer-sm"
          >
            <Square class="w-3.5 h-3.5 fill-current" />
            STOP
          </button>
        {:else}
          <button
            type="submit"
            disabled={!input.trim() || !selectedModel}
            class="shrink-0 inline-flex items-center gap-1.5 px-4 py-2.5 font-hud text-[11px] font-bold border border-[var(--accent-primary)] text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 chamfer-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send class="w-3.5 h-3.5" />
            SEND
          </button>
        {/if}
      </div>
    </form>
  {/if}
</div>
