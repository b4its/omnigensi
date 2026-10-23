/**
 * EditorState — a single, reactive snapshot of everything the ribbon needs to
 * render itself: the cursor's character formatting, paragraph formatting,
 * table/picture context, list state and the active style.
 *
 * Wordcraft keeps one "command + document feature catalog" as the source of
 * truth for its ribbon; this module is the browser-side equivalent. Instead of
 * every button reaching into `document.queryCommandState` on its own (which
 * only knows a handful of legacy commands), the page refreshes this snapshot
 * on every selection change and the ribbon is a pure function of it.
 */

import { currentBlock, isBlock } from './commands';

export type Align = 'left' | 'center' | 'right' | 'justify';

export interface InlineState {
	bold: boolean;
	italic: boolean;
	underline: boolean;
	strike: boolean;
	sup: boolean;
	sub: boolean;
	smallCaps: boolean;
	allCaps: boolean;
	hidden: boolean;
	fontFamily: string;
	fontSize: number; // pt
	color: string; // hex or rgb() string
	highlight: string;
	spacing: string; // letter-spacing, e.g. '1px'
}

export interface ParaState {
	align: Align;
	bullet: boolean;
	number: boolean;
	indent: number; // 0 = none, 1 = one level
	lineHeight: string;
	spaceAfter: number; // pt
	h1: boolean;
	h2: boolean;
	h3: boolean;
	h4: boolean;
	quote: boolean;
}

export interface CtxState {
	inTable: boolean;
	inPicture: boolean; // caret next to / inside a picture selection
	styleName: string;
}

export interface EditorStateSnapshot {
	inline: InlineState;
	para: ParaState;
	ctx: CtxState;
}

const EMPTY: EditorStateSnapshot = {
	inline: {
		bold: false,
		italic: false,
		underline: false,
		strike: false,
		sup: false,
		sub: false,
		smallCaps: false,
		allCaps: false,
		hidden: false,
		fontFamily: 'Times New Roman',
		fontSize: 12,
		color: '#000000',
		highlight: 'transparent',
		spacing: '0px',
	},
	para: {
		align: 'left',
		bullet: false,
		number: false,
		indent: 0,
		lineHeight: '1.5',
		spaceAfter: 0,
		h1: false,
		h2: false,
		h3: false,
		h4: false,
		quote: false,
	},
	ctx: { inTable: false, inPicture: false, styleName: 'Normal' },
};

function query(cmd: string): boolean {
	try {
		return document.queryCommandState(cmd);
	} catch {
		return false;
	}
}

/** Read a computed style off the element that actually carries the caret. */
function caretStyle(): CSSStyleDeclaration | null {
	const sel = window.getSelection();
	if (!sel || !sel.anchorNode) return null;
	let node: Node | null = sel.anchorNode;
	const el =
		node?.nodeType === Node.ELEMENT_NODE
			? (node as Element)
			: node?.parentElement ?? null;
	return el ? getComputedStyle(el) : null;
}

/** Walk up from the caret until an element carries a non-empty inline style. */
function inherited(prop: keyof CSSStyleDeclaration): string {
	const sel = window.getSelection();
	if (!sel || !sel.anchorNode) return '';
	let node: Node | null = sel.anchorNode;
	while (node && node !== document.body) {
		if (node.nodeType === Node.ELEMENT_NODE) {
			const v = (node as HTMLElement).style?.[prop as never] as string | undefined;
			if (v) return v;
		}
		node = node.parentNode;
	}
	return '';
}

function toHex(rgb: string): string {
	if (!rgb) return '';
	const m = rgb.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
	if (!m) return rgb;
	const hex = (n: string) => Number(n).toString(16).padStart(2, '0');
	return `#${hex(m[1])}${hex(m[2])}${hex(m[3])}`.toUpperCase();
}

/** Extract the label of the closest `data-style` block, else infer from tag. */
function styleName(): string {
	const block = currentBlock();
	if (block) {
		const explicit = block.getAttribute('data-style');
		if (explicit) return explicit;
		const tag = block.tagName;
		if (tag === 'H1') return 'Heading 1';
		if (tag === 'H2') return 'Heading 2';
		if (tag === 'H3') return 'Heading 3';
		if (tag === 'H4') return 'Heading 4';
		if (tag === 'BLOCKQUOTE') return 'Quote';
		if (tag === 'PRE') return 'Code';
	}
	return 'Normal';
}

/** Snapshot every ribbon-relevant detail of the current selection. */
export function readState(): EditorStateSnapshot {
	if (typeof document === 'undefined') return structuredClone(EMPTY);
	const computed = caretStyle();
	const fontSizePx = computed ? parseFloat(computed.fontSize) || 16 : 16;
	const fontSize = Math.round((fontSizePx * 72) / 96);

	const align: Align = query('justifyFull')
		? 'justify'
		: query('justifyCenter')
			? 'center'
			: query('justifyRight')
				? 'right'
				: 'left';

	const block = currentBlock();
	const inTable = (() => {
		const sel = window.getSelection();
		if (!sel || !sel.anchorNode) return false;
		let node: Node | null = sel.anchorNode;
		while (node) {
			if (node.nodeType === Node.ELEMENT_NODE && (node as Element).tagName === 'TD') return true;
			if (node.nodeType === Node.ELEMENT_NODE && (node as Element).tagName === 'TH') return true;
			if (node.nodeType === Node.ELEMENT_NODE && (node as Element).tagName === 'TABLE') return true;
			node = node.parentNode;
		}
		return false;
	})();

	return {
		inline: {
			bold: query('bold'),
			italic: query('italic'),
			underline: query('underline'),
			strike: query('strikeThrough'),
			sup: query('superscript'),
			sub: query('subscript'),
			smallCaps: computed?.fontVariant?.toLowerCase().includes('small-caps') ?? false,
			allCaps: (computed?.textTransform ?? '').toLowerCase() === 'uppercase',
			hidden: false,
			fontFamily: (computed?.fontFamily ?? 'Times New Roman').split(',')[0].replace(/["']/g, '').trim(),
			fontSize: Number.isFinite(fontSize) ? fontSize : 12,
			color: toHex(computed?.color ?? '#000000'),
			highlight: computed && computed.backgroundColor && computed.backgroundColor !== 'rgba(0, 0, 0, 0)'
				? toHex(computed.backgroundColor)
				: 'transparent',
			spacing: inherited('letterSpacing') || computed?.letterSpacing || '0px',
		},
		para: {
			align,
			bullet: query('insertUnorderedList'),
			number: query('insertOrderedList'),
			indent: (() => {
				const ml = block ? parseFloat(getComputedStyle(block).marginLeft) || 0 : 0;
				return Math.max(0, Math.round(ml / 32));
			})(),
			lineHeight: block ? getComputedStyle(block).lineHeight : '1.5',
			spaceAfter: block ? Math.round((parseFloat(getComputedStyle(block).marginBottom) || 0) * 0.75) : 0,
			h1: isBlock('h1'),
			h2: isBlock('h2'),
			h3: isBlock('h3'),
			h4: isBlock('h4'),
			quote: isBlock('blockquote'),
		},
		ctx: {
			inTable,
			inPicture: false,
			styleName: styleName(),
		},
	};
}

/** Empty snapshot (useful for SSR and tests). */
export function emptyState(): EditorStateSnapshot {
	return structuredClone(EMPTY);
}
