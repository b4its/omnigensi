/**
 * Word-style editing primitives for the Naskah Studio rich-text canvas.
 *
 * The canvas is a `contentEditable` region. Simple inline toggles (bold,
 * italic, lists, alignment…) go through `document.execCommand`, which still
 * has the broadest browser support for selection-aware formatting and is
 * what every lightweight editor on the web relies on today. Everything that
 * `execCommand` cannot express — font family/size, colours, headings,
 * line-height, insertion of custom markup — is done with the Range API in
 * this module so the page component stays declarative.
 *
 * Keeping the DOM manipulation here (instead of in the .svelte file) makes
 * the behaviour testable and keeps the ribbon dumb: it only calls commands.
 */

export type Align = 'left' | 'center' | 'right' | 'justify';

import { plainText } from './text';

const BLOCK_SELECTOR = 'p,div,h1,h2,h3,h4,h5,h6,li,blockquote,pre';

function exec(command: string, value?: string): boolean {
	try {
		return document.execCommand(command, false, value);
	} catch {
		return false;
	}
}

/** True when the caret/selection currently sits inside the given block tag. */
export function isBlock(tag: string): boolean {
	const sel = window.getSelection();
	if (!sel || !sel.anchorNode) return false;
	let node: Node | null = sel.anchorNode;
	while (node) {
		if (node.nodeType === Node.ELEMENT_NODE && (node as Element).tagName === tag.toUpperCase()) {
			return true;
		}
		node = node.parentNode;
	}
	return false;
}

/** Nearest block element wrapping the caret, or null. */
export function currentBlock(): HTMLElement | null {
	const sel = window.getSelection();
	if (!sel || !sel.anchorNode) return null;
	let node: Node | null = sel.anchorNode;
	while (node && node !== document.body) {
		if (
			node.nodeType === Node.ELEMENT_NODE &&
			(node as Element).matches(BLOCK_SELECTOR)
		) {
			return node as HTMLElement;
		}
		node = node.parentNode;
	}
	return null;
}

/** Force a selection to exist inside `root` when the editor lost focus. */
export function selectionIn(root: HTMLElement): Selection | null {
	const sel = window.getSelection();
	if (!sel) return null;
	if (sel.rangeCount === 0 || !root.contains(sel.anchorNode)) {
		const range = document.createRange();
		range.selectNodeContents(root);
		range.collapse(false);
		sel.removeAllRanges();
		sel.addRange(range);
	}
	return sel;
}

// ── Inline character formatting ────────────────────────────────────────────
export const fmt = {
	bold: () => exec('bold'),
	italic: () => exec('italic'),
	underline: () => exec('underline'),
	strikethrough: () => exec('strikeThrough'),
	superscript: () => exec('superscript'),
	subscript: () => exec('subscript'),
	clear: () => {
		exec('removeFormat');
		const block = currentBlock();
		if (block) {
			block.removeAttribute('style');
			block.removeAttribute('class');
		}
	},
	highlight: (color: string) => {
		// hiliteColor works in Chromium/WebKit; backColor is the IE/Gecko name.
		if (!exec('hiliteColor', color)) exec('backColor', color);
	},
	color: (color: string) => exec('foreColor', color),
	fontName: (name: string) => exec('fontName', name),
	fontSize: (pt: number) => {
		// execCommand sizes are legacy 1–7 buckets, not points. Wrap in a span
		// with an explicit pt size for predictable results.
		const sel = window.getSelection();
		if (!sel || sel.rangeCount === 0) return;
		const range = sel.getRangeAt(0);
		if (range.collapsed) return;
		const span = document.createElement('span');
		span.style.fontSize = `${pt}pt`;
		try {
			range.surroundContents(span);
		} catch {
			// surroundContents throws on ranges that bisect elements; fall back
			// to the legacy command then normalise via CSS-less downgrade.
			exec('fontSize', '7');
		}
		sel.removeAllRanges();
		const r = document.createRange();
		r.selectNodeContents(span);
		sel.addRange(r);
	},
	changeCase: (mode: 'upper' | 'lower' | 'title' | 'sentence') => {
		const sel = window.getSelection();
		if (!sel || sel.rangeCount === 0) return;
		const text = sel.toString();
		if (!text) return;
		let out = text;
		if (mode === 'upper') out = text.toUpperCase();
		else if (mode === 'lower') out = text.toLowerCase();
		else if (mode === 'title')
			out = text.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
		else out = text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
		exec('insertText', out);
	},
};

// ── Paragraph formatting ───────────────────────────────────────────────────
export const para = {
	align: (a: Align) => {
		const map: Record<Align, string> = {
			left: 'justifyLeft',
			center: 'justifyCenter',
			right: 'justifyRight',
			justify: 'justifyFull',
		};
		exec(map[a]);
	},
	bulletList: () => exec('insertUnorderedList'),
	numberList: () => exec('insertOrderedList'),
	indent: () => exec('indent'),
	outdent: () => exec('outdent'),
	/** Apply a vertical margin + line-height to the block around the caret. */
	lineHeight: (value: string) => {
		const blocks = selectedBlocks();
		for (const b of blocks) b.style.lineHeight = value;
	},
	spacingAfter: (pt: number) => {
		for (const b of selectedBlocks()) b.style.marginBottom = `${pt}pt`;
	},
	/** Convert the current block(s) into a heading (or paragraph when tag=p). */
	heading: (tag: 'p' | 'h1' | 'h2' | 'h3' | 'h4') => {
		exec('formatBlock', tag);
	},
	quote: () => exec('formatBlock', 'blockquote'),
	pre: () => exec('formatBlock', 'pre'),
	hr: () => exec('insertHorizontalRule'),
};

/** Every block element touched by the current selection. */
export function selectedBlocks(): HTMLElement[] {
	const sel = window.getSelection();
	if (!sel || sel.rangeCount === 0) return [];
	const range = sel.getRangeAt(0);
	const root = range.commonAncestorContainer;
	const scope: ParentNode =
		root.nodeType === Node.ELEMENT_NODE ? (root as Element) : root.parentNode ?? document.body;
	const blocks = Array.from(scope.querySelectorAll<HTMLElement>(BLOCK_SELECTOR));
	const containing = currentBlock();
	if (blocks.length === 0 && containing) return [containing];
	return blocks.filter((b) => range.intersectsNode(b));
}

// ── Insertions ─────────────────────────────────────────────────────────────
export const insert = {
	/**
	 * Insert an HTML block at the caret.
	 *
	 * `execCommand('insertHTML')` pastes *inline* when the caret sits inside a
	 * paragraph, which nested headings and tables inside a `<p>` (invalid
	 * markup, and visually broken). When the payload starts with a block
	 * element we split the paragraph first: insert a break at the caret, then
	 * the block, then leave the caret on a fresh paragraph after it.
	 */
	html: (html: string) => {
		const startsBlock = startsWithBlock(html);
		if (!startsBlock) return exec('insertHTML', html);

		const sel = window.getSelection();
		const inParagraph = (() => {
			let node: Node | null = sel?.anchorNode ?? null;
			while (node && node !== document.body) {
				if (node.nodeType === Node.ELEMENT_NODE) {
					const tag = (node as Element).tagName;
					if (tag === 'P' || tag === 'DIV' || /^H[1-6]$/.test(tag) || tag === 'LI') return true;
				}
				node = node.parentNode;
			}
			return false;
		})();

		if (inParagraph) {
			// Finish the current block, drop in the payload, then open a new
			// paragraph so the writer keeps typing on a clean line.
			exec('insertParagraph');
		}
		exec('insertHTML', html);
		if (inParagraph) exec('insertParagraph');
		exec('insertHTML', '<br/>');
	},
	/** Raw HTML without block splitting (inline spans, links, images). */
	inlineHtml: (html: string) => exec('insertHTML', html),
	text: (text: string) => exec('insertText', text),
	link: (href: string, label?: string) => {
		const sel = window.getSelection();
		const hasText = sel && !sel.isCollapsed;
		if (hasText) {
			exec('createLink', href);
		} else {
			insert.inlineHtml(
				`<a href="${escapeAttr(href)}" target="_blank" rel="noopener">${escapeHtml(
					label || href
				)}</a>`
			);
		}
	},
	image: (src: string, alt = '', width?: number) => {
		const w = width ? ` width="${width}"` : '';
		insert.inlineHtml(`<img src="${escapeAttr(src)}" alt="${escapeAttr(alt)}"${w} />`);
	},
	/** A table with the given dimensions, header row enabled. */
	table: (rows: number, cols: number, header = true) => {
		let html = '<table class="naskah-table"><tbody>';
		for (let r = 0; r < rows; r++) {
			html += '<tr>';
			for (let c = 0; c < cols; c++) {
				const tag = header && r === 0 ? 'th' : 'td';
				html += `<${tag}>${r === 0 && header ? `Kolom ${c + 1}` : '&nbsp;'}</${tag}>`;
			}
			html += '</tr>';
		}
		html += '</tbody></table><p><br/></p>';
		insert.html(html);
	},
	pageBreak: () => insert.html('<div class="naskah-pagebreak" contenteditable="false"></div><p><br/></p>'),
};

// ── Clipboard & history ────────────────────────────────────────────────────
export const history = {
	undo: () => exec('undo'),
	redo: () => exec('redo'),
	cut: () => exec('cut'),
	copy: () => exec('copy'),
	paste: () => exec('paste'),
	selectAll: () => exec('selectAll'),
};

// ── Find & replace ─────────────────────────────────────────────────────────
export interface ReplaceResult {
	count: number;
}

/**
 * Replace every plain-text occurrence of `find` inside `root` with `replace`.
 * Walks text nodes so it never destroys the surrounding markup; new matches
 * written this turn are not re-scanned (no infinite growth).
 */
export function replaceAll(root: HTMLElement, find: string, replace: string): ReplaceResult {
	if (!find) return { count: 0 };
	let count = 0;
	const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
	const targets: Text[] = [];
	let n: Node | null;
	while ((n = walker.nextNode())) targets.push(n as Text);

	for (const node of targets) {
		if (!node.nodeValue || !node.nodeValue.includes(find)) continue;
		const parts = node.nodeValue.split(find);
		count += parts.length - 1;
		const frag = document.createDocumentFragment();
		parts.forEach((part, i) => {
			if (i > 0) frag.appendChild(document.createTextNode(replace));
			if (part) frag.appendChild(document.createTextNode(part));
		});
		node.parentNode?.replaceChild(frag, node);
	}
	return { count };
}

/**
 * Find the next (or previous) occurrence of `find` and select it, so the caret
 * jumps to the match and the browser scrolls it into view. `backward` reverses
 * the direction. Returns true when a match was found and selected.
 */
export function findNext(root: HTMLElement, find: string, backward = false): boolean {
	if (!find) return false;
	const matches: Range[] = [];
	const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
	let node: Node | null;
	const lower = find.toLowerCase();
	while ((node = walker.nextNode())) {
		const text = node.nodeValue ?? '';
		if (!text) continue;
		const hay = text.toLowerCase();
		let idx = hay.indexOf(lower);
		while (idx !== -1) {
			const range = document.createRange();
			range.setStart(node, idx);
			range.setEnd(node, idx + find.length);
			matches.push(range);
			idx = hay.indexOf(lower, idx + find.length);
		}
	}
	if (matches.length === 0) return false;

	const sel = window.getSelection();
	if (!sel) return false;

	// Pick the match after the current selection (or before, when backward),
	// wrapping around at either end.
	let target = matches[0];
	if (sel.rangeCount > 0 && !sel.isCollapsed) {
		const cur = sel.getRangeAt(0);
		if (!backward) {
			target = matches.find((m) => cur.compareBoundaryPoints(Range.END_TO_START, m) <= 0) ?? matches[0];
		} else {
			const before = matches.filter((m) => cur.compareBoundaryPoints(Range.START_TO_END, m) >= 0);
			target = before.length ? before[before.length - 1] : matches[matches.length - 1];
		}
	} else if (sel.rangeCount > 0) {
		const caret = sel.getRangeAt(0);
		if (!backward) {
			target = matches.find((m) => caret.compareBoundaryPoints(Range.END_TO_START, m) <= 0) ?? matches[0];
		} else {
			const before = matches.filter((m) => caret.compareBoundaryPoints(Range.START_TO_END, m) >= 0);
			target = before.length ? before[before.length - 1] : matches[matches.length - 1];
		}
	}

	sel.removeAllRanges();
	sel.addRange(target);
	const el = target.startContainer.parentElement;
	el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
	return true;
}

/** Count how many times `find` occurs in the document (case-insensitive). */
export function countMatches(root: HTMLElement, find: string): number {
	if (!find) return 0;
	const lower = find.toLowerCase();
	let count = 0;
	const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
	let node: Node | null;
	while ((node = walker.nextNode())) {
		const hay = (node.nodeValue ?? '').toLowerCase();
		if (!hay) continue;
		let idx = hay.indexOf(lower);
		while (idx !== -1) {
			count++;
			idx = hay.indexOf(lower, idx + lower.length);
		}
	}
	return count;
}

/** Statistics for the current selection (or zeros when nothing is selected). */
export function selectionStats(): { words: number; characters: number } {
	const sel = window.getSelection();
	const text = sel ? sel.toString() : '';
	const trimmed = text.trim();
	return {
		words: trimmed ? trimmed.split(/\s+/).length : 0,
		characters: text.length,
	};
}

// ── Table operations ───────────────────────────────────────────────────────
/** The <table> cell (td/th) and row containing the caret, if any. */
function currentCell(): { cell: HTMLTableCellElement; row: HTMLTableRowElement; table: HTMLTableElement } | null {
	const sel = window.getSelection();
	if (!sel || !sel.anchorNode) return null;
	let node: Node | null = sel.anchorNode;
	while (node) {
		if (node.nodeType === Node.ELEMENT_NODE) {
			const el = node as HTMLElement;
			if (el.tagName === 'TD' || el.tagName === 'TH') {
				const cell = el as HTMLTableCellElement;
				const row = cell.parentElement as HTMLTableRowElement;
				const table = row?.closest('table') as HTMLTableElement;
				if (row && table) return { cell, row, table };
			}
		}
		node = node.parentNode;
	}
	return null;
}

export const table = {
	/** True when the caret sits inside a table cell. */
	inTable: () => currentCell() !== null,
	addRowAbove: () => {
		const c = currentCell();
		if (!c) return;
		const row = c.row.cloneNode(true) as HTMLTableRowElement;
		row.querySelectorAll('td,th').forEach((cell) => (cell.innerHTML = '&nbsp;'));
		c.row.parentElement?.insertBefore(row, c.row);
	},
	addRowBelow: () => {
		const c = currentCell();
		if (!c) return;
		const row = c.row.cloneNode(true) as HTMLTableRowElement;
		row.querySelectorAll('td,th').forEach((cell) => (cell.innerHTML = '&nbsp;'));
		c.row.parentElement?.insertBefore(row, c.row.nextSibling);
	},
	addColumnLeft: () => {
		const c = currentCell();
		if (!c) return;
		const index = Array.from(c.row.children).indexOf(c.cell);
		Array.from(c.table.rows).forEach((row) => {
			const tag = row.cells[0]?.tagName === 'TH' ? 'th' : 'td';
			const cell = document.createElement(tag);
			cell.innerHTML = '&nbsp;';
			row.insertBefore(cell, row.children[index] ?? null);
		});
	},
	addColumnRight: () => {
		const c = currentCell();
		if (!c) return;
		const index = Array.from(c.row.children).indexOf(c.cell) + 1;
		Array.from(c.table.rows).forEach((row) => {
			const tag = row.cells[0]?.tagName === 'TH' ? 'th' : 'td';
			const cell = document.createElement(tag);
			cell.innerHTML = '&nbsp;';
			row.insertBefore(cell, row.children[index] ?? null);
		});
	},
	deleteRow: () => {
		const c = currentCell();
		if (!c) return;
		if (c.table.rows.length <= 1) {
			c.table.remove();
			return;
		}
		c.row.remove();
	},
	deleteColumn: () => {
		const c = currentCell();
		if (!c) return;
		const index = Array.from(c.row.children).indexOf(c.cell);
		const rowCount = c.table.rows.length;
		Array.from(c.table.rows).forEach((row) => row.children[index]?.remove());
		// Drop the table entirely when no columns remain.
		if (rowCount > 0 && c.table.rows[0]?.children.length === 0) c.table.remove();
	},
};

/** Text statistics for the status bar / Review tab. */
export interface TextStats {
	words: number;
	characters: number;
	charactersNoSpaces: number;
	paragraphs: number;
	sentences: number;
	readingMinutes: number;
}

export function textStats(root: HTMLElement): TextStats {
	// `plainText` avoids the browser-only `innerText` so the same numbers are
	// produced in the test environment and in every engine the app supports.
	const text = plainText(root);
	const trimmed = text.trim();
	const words = trimmed ? trimmed.split(/\s+/).length : 0;
	const paragraphs = trimmed ? trimmed.split(/\n+/).filter((p) => p.trim()).length : 0;
	const sentences = trimmed ? (trimmed.match(/[^.!?]+[.!?]+/g) || [trimmed]).length : 0;
	return {
		words,
		characters: text.length,
		charactersNoSpaces: text.replace(/\s/g, '').length,
		paragraphs,
		sentences,
		readingMinutes: Math.max(1, Math.round(words / 200)),
	};
}

// ── Small helpers ──────────────────────────────────────────────────────────
/**
 * True when an HTML payload starts with a block-level element and therefore
 * must be inserted on its own block rather than inline inside a paragraph.
 * Exported for the insert tests.
 */
export function startsWithBlock(html: string): boolean {
	return /^\s*<(p|div|h[1-6]|ul|ol|table|blockquote|pre|hr|dl|figure)\b/i.test(html);
}

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}
function escapeAttr(s: string): string {
	return escapeHtml(s);
}
