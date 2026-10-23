<script lang="ts">
  /**
   * StyleGallery — Word's live Styles gallery. Clicking a style applies it to
   * the selection; the "A+" button creates a new paragraph style from the
   * formatting under the caret. Custom styles are persisted separately from the
   * document so they follow the operator between manuscripts.
   */
  import { applyStyle, BUILTIN_STYLES, loadCustomStyles, newStyleFromSelection, saveCustomStyles } from './styles';
  import type { DocStyle } from './styles';
  import { Plus, Trash2 } from 'lucide-svelte';

  interface Props {
    activeStyle: string;
    /** Container direction; 'row' for the ribbon, 'col' for the side pane. */
    direction?: 'row' | 'col';
    compact?: boolean;
    /** Notify the page that a style was applied so it can record history. */
    onequestyle?: (style: DocStyle) => void;
  }
  let { activeStyle, direction = 'row', compact = false, onequestyle }: Props = $props();

  let custom = $state<DocStyle[]>(loadCustomStyles());
  let naming = $state(false);
  let draftName = $state('');

  const all = $derived([...BUILTIN_STYLES, ...custom]);

  function pick(style: DocStyle) {
    applyStyle(style);
    activeStyle = style.name;
    onequestyle?.(style);
  }

  function beginCreate() {
    draftName = 'Gaya Baru';
    naming = true;
  }

  function commitCreate() {
    const name = draftName.trim();
    if (!name) return;
    const style = newStyleFromSelection(name);
    custom = [...custom.filter((s) => s.name !== name), style];
    saveCustomStyles(custom);
    naming = false;
  }

  function removeCustom(name: string) {
    custom = custom.filter((s) => s.name !== name);
    saveCustomStyles(custom);
  }
</script>

<div
  class="flex {direction === 'row' ? 'flex-row items-start' : 'flex-col'} gap-1 overflow-x-auto"
  role="listbox"
  aria-label="Galeri gaya"
>
  {#each all as style (style.name)}
    <div class="relative shrink-0">
      <button
        type="button"
        role="option"
        aria-selected={activeStyle === style.name}
        title={style.name}
        onmousedown={(e) => {
          e.preventDefault();
          pick(style);
        }}
        class="flex flex-col items-start justify-center text-left border rounded-sm px-2 py-1 min-w-[76px] transition-colors
          {activeStyle === style.name
            ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/15'
            : 'border-[var(--border-color)] hover:bg-[var(--bg-elevated)]'}"
      >
        <span
          class="truncate w-full font-serif text-[var(--text-primary)]"
          style:font-size={compact ? '11px' : '12px'}
          style:font-weight={style.css['font-weight'] ?? '400'}
          style:font-style={style.css['font-style'] ?? 'normal'}
        >
          {style.name}
        </span>
        <span class="truncate w-full text-[9px] font-code text-[var(--text-muted)]">{style.preview}</span>
      </button>
      {#if custom.some((c) => c.name === style.name)}
        <button
          type="button"
          title="Hapus gaya"
          onmousedown={(e) => {
            e.preventDefault();
            removeCustom(style.name);
          }}
          class="absolute -top-1 -right-1 bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-full p-0.5 text-[var(--status-danger)]"
        >
          <Trash2 class="w-2.5 h-2.5" />
        </button>
      {/if}
    </div>
  {/each}

  {#if naming}
    <div class="flex items-center gap-1 shrink-0">
      <input
        bind:value={draftName}
        onkeydown={(e) => {
          if (e.key === 'Enter') commitCreate();
          if (e.key === 'Escape') naming = false;
        }}
        class="w-28 px-1 py-1 text-[11px] font-code bg-[var(--bg-elevated)] border border-[var(--accent-primary)] rounded-sm text-[var(--text-primary)] outline-none"
        aria-label="Nama gaya baru"
      />
      <button
        type="button"
        onmousedown={(e) => {
          e.preventDefault();
          commitCreate();
        }}
        class="px-2 py-1 text-[10px] font-hud bg-[var(--accent-primary)] text-[var(--on-accent)] rounded-sm"
      >
        OK
      </button>
    </div>
  {:else}
    <button
      type="button"
      title="Buat gaya dari format saat ini"
      onmousedown={(e) => {
        e.preventDefault();
        beginCreate();
      }}
      class="shrink-0 flex items-center justify-center w-7 h-7 border border-dashed border-[var(--border-color)] rounded-sm text-[var(--text-muted)] hover:text-[var(--accent-primary)]"
    >
      <Plus class="w-3.5 h-3.5" />
    </button>
  {/if}
</div>
