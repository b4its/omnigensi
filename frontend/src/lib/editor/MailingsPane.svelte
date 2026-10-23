<script lang="ts">
  /**
   * MailingsPane — Word's Mailings workflow strip: load a recipient list, pick
   * the field to insert, then preview or merge. Mirrors Word's left-to-right
   * order (Start → Fields → Preview → Finish) so it's familiar on first use.
   */
  import { Upload, UserPlus, Eye, EyeOff, CheckCheck, X, ChevronLeft, ChevronRight } from 'lucide-svelte';
  import type { Recipients } from './mailings';
  import { greetingLine, addressBlock } from './mailings';
  import { formatNumber } from './dates';

  interface Props {
    recipients: Recipients;
    onupload: () => void;
    oninsertfield: (field: string) => void;
    oninsertaddress: () => void;
    oninsertgreeting: () => void;
    ontogglehighlight: () => void;
    highlight: boolean;
    onmerge: () => void;
    onlabels: () => void;
    onselectrecord: (index: number) => void;
    activeRecord: number;
    onexit: () => void;
  }
  let {
    recipients,
    onupload,
    oninsertfield,
    oninsertaddress,
    oninsertgreeting,
    ontogglehighlight,
    highlight,
    onmerge,
    onlabels,
    onselectrecord,
    activeRecord,
    onexit,
  }: Props = $props();
</script>

<div class="border-b border-[var(--border-color)] bg-[var(--bg-elevated)]/60">
  <div class="flex items-center gap-2 px-3 py-1.5 border-b border-[var(--border-color)]/50">
    <span class="text-[10px] font-hud tracking-wider text-[var(--text-muted)]">MAIL MERGE</span>
    <span class="text-[10px] font-code {recipients.rows.length ? 'text-[var(--status-success)]' : 'text-[var(--text-muted)]'}">
      {recipients.rows.length ? `${formatNumber(recipients.rows.length)} penerima · ${recipients.fields.length} kolom` : 'belum ada daftar'}
    </span>
    <div class="flex-1"></div>
    <button type="button" onclick={onexit} class="text-[var(--text-muted)] hover:text-[var(--text-primary)]" aria-label="Tutup mail merge">
      <X class="w-3.5 h-3.5" />
    </button>
  </div>
  <div class="flex items-stretch gap-0 min-h-[64px] overflow-x-auto py-1">
    <!-- Start -->
    <div class="flex flex-col justify-between px-2.5 border-r border-[var(--border-color)]/60">
      <button
        type="button"
        onclick={onupload}
        class="flex items-center gap-1.5 px-2 py-1 rounded-sm text-[11px] font-code text-[var(--text-primary)] hover:bg-[var(--bg-surface)]"
      >
        <Upload class="w-3.5 h-3.5" /> PILIH PENERIMA (CSV)
      </button>
      <div class="text-center text-[9px] font-code uppercase text-[var(--text-muted)]">Mulai</div>
    </div>

    <!-- Fields -->
    <div class="flex flex-col justify-between px-2.5 border-r border-[var(--border-color)]/60">
      <div class="flex flex-wrap items-center gap-1 max-w-md">
        {#if recipients.fields.length === 0}
          <span class="text-[10px] font-code text-[var(--text-muted)]">Muat CSV untuk kolom gabungan</span>
        {:else}
          {#each recipients.fields as f}
            <button
              type="button"
              onmousedown={(e) => {
                e.preventDefault();
                oninsertfield(f);
              }}
              class="px-1.5 py-0.5 text-[10px] font-code border border-[var(--border-color)] rounded-sm hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]"
            >
              {""}{"{"}{"{"}{f}{"}"}{"}"}
            </button>
          {/each}
        {/if}
        <button type="button" onmousedown={(e) => { e.preventDefault(); oninsertaddress(); }} class="px-1.5 py-0.5 text-[10px] font-code border border-dashed border-[var(--border-color)] rounded-sm hover:border-[var(--accent-primary)] flex items-center gap-1">
          <UserPlus class="w-3 h-3" /> Blok Alamat
        </button>
        <button type="button" onmousedown={(e) => { e.preventDefault(); oninsertgreeting(); }} class="px-1.5 py-0.5 text-[10px] font-code border border-dashed border-[var(--border-color)] rounded-sm hover:border-[var(--accent-primary)]">
          Salam
        </button>
        <button type="button" onclick={ontogglehighlight} class="px-1.5 py-0.5 text-[10px] font-code border border-[var(--border-color)] rounded-sm hover:border-[var(--accent-primary)]" aria-pressed={highlight}>
          Sorot Kolom
        </button>
      </div>
      <div class="text-center text-[9px] font-code uppercase text-[var(--text-muted)]">Sisipkan Kolom Gabungan</div>
    </div>

    <!-- Preview -->
    <div class="flex flex-col justify-between px-2.5 border-r border-[var(--border-color)]/60">
      <div class="flex items-center gap-1">
        <button
          type="button"
          onclick={() => onselectrecord(Math.max(0, activeRecord - 1))}
          disabled={recipients.rows.length === 0}
          class="p-1 text-[var(--text-primary)] disabled:opacity-30"
          aria-label="Penerima sebelumnya"
        >
          <ChevronLeft class="w-3.5 h-3.5" />
        </button>
        <span class="text-[10px] font-code text-[var(--text-primary)]">
          {recipients.rows.length ? `${activeRecord + 1} / ${recipients.rows.length}` : '—'}
        </span>
        <button
          type="button"
          onclick={() => onselectrecord(Math.min(recipients.rows.length - 1, activeRecord + 1))}
          disabled={recipients.rows.length === 0}
          class="p-1 text-[var(--text-primary)] disabled:opacity-30"
          aria-label="Penerima berikutnya"
        >
          <ChevronRight class="w-3.5 h-3.5" />
        </button>
      </div>
      {#if recipients.rows[activeRecord]}
        <div class="text-[9px] font-code text-[var(--text-muted)] truncate max-w-[180px]" title={greetingLine(recipients.rows[activeRecord])}>
          {greetingLine(recipients.rows[activeRecord])}
        </div>
      {/if}
      <div class="text-center text-[9px] font-code uppercase text-[var(--text-muted)]">
        {#if highlight}<Eye class="w-3 h-3 inline" />{:else}<EyeOff class="w-3 h-3 inline" />{/if} Pratinjau
      </div>
    </div>

    <!-- Finish -->
    <div class="flex flex-col justify-between px-2.5">
      <div class="flex items-center gap-1">
        <button
          type="button"
          onclick={onmerge}
          disabled={recipients.rows.length === 0}
          class="flex items-center gap-1 px-2 py-1 text-[11px] font-code border border-[var(--accent-primary)] text-[var(--accent-primary)] rounded-sm hover:bg-[var(--accent-primary)]/10 disabled:opacity-30"
        >
          <CheckCheck class="w-3.5 h-3.5" /> GABUNGKAN
        </button>
        <button
          type="button"
          onclick={onlabels}
          disabled={recipients.rows.length === 0}
          class="px-2 py-1 text-[11px] font-code border border-[var(--border-color)] rounded-sm hover:bg-[var(--bg-surface)] disabled:opacity-30"
        >
          Label/Amplop
        </button>
      </div>
      <div class="text-center text-[9px] font-code uppercase text-[var(--text-muted)]">Selesai</div>
    </div>
  </div>
</div>
