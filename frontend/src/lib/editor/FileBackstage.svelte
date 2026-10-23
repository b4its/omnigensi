<script lang="ts">
  /**
   * FileBackstage — Word's File tab. It replaces the whole stage (not a
   * dialog) with a start page: create from a template, open, save, export,
   * print, inspect recovery drafts and edit document properties.
   */
  import {
    ArrowLeft,
    FileText,
    FolderOpen,
    Save,
    Printer,
    Download,
    History,
    FileClock,
    ListTree,
    Info,
    ShieldCheck,
    FileDown,
  } from 'lucide-svelte';
  import { TEMPLATES } from './fileFormats';
  import type { Template } from './fileFormats';
  import type { DocProperties, Version, Draft } from './persistence';
  import { formatNumber } from './dates';

  interface Props {
    properties: DocProperties;
    versions: Version[];
    recovery: Draft[];
    onclose: () => void;
    onnew: (tpl: Template) => void;
    onopen: () => void;
    onsave: () => void;
    onexportpdf: () => void;
    onexport: (format: 'docx' | 'doc' | 'odt' | 'rtf' | 'tex' | 'html' | 'md' | 'txt') => void;
    onrestoreversion: (v: Version) => void;
    onrecover: (d: Draft) => void;
    onsaveproperties: (props: DocProperties) => void;
    oninspect: () => void;
    onaccessibility: () => void;
  }

  let {
    properties = $bindable(),
    versions,
    recovery,
    onclose,
    onnew,
    onopen,
    onsave,
    onexportpdf,
    onexport,
    onrestoreversion,
    onrecover,
    onsaveproperties,
    oninspect,
    onaccessibility,
  }: Props = $props();

  type Panel = 'home' | 'new' | 'open' | 'info' | 'export' | 'recover' | 'properties';
  let panel = $state<Panel>('home');

  const navItems: { key: Panel; label: string; icon: typeof Info }[] = [
    { key: 'home', label: 'Beranda', icon: FileText },
    { key: 'new', label: 'Baru', icon: FileText },
    { key: 'open', label: 'Buka', icon: FolderOpen },
    { key: 'info', label: 'Info', icon: Info },
    { key: 'export', label: 'Ekspor', icon: Download },
    { key: 'recover', label: 'Pulihkan', icon: FileClock },
    { key: 'properties', label: 'Properti', icon: ListTree },
  ];

  const exportFormats: { format: 'docx' | 'doc' | 'odt' | 'rtf' | 'tex' | 'html' | 'md' | 'txt'; label: string; hint: string }[] = [
    { format: 'docx', label: '.docx', hint: 'Microsoft Word (OOXML)' },
    { format: 'doc', label: '.doc', hint: 'Word HTML (kompatibilitas luas)' },
    { format: 'odt', label: '.odt', hint: 'LibreOffice / OpenDocument' },
    { format: 'rtf', label: '.rtf', hint: 'Rich Text Format' },
    { format: 'tex', label: '.tex', hint: 'LaTeX' },
    { format: 'html', label: '.html', hint: 'Halaman web' },
    { format: 'md', label: '.md', hint: 'Markdown' },
    { format: 'txt', label: '.txt', hint: 'Teks polos' },
  ];

  function stamp(ts: number): string {
    return new Date(ts).toLocaleString('id-ID', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
</script>

<div class="flex h-full bg-[var(--bg-primary)] text-[var(--text-primary)]">
  <!-- Left navigation -->
  <nav class="w-56 shrink-0 border-r border-[var(--border-color)] bg-[var(--bg-surface)]/80 p-2 flex flex-col gap-0.5">
    <button
      type="button"
      onclick={onclose}
      class="flex items-center gap-2 px-3 py-2 mb-2 text-[11px] font-hud tracking-wider border border-[var(--border-color)] rounded-sm text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10"
    >
      <ArrowLeft class="w-3.5 h-3.5" /> KEMBALI KE DOKUMEN
    </button>
    {#each navItems as item}
      <button
        type="button"
        onclick={() => (panel = item.key)}
        class="flex items-center gap-2 px-3 py-2 text-[12px] rounded-sm transition-colors
          {panel === item.key ? 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]' : 'text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]'}"
      >
        <item.icon class="w-4 h-4 shrink-0" />
        {item.label}
      </button>
    {/each}
  </nav>

  <!-- Panel body -->
  <div class="flex-1 overflow-y-auto p-6">
    {#if panel === 'home'}
      <h2 class="font-hud text-lg mb-1">
        {new Date().getHours() < 12 ? 'Selamat pagi' : new Date().getHours() < 18 ? 'Selamat siang' : 'Selamat malam'}
      </h2>
      <p class="text-[11px] font-code text-[var(--text-muted)] mb-5">{properties.title}</p>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-3 max-w-3xl">
        {#each TEMPLATES as tpl}
          <button
            type="button"
            onclick={() => onnew(tpl)}
            class="text-left border border-[var(--border-color)] rounded-sm p-3 hover:border-[var(--accent-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <div class="h-24 bg-[var(--bg-surface)] border border-[var(--border-color)]/60 rounded-sm mb-2 p-2 overflow-hidden pointer-events-none">
              <!-- eslint-disable-next-line svelte/no-at-html-tags -->
              <div class="text-[6px] leading-[1.3] opacity-70 [&_h1]:text-[10px] [&_h1]:font-bold [&_h2]:text-[8px] [&_h2]:font-bold">{@html tpl.html}</div>
            </div>
            <div class="text-[12px] text-[var(--text-primary)]">{tpl.label}</div>
            <div class="text-[10px] font-code text-[var(--text-muted)]">{tpl.description}</div>
          </button>
        {/each}
      </div>
    {:else if panel === 'new'}
      <h2 class="font-hud text-lg mb-4">Dokumen Baru</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-3xl">
        {#each TEMPLATES as tpl}
          <button
            type="button"
            onclick={() => onnew(tpl)}
            class="flex items-start gap-3 text-left border border-[var(--border-color)] rounded-sm p-3 hover:border-[var(--accent-primary)] hover:bg-[var(--bg-elevated)]"
          >
            <FileText class="w-6 h-6 text-[var(--accent-primary)] shrink-0" />
            <span>
              <span class="block text-[13px]">{tpl.label}</span>
              <span class="block text-[10px] font-code text-[var(--text-muted)]">{tpl.description}</span>
            </span>
          </button>
        {/each}
      </div>
    {:else if panel === 'open'}
      <h2 class="font-hud text-lg mb-4">Buka Dokumen</h2>
      <button
        type="button"
        onclick={onopen}
        class="flex items-center gap-3 px-4 py-3 border border-dashed border-[var(--border-color)] rounded-sm hover:border-[var(--accent-primary)] hover:bg-[var(--bg-elevated)] max-w-md w-full"
      >
        <FolderOpen class="w-5 h-5 text-[var(--accent-primary)]" />
        <span class="text-left">
          <span class="block text-[13px]">Pilih berkas…</span>
          <span class="block text-[10px] font-code text-[var(--text-muted)]">.docx .doc .odt .rtf .html .md .txt</span>
        </span>
      </button>
    {:else if panel === 'info'}
      <h2 class="font-hud text-lg mb-4">Info</h2>
      <div class="max-w-lg space-y-3">
        <div class="border border-[var(--border-color)] rounded-sm p-3">
          <div class="text-[11px] font-code text-[var(--text-muted)]">Judul</div>
          <div class="text-[14px]">{properties.title}</div>
        </div>
        <div class="flex flex-wrap gap-2">
          <button type="button" onclick={onsave} class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-hud border border-[var(--accent-primary)] text-[var(--accent-primary)] chamfer-sm hover:bg-[var(--accent-primary)]/10">
            <Save class="w-3.5 h-3.5" /> SIMPAN
          </button>
          <button type="button" onclick={onexportpdf} class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-hud border border-[var(--border-color)] chamfer-sm hover:bg-[var(--bg-elevated)]">
            <Printer class="w-3.5 h-3.5" /> EKSPOR PDF
          </button>
          <button type="button" onclick={oninspect} class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-hud border border-[var(--border-color)] chamfer-sm hover:bg-[var(--bg-elevated)]">
            <ShieldCheck class="w-3.5 h-3.5" /> PERIKSA DOKUMEN
          </button>
          <button type="button" onclick={onaccessibility} class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-hud border border-[var(--border-color)] chamfer-sm hover:bg-[var(--bg-elevated)]">
            <ShieldCheck class="w-3.5 h-3.5" /> AKSESIBILITAS
          </button>
        </div>
      </div>
    {:else if panel === 'export'}
      <h2 class="font-hud text-lg mb-4">Ekspor</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2 max-w-3xl">
        {#each exportFormats as f}
          <button
            type="button"
            onclick={() => onexport(f.format)}
            class="flex flex-col items-start gap-1 border border-[var(--border-color)] rounded-sm p-3 hover:border-[var(--accent-primary)] hover:bg-[var(--bg-elevated)]"
          >
            <FileDown class="w-4 h-4 text-[var(--accent-primary)]" />
            <span class="text-[13px] font-code">{f.label}</span>
            <span class="text-[10px] text-[var(--text-muted)]">{f.hint}</span>
          </button>
        {/each}
        <button
          type="button"
          onclick={onexportpdf}
          class="flex flex-col items-start gap-1 border border-[var(--border-color)] rounded-sm p-3 hover:border-[var(--accent-primary)] hover:bg-[var(--bg-elevated)]"
        >
          <Printer class="w-4 h-4 text-[var(--accent-primary)]" />
          <span class="text-[13px] font-code">.pdf</span>
          <span class="text-[10px] text-[var(--text-muted)]">Cetak → Simpan PDF</span>
        </button>
      </div>
    {:else if panel === 'recover'}
      <h2 class="font-hud text-lg mb-4 flex items-center gap-2"><FileClock class="w-4 h-4" /> Recover Unsaved</h2>
      {#if recovery.length === 0}
        <p class="text-[11px] font-code text-[var(--text-muted)]">Tidak ada draf yang bisa dipulihkan.</p>
      {:else}
        <div class="space-y-2 max-w-2xl">
          {#each recovery as d}
            <button
              type="button"
              onclick={() => onrecover(d)}
              class="w-full flex items-center justify-between text-left border border-[var(--border-color)] rounded-sm p-3 hover:border-[var(--accent-primary)] hover:bg-[var(--bg-elevated)]"
            >
              <span>
                <span class="block text-[12px]">{d.title}</span>
                <span class="block text-[10px] font-code text-[var(--text-muted)]">{stamp(d.at)}</span>
              </span>
              <span class="text-[10px] font-code text-[var(--accent-primary)]">PULIHKAN</span>
            </button>
          {/each}
        </div>
      {/if}

      <h3 class="font-hud text-sm mt-6 mb-2 flex items-center gap-2"><History class="w-3.5 h-3.5" /> Versi Tersimpan</h3>
      {#if versions.length === 0}
        <p class="text-[11px] font-code text-[var(--text-muted)]">Belum ada versi. Versi dibuat saat Anda menyimpan.</p>
      {:else}
        <div class="space-y-1 max-w-2xl">
          {#each [...versions].reverse() as v}
            <button
              type="button"
              onclick={() => onrestoreversion(v)}
              class="w-full flex items-center justify-between text-left px-3 py-1.5 border border-transparent rounded-sm hover:bg-[var(--bg-elevated)] hover:border-[var(--border-color)]"
            >
              <span class="text-[11px] font-code text-[var(--text-muted)]">{stamp(v.at)}</span>
              <span class="text-[10px] font-code text-[var(--text-muted)]">{formatNumber(v.words)} kata</span>
            </button>
          {/each}
        </div>
      {/if}
    {:else if panel === 'properties'}
      <h2 class="font-hud text-lg mb-4">Properti Dokumen</h2>
      <div class="max-w-md space-y-3">
        {#each [['title', 'Judul'], ['author', 'Penulis'], ['subject', 'Subjek'], ['keywords', 'Kata kunci'], ['comments', 'Catatan']] as [field, label]}
          <label class="block">
            <span class="block text-[10px] font-code text-[var(--text-muted)] mb-1">{label}</span>
            <input
              bind:value={properties[field as keyof DocProperties]}
              class="w-full px-2 py-1.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
            />
          </label>
        {/each}
        <button
          type="button"
          onclick={() => onsaveproperties(properties)}
          class="px-3 py-1.5 text-[11px] font-hud bg-[var(--accent-primary)] text-[var(--on-accent)] chamfer-sm"
        >
          SIMPAN PROPERTI
        </button>
      </div>
    {/if}
  </div>
</div>
