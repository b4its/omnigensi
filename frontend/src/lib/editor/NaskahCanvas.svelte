<script lang="ts">
  /**
   * NaskahCanvas — the A4 "paper" the manuscript is typed on.
   *
   * It owns the `contentEditable` region and everything page-level: page size,
   * margins, zoom, and the page-break visual. Formatting *commands* live in
   * the parent page + ribbon; this component only:
   *   • keeps the DOM in sync with the `html` prop (without clobbering the
   *     caret while the user types),
   *   • reports edits upward,
   *   • exposes `focus()` so the ribbon can return the caret.
   */
  import { onMount } from 'svelte';
  import type { TextStats } from './commands';
  import { textStats, selectionIn } from './commands';

  interface PageSetup {
    width: number; // px at 96dpi
    minHeight: number;
    marginY: number;
    marginX: number;
    fontFamily: string;
    fontSize: number; // pt
    lineHeight: number;
  }

  interface Props {
    html: string;
    zoom?: number;
    setup?: Partial<PageSetup>;
    onchange?: (html: string, stats: TextStats) => void;
  }

  let { html, zoom = 100, setup = {}, onchange }: Props = $props();

  let editorEl = $state<HTMLElement>();
  let lastSyncedHtml = '';

  const page: PageSetup = $derived({
    width: 794,
    minHeight: 1123,
    marginY: 96,
    marginX: 96,
    fontFamily: "'Times New Roman', Georgia, serif",
    fontSize: 12,
    lineHeight: 1.5,
    ...setup,
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

  // Sync inbound html → DOM, but only when it genuinely differs from what the
  // user has produced, so typing is never interrupted by a re-render.
  $effect(() => {
    if (!editorEl) return;
    if (html !== lastSyncedHtml && html !== editorEl.innerHTML) {
      // Preserve caret when the change is external but the region still has
      // focus (e.g. programmatic undo); otherwise just replace.
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
      el.removeAttribute('class');
      el.removeAttribute('id');
      el.removeAttribute('style');
      el.removeAttribute('width');
      el.removeAttribute('height');
    });
    return doc.body.innerHTML;
  }
</script>

<div class="naskah-stage overflow-auto bg-[var(--bg-primary)]">
  <div class="naskah-stage-inner">
    <div
      class="naskah-paper"
      style:width="{page.width * (zoom / 100)}px"
      style:min-height="{page.minHeight * (zoom / 100)}px"
      style:padding="{page.marginY * (zoom / 100)}px {page.marginX * (zoom / 100)}px"
      style:font-family={page.fontFamily}
      style:font-size="{page.fontSize * (zoom / 100)}pt"
      style:line-height={page.lineHeight}
    >
      <!-- eslint-disable-next-line svelte/no-at-html-tags -->
      <div
        bind:this={editorEl}
        class="naskah-content"
        contenteditable="true"
        role="textbox"
        aria-multiline="true"
        aria-label="Naskah dokumen"
        spellcheck="true"
        oninput={handleInput}
        onpaste={handlePaste}
      ></div>
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
  /* min-width:max-content keeps the centred paper from being *shrunk* by the
     flex/grid alignment when it overflows; combined with margin:auto it stays
     centred when it fits and scrolls from the left edge when it doesn't. */
  .naskah-stage-inner {
    min-width: max-content;
    min-height: 100%;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 1rem;
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
    background: var(--bg-surface);
    color: var(--text-primary);
    box-shadow: 0 8px 40px rgba(0, 0, 0, 0.45), 0 0 0 1px var(--border-color);
    outline: none;
    box-sizing: border-box;
    transition: width 0.12s ease, min-height 0.12s ease;
  }
  .naskah-content {
    outline: none;
    min-height: 100%;
  }
  .naskah-content:focus {
    outline: none;
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
