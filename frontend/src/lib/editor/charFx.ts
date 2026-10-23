/**
 * charFx — character-level formatting that `execCommand` cannot express.
 *
 * Every helper wraps the current non-collapsed selection in a `<span>` with an
 * inline style — Word's equivalent of a "run". Toggles are idempotent: applying
 * small caps to text that already has it removes it, so the ribbon behaves like
 * Word's toggle buttons instead of stacking spans.
 */

const SPAN_MARK = 'data-naskah-fx';

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}

/** The innermost marked span above the caret that carries `styleKey`. */
function enclosingFx(styleKey: string): HTMLElement | null {
	const sel = window.getSelection();
	if (!sel || !sel.anchorNode) return null;
	let node: Node | null = sel.anchorNode;
	while (node) {
		if (node.nodeType === Node.ELEMENT_NODE) {
			const el = node as HTMLElement;
			if (el.hasAttribute(SPAN_MARK) && el.style.getPropertyValue(styleKey)) return el;
		}
		node = node.parentNode;
	}
	return null;
}

function unwrap(el: HTMLElement): void {
	const parent = el.parentNode;
	if (!parent) return;
	while (el.firstChild) parent.insertBefore(el.firstChild, el);
	parent.removeChild(el);
}

/** Wrap the selection in a styled span. With `toggleKey`, remove it if present. */
export function wrapSelection(styles: Record<string, string>, toggleKey?: string): boolean {
	const sel = window.getSelection();
	if (!sel || sel.rangeCount === 0) return false;
	const range = sel.getRangeAt(0);
	if (range.collapsed) return false;

	if (toggleKey) {
		const existing = enclosingFx(toggleKey);
		if (existing) {
			existing.style.removeProperty(toggleKey);
			if (!existing.getAttribute('style')?.trim()) unwrap(existing);
			return true;
		}
	}

	const span = document.createElement('span');
	span.setAttribute(SPAN_MARK, '');
	for (const [k, v] of Object.entries(styles)) span.style.setProperty(k, v);
	try {
		range.surroundContents(span);
	} catch {
		// The range bisects elements: extract, wrap, re-insert.
		const frag = range.extractContents();
		span.appendChild(frag);
		range.insertNode(span);
	}
	sel.removeAllRanges();
	const r = document.createRange();
	r.selectNodeContents(span);
	sel.addRange(r);
	return true;
}

export const charFx = {
	smallCaps: () => wrapSelection({ 'font-variant': 'small-caps' }, 'font-variant'),
	allCaps: () => wrapSelection({ 'text-transform': 'uppercase' }, 'text-transform'),
	hidden: () => wrapSelection({ display: 'none' }, 'display'),
	doubleUnderline: () => wrapSelection({ 'text-decoration': 'underline double' }, 'text-decoration'),
	/** Outline text: transparent fill with a stroke in the current colour. */
	outline: () =>
		wrapSelection({ '-webkit-text-stroke': '1px currentColor', 'text-fill-color': 'transparent' }),
	shadow: () => wrapSelection({ 'text-shadow': '2px 2px 3px rgba(0,0,0,0.45)' }, 'text-shadow'),
	glow: () => wrapSelection({ 'text-shadow': '0 0 6px currentColor' }, 'text-shadow'),
	emboss: () =>
		wrapSelection({ 'text-shadow': '1px 1px 0 #fff, -1px -1px 0 rgba(0,0,0,.5)' }, 'text-shadow'),
	engrave: () =>
		wrapSelection({ 'text-shadow': '-1px -1px 0 #fff, 1px 1px 0 rgba(0,0,0,.5)' }, 'text-shadow'),
	/** Letter-spacing in points (Word's Expanded / Condensed). */
	spacing: (pt: number) => wrapSelection({ 'letter-spacing': `${pt}pt` }, 'letter-spacing'),
	/** Horizontal glyph scale, in percent. */
	scale: (pct: number) => wrapSelection({ display: 'inline-block', transform: `scaleX(${pct / 100})` }),
	/** Baseline raise (negative) / lower (positive) in points. */
	position: (pt: number) => wrapSelection({ position: 'relative', top: `${-pt}pt` }, 'top'),
	shading: (color: string) => wrapSelection({ background: color }, 'background'),
	border: (color = '#888888') => wrapSelection({ border: `1px solid ${color}`, padding: '0 1px' }, 'border'),
	/** Strikethrough style: single vs double. */
	doubleStrike: () => wrapSelection({ 'text-decoration': 'line-through double' }, 'text-decoration'),
	/** Ruby-style phonetic guide above the selected characters. */
	phonetic: (reading: string): boolean => {
		const sel = window.getSelection();
		if (!sel || sel.isCollapsed || !reading.trim()) return false;
		const base = sel.toString();
		document.execCommand(
			'insertHTML',
			false,
			`<ruby>${escapeHtml(base)}<rt>${escapeHtml(reading)}</rt></ruby>`
		);
		return true;
	},
};

/** Enclose the selection in a shape glyph using Unicode combining forms. */
const ENCLOSE_MAP: Record<'circle' | 'square' | 'triangle' | 'diamond', Record<string, string>> = {
	circle: {},
	square: {},
	triangle: {},
	diamond: {},
};
for (let i = 0; i < 26; i++) {
	const c = String.fromCharCode(65 + i);
	ENCLOSE_MAP.circle[c] = String.fromCharCode(0x24b6 + i); // Ⓐ
	ENCLOSE_MAP.circle[c.toLowerCase()] = String.fromCharCode(0x24d0 + i); // ⓐ
	ENCLOSE_MAP.square[c] = String.fromCharCode(0x1f130 + i); // 🄰
	ENCLOSE_MAP.diamond[c] = String.fromCharCode(0x1f150 + i); // 🅐
}
// Numbers in circles, a widely used set.
'0123456789'.split('').forEach((d, i) => {
	ENCLOSE_MAP.circle[d] = String.fromCharCode(0x2460 + i); // ①
});

/** Replace each selected character with its enclosed form when possible. */
export function encloseSelection(shape: keyof typeof ENCLOSE_MAP): boolean {
	const sel = window.getSelection();
	if (!sel || sel.isCollapsed) return false;
	const map = ENCLOSE_MAP[shape];
	const out = sel
		.toString()
		.split('')
		.map((ch) => map[ch] ?? map[ch.toUpperCase()] ?? ch)
		.join('');
	document.execCommand('insertText', false, out);
	return true;
}

export interface FontDialogModel {
	family: string;
	size: number;
	bold: boolean;
	italic: boolean;
	underline: boolean;
	color: string;
	highlight: string;
}

/**
 * Apply every property of the Font dialog in one pass. `execCommand` toggles
 * are unreliable for *setting* a definite state, so we force the desired value
 * by only issuing the toggle when the current state disagrees.
 */
export function applyFontDialog(m: FontDialogModel): void {
	if (m.family) document.execCommand('fontName', false, m.family);
	const state = (c: string) => {
		try {
			return document.queryCommandState(c);
		} catch {
			return false;
		}
	};
	if (state('bold') !== m.bold) document.execCommand('bold');
	if (state('italic') !== m.italic) document.execCommand('italic');
	if (state('underline') !== m.underline) document.execCommand('underline');
	if (m.color) document.execCommand('foreColor', false, m.color);
	if (m.highlight && m.highlight !== 'transparent') {
		if (!document.execCommand('hiliteColor', false, m.highlight)) {
			document.execCommand('backColor', false, m.highlight);
		}
	}
	if (m.size) wrapSelection({ 'font-size': `${m.size}pt` });
}
