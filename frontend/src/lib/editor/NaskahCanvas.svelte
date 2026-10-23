<script lang="ts">
  /**
   * NaskahCanvas — the "paper" the manuscript is typed on.
   *
   * It owns the `contentEditable` region and everything page-level: paper size,
   * orientation, margins, columns, page colour, page borders, watermark and the
   * header/footer bands. Formatting *commands* live in the parent page + ribbon;
   * this component only:
   *   • keeps the DOM in sync with the `html` prop (without clobbering the
   *     caret while the user types),
   *   • reports edits upward,
   *   • exposes `focus()` / `getEl()` so commands can target the canvas.
   */
  import { onMount } from 'svelte';
  import type { TextStats } from './commands';
  import { textStats, selectionIn } from './commands';
  import type { SectionSetup } from './pageSetup';
  import { footerMarkup, headerMarkup, pageDimensions, paperStyle, watermarkMarkup } from './pageSetup';

  interface Props {
    html: string;
    zoom?: number;
    /** Reading mode: drop the paper chrome and present a clean, wide column. */
    reading?: boolean;
    section: SectionSetup;
    /** Number of sheets shown side by side (1 = single page, 2 = book view). */
    pageView?: 1 | 2;
    /** Show ruler ticks above the paper. */
    ruler?: boolean;
    /** Show the non-printing formatting marks. */
    showMarks?: boolean;
    /** Draw Word/Writer margin comment balloons beside the text. */
    showCommentMargins?: boolean;
    onchange?: (html: string, stats: TextStats) => void;
    /** Click on a margin balloon. */
    oncommentclick?: (id: string) => void;
  }

  let {
    html,
    zoom = 100,
    reading = false,
    section,
    pageView = 1,
    ruler = false,
    showMarks = false,
    showCommentMargins = false,
    onchange,
    oncommentclick,
  }: Props = $props();

  let editorEl = $state<HTMLElement>();
  let lastSyncedHtml = '';

  const dims = $derived(pageDimensions(section));

  // Margin notes: recomputed whenever the document text changes.
  let notes = $state<{ id: string; text: string; author: string; top: number; color: string }[]>([]);
  const COMMENT_COLORS = ['#0066FF', '#FF0055', '#00A86B', '#B8860B', '#7C4DFF'];

  function recomputeNotes() {
    if (!editorEl || !showCommentMargins) {
      notes = [];
      return;
    }
    const anchors = Array.from(editorEl.querySelectorAll<HTMLElement>('[data-comment]'));
    notes = anchors.map((el, i) => {
      const paperTop = editorEl!.getBoundingClientRect().top;
      return {
        id: el.getAttribute('data-comment') ?? String(i),
        text: el.getAttribute('data-comment-text') ?? '',
        author: el.getAttribute('data-author') ?? 'Penulis',
        top: el.getBoundingClientRect().top - paperTop,
        color: COMMENT_COLORS[i % COMMENT_COLORS.length],
      };
    });
  }

  $effect(() => {
    if (showCommentMargins) {
      // Reading `html` makes this recompute after every edit.
      void html;
      void section;
      requestAnimationFrame(recomputeNotes);
    } else {
      notes = [];
    }
  });

  export function focus() {
    if (!editorEl) return;
    editorEl.focus();
    selectionIn(editorEl);
  }

  export function getEl(): HTMLElement | undefined {
    return editorEl;
  }

  export function stats(): TextStats | null {
    return editorEl ? textStats(editorEl) : null;
  }

  export function pageCount(): number {
    if (!editorEl) return 1;
    const contentHeight = editorEl.scrollHeight;
    const usable = (dims.height - section.margins.top - section.margins.bottom) * (zoom / 100);
    const breaks = editorEl.querySelectorAll('.naskah-pagebreak').length;
    return Math.max(breaks + 1, Math.ceil(contentHeight / Math.max(1, usable)));
  }

  // Sync inbound html → DOM, but only when it genuinely differs from what the
  // user has produced, so typing is never interrupted by a re-render.
  $effect(() => {
    if (!editorEl) return;
    if (html !== lastSyncedHtml && html !== editorEl.innerHTML) {
      editorEl.innerHTML = html;
      lastSyncedHtml = html;
    }
  });

  onMount(() => {
    if (editorEl) {
      editorEl.innerHTML = html;
      lastSyncedHtml = html;
    }
  });

  function handleInput() {
    if (!editorEl) return;
    lastSyncedHtml = editorEl.innerHTML;
    onchange?.(editorEl.innerHTML, textStats(editorEl));
  }

  // Paste as clean text+basic markup: strip external styles to keep the
  // document consistent, then drop the clipboard HTML in as-is.
  function handlePaste(e: ClipboardEvent) {
    if (!e.clipboardData) return;
    const htmlData = e.clipboardData.getData('text/html');
    const text = e.clipboardData.getData('text/plain');
    e.preventDefault();
    if (htmlData) {
      document.execCommand('insertHTML', false, sanitizePaste(htmlData));
    } else {
      document.execCommand('insertText', false, text);
    }
  }

  function sanitizePaste(raw: string): string {
    const doc = new DOMParser().parseFromString(raw, 'text/html');
    // Drop script/style and every class/id so foreign styling cannot leak.
    doc.querySelectorAll('script,style,meta,link').forEach((n) => n.remove());
    doc.querySelectorAll('*').forEach((el) => {
      if (el.hasAttribute('data-object') || el.hasAttribute('data-style')) return;
      el.removeAttribute('class');
      el.removeAttribute('id');
      el.removeAttribute('style');
      el.removeAttribute('width');
      el.removeAttribute('height');
    });
    return doc.body.innerHTML;
  }

  // Ruler ticks: one mark every simulated centimetre across the page width.
  const rulerTicks = $derived(
    Array.from({ length: Math.floor(dims.width / 38) }, (_, i) => i)
  );
</script>

<div class="naskah-stage overflow-auto bg-[var(--bg-primary)]" class:reading class:dark-paper={section.darkPaper}>
  {#if ruler && !reading}
    <div class="naskah-ruler" style:width="{dims.width * (zoom / 100)}px">
      {#each rulerTicks as t}
        <span class="tick" class:major={t % 5 === 0}>{t % 5 === 0 ? t : ''}</span>
      {/each}
    </div>
  {/if}
  <div class="naskah-stage-inner" class:book={pageView === 2 && !reading}>
    <div
      class="naskah-paper"
      class:show-marks={showMarks}
      style:width="{dims.width * (zoom / 100)}px"
      style:min-height="{reading ? 0 : dims.height * (zoom / 100)}px"
      style:font-size={reading ? `${Math.max(13, 12)}pt` : `${12 * (zoom / 100)}pt`}
      style:line-height={reading ? 1.75 : undefined}
      style={reading ? undefined : paperStyle(section)}
    >
      {#if section.watermark && !reading}
        <!-- eslint-disable-next-line svelte/no-at-html-tags -->
        {@html watermarkMarkup(section)}
      {/if}

      {#if !reading && (section.header || section.showPageNumbers)}
        <div class="naskah-hf naskah-header" style:top="{section.headerFromTop * (zoom / 100)}px">
          <!-- eslint-disable-next-line svelte/no-at-html-tags -->
          {@html headerMarkup(section)}
        </div>
      {/if}

      <div
        bind:this={editorEl}
        class="naskah-content"
        class:draft-view={reading}
        contenteditable="true"
        role="textbox"
        aria-multiline="true"
        aria-label="Naskah dokumen"
        spellcheck="true"
        oninput={handleInput}
        onpaste={handlePaste}
      ></div>

      {#if !reading && (section.footer || section.showPageNumbers)}
        <div class="naskah-hf naskah-footer" style:bottom="{section.footerFromBottom * (zoom / 100)}px">
          <!-- eslint-disable-next-line svelte/no-at-html-tags -->
          {@html footerMarkup(section)}
        </div>
      {/if}

      {#if showCommentMargins && notes.length > 0}
        <div class="naskah-margin-balloons" contenteditable="false" aria-hidden="true">
          {#each notes as n (n.id)}
            <button
              type="button"
              class="naskah-balloon"
              style:top="{n.top}px"
              style:border-left-color={n.color}
              title="{n.author}: {n.text}"
              onclick={() => oncommentclick?.(n.id)}
            >
              <span class="balloon-author">{n.author}</span>
              <span class="balloon-text">{n.text}</span>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  /* Scroll container: fills the stage and scrolls both axes when the paper is
     larger than the viewport (e.g. zoom > 100%). */
  .naskah-stage {
    width: 100%;
    height: 100%;
  }
  .naskah-ruler {
    position: sticky;
    top: 0;
    margin: 0 auto;
    height: 18px;
    background: var(--bg-elevated);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: flex-end;
    z-index: 1;
    font-size: 8px;
    color: var(--text-muted);
    overflow: hidden;
  }
  .naskah-ruler .tick {
    width: 38px;
    height: 5px;
    border-left: 1px solid var(--border-color);
    box-sizing: border-box;
    text-align: left;
    padding-left: 2px;
  }
  .naskah-ruler .tick.major {
    height: 10px;
    border-left-color: var(--text-muted);
  }
  /* min-width:max-content keeps the centred paper from being *shrunk* by the
     flex/grid alignment when it overflows; combined with margin:auto it stays
     centred when it fits and scrolls from the left edge when it doesn't. */
  .naskah-stage-inner {
    min-width: max-content;
    min-height: 100%;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    gap: 1.5rem;
    padding: 1rem;
  }
  .naskah-stage-inner.book {
    justify-content: flex-start;
    padding-left: 2rem;
  }
  @media (min-width: 768px) {
    .naskah-stage-inner {
      padding: 2rem;
    }
  }
  .naskah-paper {
    /* Paper surface follows the active theme so dark mode isn't a blinding
       white rectangle, but text keeps a high-contrast ink colour. */
    flex-shrink: 0;
    position: relative;
    background: var(--bg-surface);
    color: var(--text-primary);
    box-shadow: 0 8px 40px rgba(0, 0, 0, 0.45), 0 0 0 1px var(--border-color);
    outline: none;
    box-sizing: border-box;
    transition: width 0.12s ease, min-height 0.12s ease;
  }
  .naskah-stage.dark-paper .naskah-paper {
    background: #1e1e1e;
    color: #e6e6e6;
  }
  .naskah-content {
    outline: none;
    min-height: 100%;
    position: relative;
    z-index: 1;
  }
  .naskah-content:focus {
    outline: none;
  }
  /* Formatting marks: visible pilcrows, spaces and tabs, Word-style. */
  .naskah-paper.show-marks .naskah-content :global(p)::after {
    content: '¶';
    color: rgba(128, 128, 128, 0.45);
    margin-left: 2px;
  }
  /* Header / footer bands sit in the page margins. */
  /* Writer/Word margin comment balloons: a narrow column to the right of the
     paper. Absolute so they scroll with the page and never affect layout. */
  .naskah-margin-balloons {
    position: absolute;
    top: 0;
    left: 100%;
    width: 190px;
    margin-left: 12px;
    height: 100%;
    pointer-events: none;
  }
  .naskah-balloon {
    position: absolute;
    left: 0;
    width: 190px;
    pointer-events: auto;
    text-align: left;
    background: var(--bg-elevated);
    border: 1px solid var(--border-color);
    border-left-width: 3px;
    border-radius: 3px;
    padding: 4px 6px;
    font-size: 10px;
    line-height: 1.3;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
    cursor: pointer;
  }
  .naskah-balloon:hover {
    border-color: var(--accent-primary);
  }
  .balloon-author {
    display: block;
    font-size: 8px;
    letter-spacing: 0.05em;
    color: var(--accent-primary);
    text-transform: uppercase;
    margin-bottom: 1px;
  }
  .balloon-text {
    display: block;
    color: var(--text-primary);
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
  }
  /* Highlighted comment spans inside the text. */
  .naskah-content :global([data-comment]) {
    background: rgba(255, 235, 59, 0.18);
    border-bottom: 1px dotted currentColor;
  }
  .naskah-hf {
    position: absolute;
    left: 0;
    right: 0;
    padding: 0 2.5cm;
    font-size: 0.8em;
    color: var(--text-muted);
    display: flex;
    justify-content: space-between;
    align-items: center;
    pointer-events: none;
    z-index: 0;
  }
  /* Reading mode: a wide, shadowless column centred for comfortable reading —
     the page-break markers are hidden because pagination is irrelevant here. */
  .naskah-stage.reading .naskah-stage-inner {
    padding: 1.5rem 1rem;
  }
  .naskah-stage.reading .naskah-paper {
    width: min(760px, calc(100vw - 2rem)) !important;
    max-width: 760px;
    box-shadow: none;
    background: transparent;
  }
  .naskah-stage.reading :global(.naskah-pagebreak) {
    display: none;
  }
  /* Global content styles for anything inserted or typed inside the paper. */
  .naskah-content :global(h1) {
    font-size: 2em;
    font-weight: 700;
    margin: 0.6em 0 0.4em;
  }
  .naskah-content :global(h2) {
    font-size: 1.5em;
    font-weight: 700;
    margin: 0.6em 0 0.35em;
  }
  .naskah-content :global(h3) {
    font-size: 1.25em;
    font-weight: 700;
    margin: 0.5em 0 0.3em;
  }
  .naskah-content :global(h4) {
    font-size: 1.1em;
    font-weight: 700;
    margin: 0.5em 0 0.3em;
  }
  .naskah-content :global(p) {
    margin: 0 0 0.7em;
  }
  .naskah-content :global(blockquote) {
    border-left: 3px solid var(--accent-secondary);
    margin: 0.7em 0;
    padding-left: 0.9em;
    color: var(--text-muted);
    font-style: italic;
  }
  .naskah-content :global(pre) {
    font-family: 'JetBrains Mono', monospace;
    background: var(--bg-elevated);
    padding: 0.75em;
    border-radius: 4px;
    overflow-x: auto;
  }
  .naskah-content :global(ul),
  .naskah-content :global(ol) {
    padding-left: 1.6em;
    margin: 0 0 0.7em;
  }
  .naskah-content :global(ul) {
    list-style: disc;
  }
  .naskah-content :global(ol) {
    list-style: decimal;
  }
  .naskah-content :global(ul[data-list='check']) {
    list-style: none;
    padding-left: 0.6em;
  }
  .naskah-content :global(a) {
    color: var(--accent-primary);
    text-decoration: underline;
  }
  .naskah-content :global(img) {
    max-width: 100%;
    height: auto;
    border-radius: 2px;
  }
  .naskah-content :global(table),
  .naskah-content :global(.naskah-table) {
    border-collapse: collapse;
    width: 100%;
    margin: 0.7em 0;
  }
  .naskah-content :global(td),
  .naskah-content :global(th) {
    border: 1px solid var(--border-color);
    padding: 6px 9px;
    vertical-align: top;
  }
  .naskah-content :global(th) {
    background: var(--bg-elevated);
    font-weight: 700;
  }
  /* Banded rows, applied when a table style turns striping on. */
  .naskah-content :global(table[data-banded] tbody tr:nth-child(even)) {
    background: rgba(128, 128, 128, 0.08);
  }
  .naskah-content :global(hr) {
    border: 0;
    border-top: 1px solid var(--border-color);
    margin: 1em 0;
  }
  .naskah-content :global(.naskah-pagebreak) {
    height: 0;
    border-top: 2px dashed var(--status-warning);
    margin: 1.5em 0;
    position: relative;
  }
  .naskah-content :global(.naskah-pagebreak)::after {
    content: 'PAGE BREAK';
    position: absolute;
    right: 0;
    top: -0.7em;
    font-size: 8px;
    letter-spacing: 0.1em;
    color: var(--status-warning);
    background: var(--bg-surface);
    padding: 0 4px;
  }
</style>
