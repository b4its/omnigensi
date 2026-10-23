<script lang="ts">
  /**
   * EditorDialogs — every modal Naskah Studio can open, in one place, driven by
   * a discriminated `kind`. Keeping them in one component avoids ~20 tiny
   * files while still letting the page own the state and the commands.
   *
   * `submit(kind, payload)` receives the collected form values; the page turns
   * them into commands.
   */
  import EditorDialog from './EditorDialog.svelte';
  import { formatSource, CITATION_STYLES } from './references';
  import type { Source, CitationStyle } from './references';
  import { EQUATION_PRESETS } from './insertBlocks';
  import { SYMBOL_SETS } from './insertBlocks';
  import { DEFAULT_AUTOTEXT } from './loBlocks';
  import type { Anchor, Wrap } from './loBlocks';
  import type { LinkKind } from './loLinks';
  import { PAGE_NUMBER_FORMATS, PAPER_SIZES } from './pageSetup';
  import { Plus, Trash2, Search, ChevronLeft, ChevronRight } from 'lucide-svelte';

  export type DialogKind =
    | 'find'
    | 'link'
    | 'image'
    | 'font'
    | 'paragraph'
    | 'pagesetup'
    | 'watermark'
    | 'cover'
    | 'symbol'
    | 'equation'
    | 'quickparts'
    | 'chart'
    | 'smartart'
    | 'caption'
    | 'citations'
    | 'bookmark'
    | 'crossref'
    | 'comment'
    | 'pagecolor'
    | 'textbox'
    | 'wordart'
    | 'signature'
    | 'tableborders'
    | 'pictureformat'
    | 'wordcount'
    | 'inspect'
    | 'autotext'
    | 'field'
    | 'textframe'
    | 'hyperwriter'
    | 'fontwork';

  interface Props {
    kind: DialogKind;
    onexit: () => void;
    onsubmit: (kind: DialogKind, payload: Record<string, unknown>) => void;
    // find & replace needs live results
    findText: string;
    replaceText: string;
    matchCount: number;
    onfindnext: (backward: boolean) => void;
    onreplace: () => void;
    // citations/sources
    sources: Source[];
    citationStyle: CitationStyle;
    onaddsource: (s: Source) => void;
    onremovesource: (id: string) => void;
    oninsertcitation: (s: Source) => void;
    oninsertbibliography: () => void;
    // cross-reference targets
    headings: { id: string; text: string; level: number }[];
    // inspect findings / counts
    findings: { level: string; message: string }[];
    counts: { words: number; characters: number; charactersNoSpaces: number; paragraphs: number; lines: number; pages: number };
  }
  let {
    kind,
    onexit,
    onsubmit,
    findText = $bindable(''),
    replaceText = $bindable(''),
    matchCount,
    onfindnext,
    onreplace,
    sources,
    citationStyle = $bindable<CitationStyle>('APA'),
    onaddsource,
    onremovesource,
    oninsertcitation,
    oninsertbibliography,
    headings,
    findings,
    counts,
  }: Props = $props();

  // Local form state, reset whenever a new dialog kind opens.
  let linkUrl = $state('https://');
  let linkLabel = $state('');
  let imageUrl = $state('');
  let dfont = $state('Times New Roman');
  let dsize = $state(12);
  let dbold = $state(false);
  let ditalic = $state(false);
  let dunderline = $state(false);
  let dcolor = $state('#000000');
  let dhighlight = $state('transparent');
  let align = $state<'left' | 'center' | 'right' | 'justify'>('left');
  let indentLeft = $state(0);
  let spacingBefore = $state(0);
  let spacingAfter = $state(0);
  let lineSpacing = $state('1.5');
  let paper = $state('A4');
  let orientation = $state<'portrait' | 'landscape'>('portrait');
  let mTop = $state(96);
  let mBottom = $state(96);
  let mLeft = $state(96);
  let mRight = $state(96);
  let pageBorder = $state(false);
  let pageBorderColor = $state('#999999');
  let lineNumbers = $state(false);
  let showPageNumbers = $state(false);
  let pageNumberFormat = $state<'decimal' | 'roman' | 'alpha'>('decimal');
  let headerText = $state('');
  let footerText = $state('');
  let hyphenation = $state(false);
  let watermarkText = $state('DRAF');
  let watermarkOpacity = $state(0.12);
  let watermarkRotate = $state(-35);
  let coverTitle = $state('');
  let coverSubtitle = $state('');
  let coverTemplate = $state<'Formal' | 'Minimal' | 'Laporan'>('Formal');
  let category = $state('Umum');
  let equationLatex = $state('E = mc^2');
  let chartKind = $state<'bar' | 'line' | 'pie'>('bar');
  let chartValues = $state('4,7,3,8,5');
  let smartSteps = $state('Langkah 1, Langkah 2, Langkah 3');
  let captionLabel = $state('Gambar');
  let captionText = $state('Keterangan gambar');
  let bookmarkName = $state('');
  let crossrefTarget = $state('');
  let commentText = $state('');
  let textboxText = $state('Teks kotak');
  // LibreOffice Writer dialogs
  let autotextCat = $state('Semua');
  let frameAnchor = $state<Anchor>('toParagraph');
  let frameWrap = $state<Wrap>('right');
  let linkKind = $state<LinkKind>('internet');
  let linkTarget = $state('');
  let linkBookmark = $state('');
  let linkName = $state('');
  let fontworkStyle = $state<'arc' | 'circle' | 'wave' | 'slant'>('arc');
  let wordartText = $state('WordArt');
  let signName = $state('Nama');
  let signTitle = $state('Jabatan');
  let borderSpec = $state('1px solid #888888');
  let picWidth = $state(300);
  let picRotate = $state(0);
  let picAlt = $state('');
  let picWrap = $state<'inline' | 'square' | 'behind' | 'front'>('inline');
  let pageColor = $state('#FFF8E1');
  let fileInput = $state<HTMLInputElement>();

  // New source form
  let newSource = $state<Source>({
    id: '',
    type: 'book',
    authors: '',
    year: String(new Date().getFullYear()),
    title: '',
    container: '',
    location: '',
  });

  function addSource() {
    const id = newSource.id || `src-${Date.now().toString(36)}`;
    onaddsource({ ...newSource, id });
    newSource = { id: '', type: 'book', authors: '', year: String(new Date().getFullYear()), title: '', container: '', location: '' };
  }

  function submitImageFile(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onsubmit('image', { src: String(reader.result), alt: file.name });
    reader.readAsDataURL(file);
    input.value = '';
  }

  const titles: Record<DialogKind, string> = {
    find: 'Cari & Ganti',
    link: 'Sisipkan Tautan',
    image: 'Sisipkan Gambar',
    font: 'Font',
    paragraph: 'Paragraf',
    pagesetup: 'Penyiapan Halaman',
    watermark: 'Tanda Air',
    cover: 'Sampul',
    symbol: 'Simbol',
    equation: 'Persamaan',
    quickparts: 'Bagian Cepat',
    chart: 'Diagram',
    smartart: 'SmartArt',
    caption: 'Keterangan',
    citations: 'Sumber & Sitasi',
    bookmark: 'Penanda',
    crossref: 'Referensi Silang',
    comment: 'Komentar Baru',
    pagecolor: 'Warna Halaman',
    textbox: 'Kotak Teks',
    wordart: 'WordArt',
    signature: 'Garis Tanda Tangan',
    tableborders: 'Batas Tabel',
    pictureformat: 'Format Gambar',
    wordcount: 'Statistik Dokumen',
    inspect: 'Periksa Dokumen',
    autotext: 'AutoText',
    field: 'Sisipkan Field',
    textframe: 'Teks Berjalan (Bingkai)',
    hyperwriter: 'Hyperlink',
    fontwork: 'Fontwork',
  };

  const inputClass =
    'w-full px-2 py-1.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]';
  const labelClass = 'block text-[10px] font-code text-[var(--text-muted)] mb-1';
  const btnPrimary = 'px-3 py-1.5 text-[11px] font-hud bg-[var(--accent-primary)] text-[var(--on-accent)] chamfer-sm';
  const btnGhost = 'px-3 py-1.5 text-[11px] font-hud border border-[var(--border-color)] text-[var(--text-muted)] chamfer-sm hover:bg-[var(--bg-elevated)]';
</script>

<EditorDialog title={titles[kind]} onexit={onexit} width={kind === 'citations' || kind === 'symbol' ? 'max-w-2xl' : 'max-w-md'}>
  {#if kind === 'find'}
    <label class={labelClass} for="d-find">Cari</label>
    <input id="d-find" bind:value={findText} class="{inputClass} mb-2" placeholder="teks yang dicari" />
    <label class={labelClass} for="d-replace">Ganti dengan</label>
    <input id="d-replace" bind:value={replaceText} class="{inputClass} mb-2" placeholder="teks pengganti" />
    <p class="text-[10px] font-code text-[var(--text-muted)] mb-3">{matchCount} kemunculan</p>
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex gap-1">
        <button type="button" onclick={() => onfindnext(true)} class={btnGhost} aria-label="Sebelumnya"><ChevronLeft class="w-3.5 h-3.5" /></button>
        <button type="button" onclick={() => onfindnext(false)} class={btnGhost} aria-label="Berikutnya"><ChevronRight class="w-3.5 h-3.5" /></button>
      </div>
      <button type="button" onclick={onreplace} class={btnPrimary}>GANTI SEMUA</button>
    </div>
  {:else if kind === 'link'}
    <label class={labelClass} for="d-url">URL</label>
    <input id="d-url" bind:value={linkUrl} class="{inputClass} mb-2" placeholder="https://" />
    <label class={labelClass} for="d-label">Teks tampilan (opsional)</label>
    <input id="d-label" bind:value={linkLabel} class="{inputClass} mb-3" placeholder="teks tautan" />
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('link', { href: linkUrl, label: linkLabel })} class={btnPrimary}>SISIPKAN</button>
    </div>
  {:else if kind === 'image'}
    <label class={labelClass} for="d-imgurl">URL gambar</label>
    <div class="flex gap-2 mb-3">
      <input id="d-imgurl" bind:value={imageUrl} class={inputClass} placeholder="https://…" />
      <button type="button" onclick={() => onsubmit('image', { src: imageUrl, alt: 'gambar' })} class={btnPrimary}>OK</button>
    </div>
    <div class="text-center text-[10px] font-code text-[var(--text-muted)] mb-2">— atau —</div>
    <label class="block">
      <span class="inline-block w-full text-center px-3 py-2 text-[11px] font-hud border border-[var(--border-color)] text-[var(--text-primary)] chamfer-sm cursor-pointer hover:bg-[var(--bg-elevated)]">PILIH BERKAS GAMBAR</span>
      <input type="file" accept="image/*" onchange={submitImageFile} class="hidden" />
    </label>
  {:else if kind === 'font'}
    <div class="grid grid-cols-2 gap-2 mb-2">
      <div>
        <label class={labelClass} for="d-font">Jenis huruf</label>
        <input id="d-font" bind:value={dfont} class={inputClass} />
      </div>
      <div>
        <label class={labelClass} for="d-size">Ukuran (pt)</label>
        <input id="d-size" type="number" min="6" max="72" bind:value={dsize} class={inputClass} />
      </div>
    </div>
    <div class="flex items-center gap-3 mb-2 text-[12px]">
      <label class="flex items-center gap-1"><input type="checkbox" bind:checked={dbold} /> Tebal</label>
      <label class="flex items-center gap-1"><input type="checkbox" bind:checked={ditalic} /> Miring</label>
      <label class="flex items-center gap-1"><input type="checkbox" bind:checked={dunderline} /> Garis bawah</label>
    </div>
    <div class="grid grid-cols-2 gap-2 mb-3">
      <div>
        <label class={labelClass} for="d-color">Warna huruf</label>
        <input id="d-color" type="color" bind:value={dcolor} class="w-full h-8 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm" />
      </div>
      <div>
        <label class={labelClass} for="d-hl">Sorotan</label>
        <input id="d-hl" type="color" bind:value={dhighlight} class="w-full h-8 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm" />
      </div>
    </div>
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('font', { family: dfont, size: dsize, bold: dbold, italic: ditalic, underline: dunderline, color: dcolor, highlight: dhighlight })} class={btnPrimary}>TERAPKAN</button>
    </div>
  {:else if kind === 'paragraph'}
    <span class="block text-[10px] font-code text-[var(--text-muted)] mb-1">Perataan</span>
    <div class="flex gap-1 mb-2">
      {#each ['left', 'center', 'right', 'justify'] as a}
        <button type="button" onclick={() => (align = a as typeof align)} class="px-2 py-1 text-[11px] border rounded-sm {align === a ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]' : 'border-[var(--border-color)] text-[var(--text-primary)]'}">{a}</button>
      {/each}
    </div>
    <div class="grid grid-cols-2 gap-2 mb-2">
      <div><label class={labelClass} for="d-ind">Indentasi kiri (px)</label><input id="d-ind" type="number" bind:value={indentLeft} class={inputClass} /></div>
      <div><label class={labelClass} for="d-ls">Jarak baris</label><input id="d-ls" bind:value={lineSpacing} class={inputClass} /></div>
      <div><label class={labelClass} for="d-sb">Sebelum (pt)</label><input id="d-sb" type="number" bind:value={spacingBefore} class={inputClass} /></div>
      <div><label class={labelClass} for="d-sa">Sesudah (pt)</label><input id="d-sa" type="number" bind:value={spacingAfter} class={inputClass} /></div>
    </div>
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('paragraph', { align, indentLeft, lineSpacing, spacingBefore, spacingAfter })} class={btnPrimary}>TERAPKAN</button>
    </div>
  {:else if kind === 'pagesetup'}
    <div class="grid grid-cols-2 gap-2 mb-2">
      <div>
        <label class={labelClass} for="d-paper">Ukuran kertas</label>
        <select id="d-paper" bind:value={paper} class={inputClass}>
          {#each Object.keys(PAPER_SIZES) as p}<option value={p}>{p} — {PAPER_SIZES[p as keyof typeof PAPER_SIZES].label}</option>{/each}
        </select>
      </div>
      <div>
        <label class={labelClass} for="d-orient">Orientasi</label>
        <select id="d-orient" bind:value={orientation} class={inputClass}><option value="portrait">Potret</option><option value="landscape">Lanskap</option></select>
      </div>
    </div>
    <span class="block text-[10px] font-code text-[var(--text-muted)] mb-1">Margin (px)</span>
    <div class="grid grid-cols-4 gap-1 mb-2">
      <input type="number" bind:value={mTop} class={inputClass} title="Atas" />
      <input type="number" bind:value={mBottom} class={inputClass} title="Bawah" />
      <input type="number" bind:value={mLeft} class={inputClass} title="Kiri" />
      <input type="number" bind:value={mRight} class={inputClass} title="Kanan" />
    </div>
    <div class="grid grid-cols-2 gap-2 mb-2">
      <div><label class={labelClass} for="d-hdr">Header</label><input id="d-hdr" bind:value={headerText} class={inputClass} placeholder="teks header" /></div>
      <div><label class={labelClass} for="d-ftr">Footer</label><input id="d-ftr" bind:value={footerText} class={inputClass} placeholder="teks footer" /></div>
    </div>
    <div class="flex flex-wrap items-center gap-3 mb-2 text-[11px]">
      <label class="flex items-center gap-1"><input type="checkbox" bind:checked={showPageNumbers} /> Nomor halaman</label>
      <select bind:value={pageNumberFormat} class="text-[11px] bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm px-1 py-0.5 text-[var(--text-primary)]">
        {#each PAGE_NUMBER_FORMATS as f}<option value={f.key}>{f.label}</option>{/each}
      </select>
    </div>
    <div class="flex items-center gap-3 mb-2 text-[11px]">
      <label class="flex items-center gap-1"><input type="checkbox" bind:checked={pageBorder} /> Batas halaman</label>
      {#if pageBorder}<input type="color" bind:value={pageBorderColor} class="w-6 h-6 rounded-sm" />{/if}
      <label class="flex items-center gap-1"><input type="checkbox" bind:checked={lineNumbers} /> Nomor baris</label>
      <label class="flex items-center gap-1"><input type="checkbox" bind:checked={hyphenation} /> Pemenggalan</label>
    </div>
    <div class="flex justify-end gap-2 mt-3">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('pagesetup', { paper, orientation, mTop, mBottom, mLeft, mRight, headerText, footerText, showPageNumbers, pageNumberFormat, pageBorder, pageBorderColor, lineNumbers, hyphenation })} class={btnPrimary}>TERAPKAN</button>
    </div>
  {:else if kind === 'watermark'}
    <label class={labelClass} for="d-wm">Teks tanda air</label>
    <input id="d-wm" bind:value={watermarkText} class="{inputClass} mb-2" />
    <div class="grid grid-cols-2 gap-2 mb-3">
      <div><label class={labelClass} for="d-wmo">Opasitas</label><input id="d-wmo" type="number" step="0.05" min="0.02" max="0.5" bind:value={watermarkOpacity} class={inputClass} /></div>
      <div><label class={labelClass} for="d-wmr">Rotasi (°)</label><input id="d-wmr" type="number" bind:value={watermarkRotate} class={inputClass} /></div>
    </div>
    <div class="flex justify-between gap-2">
      <button type="button" onclick={() => onsubmit('watermark', { remove: true })} class={btnGhost}>HAPUS</button>
      <div class="flex gap-2">
        <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
        <button type="button" onclick={() => onsubmit('watermark', { text: watermarkText, opacity: watermarkOpacity, rotate: watermarkRotate })} class={btnPrimary}>TERAPKAN</button>
      </div>
    </div>
  {:else if kind === 'cover'}
    <label class={labelClass} for="d-ct">Judul sampul</label>
    <input id="d-ct" bind:value={coverTitle} class="{inputClass} mb-2" />
    <label class={labelClass} for="d-cs">Subjudul</label>
    <input id="d-cs" bind:value={coverSubtitle} class="{inputClass} mb-2" />
    <span class="block text-[10px] font-code text-[var(--text-muted)] mb-1">Gaya</span>
    <div class="flex gap-1 mb-3">
      {#each ['Formal', 'Minimal', 'Laporan'] as t}
        <button type="button" onclick={() => (coverTemplate = t as typeof coverTemplate)} class="px-2 py-1 text-[11px] border rounded-sm {coverTemplate === t ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]' : 'border-[var(--border-color)] text-[var(--text-primary)]'}">{t}</button>
      {/each}
    </div>
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('cover', { title: coverTitle, subtitle: coverSubtitle, template: coverTemplate })} class={btnPrimary}>SISIPKAN</button>
    </div>
  {:else if kind === 'symbol'}
    <div class="flex flex-wrap gap-1 mb-2">
      {#each Object.keys(SYMBOL_SETS) as set}
        <button type="button" onclick={() => (category = set)} class="px-2 py-0.5 text-[10px] font-code border rounded-sm {category === set ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]' : 'border-[var(--border-color)] text-[var(--text-primary)]'}">{set}</button>
      {/each}
    </div>
    <div class="grid grid-cols-10 gap-1">
      {#each (SYMBOL_SETS[category] ?? []) as sym}
        <button type="button" onclick={() => onsubmit('symbol', { char: sym })} class="w-8 h-8 text-[16px] border border-[var(--border-color)] rounded-sm hover:bg-[var(--bg-elevated)] text-[var(--text-primary)]">{sym}</button>
      {/each}
    </div>
  {:else if kind === 'equation'}
    <label class={labelClass} for="d-eq">LaTeX / sintaks persamaan</label>
    <input id="d-eq" bind:value={equationLatex} class="{inputClass} mb-2 font-mono" />
    <div class="flex flex-wrap gap-1 mb-3">
      {#each EQUATION_PRESETS as p}
        <button type="button" onclick={() => (equationLatex = p.latex)} class="px-1.5 py-0.5 text-[10px] font-code border border-[var(--border-color)] rounded-sm hover:border-[var(--accent-primary)] text-[var(--text-primary)]">{p.label}</button>
      {/each}
    </div>
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('equation', { latex: equationLatex })} class={btnPrimary}>SISIPKAN</button>
    </div>
  {:else if kind === 'quickparts'}
    <div class="grid grid-cols-2 gap-2">
      <button type="button" onclick={() => onsubmit('quickparts', { what: 'address' })} class={btnGhost}>Blok Alamat</button>
      <button type="button" onclick={() => onsubmit('quickparts', { what: 'greeting' })} class={btnGhost}>Salam Pembuka</button>
      <button type="button" onclick={() => onsubmit('quickparts', { what: 'closing' })} class={btnGhost}>Penutup Surat</button>
      <button type="button" onclick={() => onsubmit('quickparts', { what: 'signature' })} class={btnGhost}>Tanda Tangan</button>
      <button type="button" onclick={() => onsubmit('quickparts', { what: 'date' })} class={btnGhost}>Tanggal Hari Ini</button>
      <button type="button" onclick={() => onsubmit('quickparts', { what: 'title' })} class={btnGhost}>Judul Dokumen</button>
    </div>
  {:else if kind === 'chart'}
    <div class="flex gap-1 mb-2">
      {#each ['bar', 'line', 'pie'] as c}
        <button type="button" onclick={() => (chartKind = c as typeof chartKind)} class="px-2 py-1 text-[11px] border rounded-sm {chartKind === c ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]' : 'border-[var(--border-color)] text-[var(--text-primary)]'}">{c}</button>
      {/each}
    </div>
    <label class={labelClass} for="d-cv">Nilai (pisahkan koma)</label>
    <input id="d-cv" bind:value={chartValues} class="{inputClass} mb-3" />
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('chart', { kind: chartKind, values: chartValues.split(',').map(Number) })} class={btnPrimary}>SISIPKAN</button>
    </div>
  {:else if kind === 'smartart'}
    <label class={labelClass} for="d-sa">Langkah (pisahkan koma)</label>
    <input id="d-sa" bind:value={smartSteps} class="{inputClass} mb-3" />
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('smartart', { steps: smartSteps.split(',').map((s) => s.trim()) })} class={btnPrimary}>SISIPKAN</button>
    </div>
  {:else if kind === 'caption'}
    <div class="grid grid-cols-2 gap-2 mb-2">
      <div>
        <label class={labelClass} for="d-cl">Label</label>
        <select id="d-cl" bind:value={captionLabel} class={inputClass}><option>Gambar</option><option>Tabel</option><option>Persamaan</option></select>
      </div>
      <div><label class={labelClass} for="d-ctext">Teks</label><input id="d-ctext" bind:value={captionText} class={inputClass} /></div>
    </div>
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('caption', { label: captionLabel, text: captionText })} class={btnPrimary}>SISIPKAN</button>
    </div>
  {:else if kind === 'citations'}
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-2">
        <label class="text-[10px] font-code text-[var(--text-muted)]" for="d-cstyle">Gaya</label>
        <select id="d-cstyle" bind:value={citationStyle} class="text-[11px] bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm px-1 py-0.5 text-[var(--text-primary)]">
          {#each CITATION_STYLES as s}<option value={s}>{s}</option>{/each}
        </select>
      </div>
      <button type="button" onclick={oninsertbibliography} class={btnPrimary}>SISIP DAFTAR PUSTAKA</button>
    </div>
    <div class="space-y-1 mb-3 max-h-48 overflow-y-auto">
      {#if sources.length === 0}<p class="text-[10px] text-[var(--text-muted)]">Belum ada sumber.</p>{/if}
      {#each sources as s (s.id)}
        <div class="flex items-center justify-between gap-2 border border-[var(--border-color)] rounded-sm p-1.5">
          <div class="min-w-0">
            <div class="text-[11px] text-[var(--text-primary)] truncate">{s.title} ({s.year})</div>
            <div class="text-[9px] font-code text-[var(--text-muted)] truncate">{formatSource(s, citationStyle)}</div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <button type="button" onclick={() => oninsertcitation(s)} class="px-1.5 py-0.5 text-[9px] font-code border border-[var(--accent-primary)] text-[var(--accent-primary)] rounded-sm">SITIR</button>
            <button type="button" onclick={() => onremovesource(s.id)} class="text-[var(--status-danger)]"><Trash2 class="w-3 h-3" /></button>
          </div>
        </div>
      {/each}
    </div>
    <div class="border-t border-[var(--border-color)] pt-2">
      <div class="text-[10px] font-code text-[var(--text-muted)] mb-1">Tambah sumber</div>
      <div class="grid grid-cols-2 gap-1 mb-1">
        <input bind:value={newSource.authors} placeholder="Penulis (a; b)" class="text-[11px] px-1.5 py-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]" />
        <input bind:value={newSource.title} placeholder="Judul" class="text-[11px] px-1.5 py-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]" />
        <input bind:value={newSource.year} placeholder="Tahun" class="text-[11px] px-1.5 py-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]" />
        <input bind:value={newSource.container} placeholder="Penerbit / jurnal" class="text-[11px] px-1.5 py-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]" />
      </div>
      <button type="button" onclick={addSource} class="flex items-center gap-1 px-2 py-1 text-[10px] font-hud border border-[var(--accent-primary)] text-[var(--accent-primary)] rounded-sm"><Plus class="w-3 h-3" /> TAMBAH</button>
    </div>
  {:else if kind === 'bookmark'}
    <label class={labelClass} for="d-bm">Nama penanda</label>
    <input id="d-bm" bind:value={bookmarkName} class="{inputClass} mb-3" placeholder="mis. bab-1" />
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('bookmark', { name: bookmarkName })} class={btnPrimary}>SISIPKAN</button>
    </div>
  {:else if kind === 'crossref'}
    <label class={labelClass} for="d-cr">Rujuk ke judul</label>
    <select id="d-cr" bind:value={crossrefTarget} class={inputClass}>
      {#each headings as h}<option value={h.id}>{'—'.repeat(Math.max(0, h.level - 1))} {h.text}</option>{/each}
    </select>
    <div class="flex justify-end gap-2 mt-3">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('crossref', { target: crossrefTarget, label: headings.find((h) => h.id === crossrefTarget)?.text ?? 'rujukan' })} class={btnPrimary}>SISIPKAN</button>
    </div>
  {:else if kind === 'comment'}
    <textarea bind:value={commentText} rows="3" class={inputClass} placeholder="Tulis komentar…"></textarea>
    <div class="flex justify-end gap-2 mt-3">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('comment', { text: commentText })} class={btnPrimary}>KOMENTARI</button>
    </div>
  {:else if kind === 'pagecolor'}
    <div class="flex items-center gap-2 mb-3">
      <input type="color" bind:value={pageColor} class="w-10 h-8" />
      <button type="button" onclick={() => onsubmit('pagecolor', { color: 'transparent' })} class={btnGhost}>Tanpa warna</button>
    </div>
    <button type="button" onclick={() => onsubmit('pagecolor', { color: pageColor })} class={btnPrimary}>TERAPKAN</button>
  {:else if kind === 'textbox'}
    <input bind:value={textboxText} class="{inputClass} mb-3" placeholder="Isi kotak teks" />
    <button type="button" onclick={() => onsubmit('textbox', { text: textboxText })} class={btnPrimary}>SISIPKAN</button>
  {:else if kind === 'wordart'}
    <input bind:value={wordartText} class="{inputClass} mb-3" />
    <button type="button" onclick={() => onsubmit('wordart', { text: wordartText })} class={btnPrimary}>SISIPKAN</button>
  {:else if kind === 'signature'}
    <div class="grid grid-cols-2 gap-2 mb-3">
      <input bind:value={signName} class={inputClass} placeholder="Nama" />
      <input bind:value={signTitle} class={inputClass} placeholder="Jabatan" />
    </div>
    <button type="button" onclick={() => onsubmit('signature', { name: signName, title: signTitle })} class={btnPrimary}>SISIPKAN</button>
  {:else if kind === 'tableborders'}
    <label class={labelClass} for="d-bd">Gaya batas (CSS)</label>
    <input id="d-bd" bind:value={borderSpec} class="{inputClass} mb-3" />
    <div class="flex gap-1 mb-3">
      {#each ['1px solid #888888', '2px solid var(--accent-primary)', '1px dashed #999999', 'none'] as b}
        <button type="button" onclick={() => (borderSpec = b)} class="px-1.5 py-0.5 text-[9px] font-code border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]">{b}</button>
      {/each}
    </div>
    <button type="button" onclick={() => onsubmit('tableborders', { spec: borderSpec })} class={btnPrimary}>TERAPKAN</button>
  {:else if kind === 'pictureformat'}
    <div class="grid grid-cols-2 gap-2 mb-2">
      <div><label class={labelClass} for="d-pw">Lebar (px)</label><input id="d-pw" type="number" bind:value={picWidth} class={inputClass} /></div>
      <div><label class={labelClass} for="d-pr">Putar (°)</label><input id="d-pr" type="number" bind:value={picRotate} class={inputClass} /></div>
    </div>
    <label class={labelClass} for="d-pa">Teks alternatif</label>
    <input id="d-pa" bind:value={picAlt} class="{inputClass} mb-2" />
    <span class="block text-[10px] font-code text-[var(--text-muted)] mb-1">Bungkus teks</span>
    <div class="flex gap-1 mb-3">
      {#each ['inline', 'square', 'behind', 'front'] as w}
        <button type="button" onclick={() => (picWrap = w as typeof picWrap)} class="px-2 py-1 text-[10px] border rounded-sm {picWrap === w ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]' : 'border-[var(--border-color)] text-[var(--text-primary)]'}">{w}</button>
      {/each}
    </div>
    <div class="flex justify-end gap-2">
      <button type="button" onclick={() => onsubmit('pictureformat', { reset: true })} class={btnGhost}>RESET</button>
      <button type="button" onclick={() => onsubmit('pictureformat', { width: picWidth, rotate: picRotate, alt: picAlt, wrap: picWrap })} class={btnPrimary}>TERAPKAN</button>
    </div>
  {:else if kind === 'wordcount'}
    <table class="w-full text-[12px]">
      <tbody>
        {#each [['Kata', counts.words], ['Karakter', counts.characters], ['Karakter (tanpa spasi)', counts.charactersNoSpaces], ['Paragraf', counts.paragraphs], ['Baris', counts.lines], ['Perkiraan halaman', counts.pages]] as [label, value]}
          <tr class="border-b border-[var(--border-color)]/40">
            <td class="py-1 text-[var(--text-muted)]">{label}</td>
            <td class="py-1 text-right font-code text-[var(--text-primary)]">{value}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else if kind === 'inspect'}
    {#if findings.length === 0}
      <p class="text-[11px] font-code text-[var(--status-success)]">Tidak ada temuan. Dokumen bersih.</p>
    {:else}
      <ul class="space-y-1.5">
        {#each findings as f}
          <li class="flex items-start gap-2 text-[12px]">
            <span class="mt-1 w-1.5 h-1.5 rounded-full shrink-0" style:background={f.level === 'error' ? 'var(--status-danger)' : f.level === 'warning' ? 'var(--status-warning)' : 'var(--accent-primary)'}></span>
            <span class="text-[var(--text-primary)]">{f.message}</span>
          </li>
        {/each}
      </ul>
    {/if}
  {:else if kind === 'autotext'}
    <div class="flex flex-wrap gap-1 mb-2">
      {#each ['Semua', ...new Set(DEFAULT_AUTOTEXT.map((a) => a.category))] as cat}
        <button type="button" onclick={() => (autotextCat = cat)} class="px-2 py-0.5 text-[10px] font-code border rounded-sm {autotextCat === cat ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]' : 'border-[var(--border-color)] text-[var(--text-primary)]'}">{cat}</button>
      {/each}
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-1 max-h-64 overflow-y-auto">
      {#each DEFAULT_AUTOTEXT.filter((a) => autotextCat === 'Semua' || a.category === autotextCat) as entry (entry.key)}
        <button type="button" onclick={() => onsubmit('autotext', { key: entry.key })} class="text-left px-2 py-1 border border-[var(--border-color)] rounded-sm hover:border-[var(--accent-primary)] hover:bg-[var(--bg-elevated)]">
          <div class="flex items-center justify-between">
            <span class="text-[11px] text-[var(--text-primary)]">{entry.label}</span>
            <span class="text-[9px] font-code text-[var(--accent-primary)]">{entry.key}</span>
          </div>
          <div class="text-[9px] font-code text-[var(--text-muted)] truncate">{entry.category}</div>
        </button>
      {/each}
    </div>
  {:else if kind === 'field'}
    <div class="grid grid-cols-2 gap-1">
      {#each [['insertedBy', 'Disisipkan oleh'], ['author', 'Penulis'], ['createdOn', 'Tanggal dibuat'], ['modifiedOn', 'Tanggal diubah'], ['pageNumber', 'Nomor halaman'], ['totalPages', 'Jumlah halaman'], ['wordCount', 'Jumlah kata'], ['title', 'Judul dokumen'], ['fileName', 'Nama berkas']] as [k, label]}
        <button type="button" onclick={() => onsubmit('field', { field: k })} class={btnGhost}>{label}</button>
      {/each}
    </div>
  {:else if kind === 'textframe'}
    <label class={labelClass} for="d-tf">Isi bingkai</label>
    <textarea id="d-tf" bind:value={textboxText} rows="2" class="{inputClass} mb-2"></textarea>
    <div class="grid grid-cols-2 gap-2 mb-2">
      <div>
        <label class={labelClass} for="d-tfa">Jangkar</label>
        <select id="d-tfa" bind:value={frameAnchor} class={inputClass}>
          <option value="toParagraph">Ke paragraf</option>
          <option value="toCharacter">Ke karakter</option>
          <option value="toPage">Ke halaman</option>
          <option value="asCharacter">Sebagai karakter</option>
        </select>
      </div>
      <div>
        <label class={labelClass} for="d-tfw">Bungkus teks</label>
        <select id="d-tfw" bind:value={frameWrap} class={inputClass}>
          <option value="none">Tanpa</option>
          <option value="left">Kiri</option>
          <option value="right">Kanan</option>
          <option value="both">Kedua sisi</option>
        </select>
      </div>
    </div>
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('textframe', { text: textboxText, anchor: frameAnchor, wrap: frameWrap })} class={btnPrimary}>SISIPKAN</button>
    </div>
  {:else if kind === 'hyperwriter'}
    <div class="flex gap-1 mb-2">
      {#each [['internet', 'Internet'], ['mail', 'Surel'], ['document', 'Dokumen'], ['newDocument', 'Dokumen Baru']] as [k, label]}
        <button type="button" onclick={() => (linkKind = k as typeof linkKind)} class="px-2 py-1 text-[10px] font-code border rounded-sm {linkKind === k ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]' : 'border-[var(--border-color)] text-[var(--text-primary)]'}">{label}</button>
      {/each}
    </div>
    {#if linkKind === 'document'}
      <label class={labelClass} for="d-hwd">Tujuan (judul/penanda)</label>
      <select id="d-hwd" bind:value={linkBookmark} class="{inputClass} mb-2">
        <option value="">— pilih tujuan —</option>
        {#each headings as h}<option value={h.id}>{h.text}</option>{/each}
      </select>
    {:else}
      <label class={labelClass} for="d-hwt">Tujuan</label>
      <input id="d-hwt" bind:value={linkTarget} class="{inputClass} mb-2" placeholder={linkKind === 'mail' ? 'nama@contoh.id' : 'https://'} />
    {/if}
    <label class={labelClass} for="d-hwtext">Teks</label>
    <input id="d-hwtext" bind:value={linkLabel} class="{inputClass} mb-2" />
    <label class={labelClass} for="d-hwname">Nama (target)</label>
    <input id="d-hwname" bind:value={linkName} class="{inputClass} mb-3" placeholder="opsional" />
    <div class="flex justify-end gap-2">
      <button type="button" onclick={onexit} class={btnGhost}>BATAL</button>
      <button type="button" onclick={() => onsubmit('hyperwriter', { kind: linkKind, target: linkTarget, text: linkLabel, name: linkName, bookmark: linkBookmark })} class={btnPrimary}>TERAPKAN</button>
    </div>
  {:else if kind === 'fontwork'}
    <label class={labelClass} for="d-fw">Teks Fontwork</label>
    <input id="d-fw" bind:value={wordartText} class="{inputClass} mb-2" />
    <div class="flex gap-1 mb-3">
      {#each [['arc', 'Busur'], ['circle', 'Lingkaran'], ['wave', 'Gelombang'], ['slant', 'Miring']] as [k, label]}
        <button type="button" onclick={() => (fontworkStyle = k as typeof fontworkStyle)} class="px-2 py-1 text-[11px] border rounded-sm {fontworkStyle === k ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]' : 'border-[var(--border-color)] text-[var(--text-primary)]'}">{label}</button>
      {/each}
    </div>
    <button type="button" onclick={() => onsubmit('fontwork', { text: wordartText, style: fontworkStyle })} class={btnPrimary}>SISIPKAN</button>
  {/if}
</EditorDialog>

<input bind:this={fileInput} type="file" class="hidden" />
