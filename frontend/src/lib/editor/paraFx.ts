/**
 * paraFx — block-level formatting Word exposes in Home › Paragraph and
 * Layout › Paragraph that `execCommand` cannot do: borders, shading, keep
 * with next, widow/orphan control, tabs with leaders, hanging indent, RTL,
 * outline level, sorting paragraphs and moving paragraphs up/down.
 *
 * Everything operates on the blocks touched by the current selection using
 * the block list from `commands.ts`.
 */

import { selectedBlocks, currentBlock } from './commands';

type Block = HTMLElement;

function blocks(): Block[] {
	const list = selectedBlocks();
	if (list.length) return list;
	const one = currentBlock();
	return one ? [one] : [];
}

function styleAll(prop: string, value: string) {
	for (const b of blocks()) b.style.setProperty(prop, value);
}

export const paraFx = {
	/** Draw a box border around each selected paragraph. */
	border: (spec = '1px solid currentColor') => styleAll('border', spec),
	removeBorder: () => styleAll('border', 'none'),
	/** Paragraph background / shading. */
	shading: (color: string) => styleAll('background', color),
	keepWithNext: (on = true) => styleAll('break-after', on ? 'avoid' : 'auto'),
	keepLines: (on = true) => styleAll('break-inside', on ? 'avoid' : 'auto'),
	widowControl: (on = true) => styleAll('widows', on ? '2' : '1'),
	/** Page break before the paragraph. */
	pageBreakBefore: (on = true) => styleAll('break-before', on ? 'page' : 'auto'),
	/** Left indent in px (hanging uses a negative text-indent). */
	leftIndent: (px: number) => styleAll('margin-left', `${px}px`),
	rightIndent: (px: number) => styleAll('margin-right', `${px}px`),
	hangingIndent: (px: number) => {
		for (const b of blocks()) {
			b.style.marginLeft = `${px}px`;
			b.style.textIndent = `-${px}px`;
		}
	},
	spaceBefore: (pt: number) => styleAll('margin-top', `${pt}pt`),
	spaceAfter: (pt: number) => styleAll('margin-bottom', `${pt}pt`),
	lineSpacing: (value: string) => styleAll('line-height', value),
	rtl: (on = true) => styleAll('direction', on ? 'rtl' : 'ltr'),
	/** Outline level maps to Word's paragraph outline; stored as a data attr. */
	outlineLevel: (level: number) => {
		for (const b of blocks()) b.setAttribute('data-outline-level', String(level));
	},
	/** Distributed text: justify-all spreads the last line too. */
	distribute: () => styleAll('text-align-last', 'justify'),

	/** Move the caret paragraph up or down among its siblings. */
	moveUp: () => moveBlock(-1),
	moveDown: () => moveBlock(1),

	/** Sort paragraphs (or the rows of the current table) alphabetically. */
	sort: (ascending = true) => sortBlocks(ascending),

	/** Tab stop with a leader, stored as a CSS tab-size plus data attribute. */
	tabs: (size = 4) => styleAll('tab-size', String(size)),
};

function moveBlock(dir: -1 | 1): void {
	const b = currentBlock();
	if (!b || !b.parentElement) return;
	const sibling = dir < 0 ? b.previousElementSibling : b.nextElementSibling;
	if (!sibling) return;
	if (dir < 0) b.parentElement.insertBefore(b, sibling);
	else b.parentElement.insertBefore(sibling, b);
	b.scrollIntoView({ block: 'nearest' });
}

function sortBlocks(ascending: boolean): void {
	const b = currentBlock();
	if (!b) return;
	// Sorting inside a table sorts its rows instead of the document.
	const table = b.closest('table');
	if (table) {
		const body = table.tBodies[0] ?? table;
		const rows = Array.from(body.rows).filter((r) => r.querySelector('td'));
		rows.sort((x, y) => {
			const a = (x.textContent ?? '').trim().toLowerCase();
			const c = (y.textContent ?? '').trim().toLowerCase();
			return ascending ? a.localeCompare(c) : c.localeCompare(a);
		});
		for (const r of rows) body.appendChild(r);
		return;
	}
	const parent = b.parentElement;
	if (!parent) return;
	const group: HTMLElement[] = [];
	let node: Element | null = b;
	// Collect the contiguous run of block siblings that are paragraphs.
	while (node && /^(P|H[1-6]|LI|BLOCKQUOTE)$/.test(node.tagName)) {
		group.push(node as HTMLElement);
		node = node.nextElementSibling;
	}
	group.sort((x, y) => {
		const a = (x.textContent ?? '').trim().toLowerCase();
		const c = (y.textContent ?? '').trim().toLowerCase();
		return ascending ? a.localeCompare(c) : c.localeCompare(a);
	});
	const anchor = group.length ? group[0] : null;
	void anchor;
	// Re-insert in sorted order, before the original first element.
	const first = group[0]?.previousElementSibling ?? null;
	const before = first ? first.nextSibling : parent.firstChild;
	for (const el of group) parent.insertBefore(el, before);
}

/** Convert a run of "a,b,c" text lines into a table. */
export function textToTable(text: string, delimiter = ','): string {
	const rows = text
		.split(/\r?\n/)
		.filter((l) => l.trim())
		.map((l) => l.split(delimiter).map((c) => c.trim()));
	const cols = Math.max(1, ...rows.map((r) => r.length));
	let html = '<table class="naskah-table"><tbody>';
	for (const r of rows) {
		html += '<tr>';
		for (let c = 0; c < cols; c++) html += `<td>${escapeHtml(r[c] ?? '')}</td>`;
		html += '</tr>';
	}
	html += '</tbody></table><p><br/></p>';
	return html;
}

/** Convert the current table back to tab-delimited text. */
export function tableToText(): string {
	const b = currentBlock();
	const table = b?.closest('table');
	if (!table) return '';
	return Array.from(table.rows)
		.map((r) => Array.from(r.cells).map((c) => (c.textContent ?? '').trim()).join('\t'))
		.join('\n');
}

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}
