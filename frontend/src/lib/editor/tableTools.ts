/**
 * tableTools — Word's Table Layout and Table Design tabs: merge and split
 * cells, repeat header rows, banded rows, borders and shading, auto-fit,
 * sorting, formulas (`=SUM(ABOVE)`) and text <-> table conversion.
 *
 * Operations act on the table containing the caret and are idempotent where
 * Word's are (merging merges only the selected span, repeating headers toggles
 * the flag rather than stacking).
 */

import { currentBlock } from './commands';

/** The `<table>` under the caret. */
/**
 * The `<table>` under the caret.
 *
 * `currentBlock()` only knows paragraph-ish blocks, so it returns null inside a
 * cell; walk up from the caret's element instead, which also covers the case
 * where the selection anchor is a text node inside `<td>`.
 */
export function activeTable(): HTMLTableElement | null {
	const sel = window.getSelection();
	let node: Node | null = sel?.anchorNode ?? null;
	while (node) {
		if (node.nodeType === Node.ELEMENT_NODE) {
			const el = node as HTMLElement;
			if (el.tagName === 'TABLE') return el as HTMLTableElement;
			const table = el.closest?.('table');
			if (table) return table as HTMLTableElement;
		}
		node = node.parentNode;
	}
	return (currentBlock()?.closest('table') as HTMLTableElement | null) ?? null;
}

/** The `<td>`/`<th>` under the caret. */
export function activeCell(): HTMLTableCellElement | null {
	const sel = window.getSelection();
	if (!sel || !sel.anchorNode) return null;
	let node: Node | null = sel.anchorNode;
	while (node) {
		if (node.nodeType === Node.ELEMENT_NODE) {
			const el = node as HTMLElement;
			if (el.tagName === 'TD' || el.tagName === 'TH') return el as HTMLTableCellElement;
		}
		node = node.parentNode;
	}
	return null;
}

/** Index of `cell` inside its own row (TD/TH children only). */
function cellColumn(cell: HTMLTableCellElement): number {
	const row = cell.parentElement as HTMLTableRowElement | null;
	if (!row) return 0;
	return Array.from(row.children).indexOf(cell);
}

/**
 * The bounding box of the selected cells inside the active table.
 *
 * Uses explicit row/column geometry derived from container ancestry and child
 * order. `Range.intersectsNode` is deliberately avoided: its result for table
 * cells differs between engines and even between document-owned and
 * selection-owned ranges, which made multi-cell operations unreliable.
 */
export function selectionBox(): { table: HTMLTableElement; rows: number[]; cols: number[] } | null {
	const table = activeTable();
	const cell = activeCell();
	if (!table || !cell) return null;

	const sel = window.getSelection();
	const range = sel && sel.rangeCount ? sel.getRangeAt(0) : null;
	const anchors: HTMLTableCellElement[] = [cell];
	if (range) {
		const startCell = closestCell(range.startContainer);
		const endCell = closestCell(range.endContainer);
		if (startCell && startCell.closest('table') === table) anchors.push(startCell);
		if (endCell && endCell.closest('table') === table) anchors.push(endCell);
	}

	const rows: number[] = [];
	const cols: number[] = [];
	for (const c of anchors) {
		const rowIndex = (c.parentElement as HTMLTableRowElement).rowIndex;
		const colIndex = cellColumn(c);
		rows.push(rowIndex);
		cols.push(colIndex);
	}

	const minRow = Math.min(...rows);
	const maxRow = Math.max(...rows);
	const minCol = Math.min(...cols);
	const maxCol = Math.max(...cols);
	if (minRow === maxRow && minCol === maxCol) {
		return { table, rows: [minRow], cols: [minCol] };
	}

	const rowRange: number[] = [];
	const colRange: number[] = [];
	for (let r = minRow; r <= maxRow; r++) rowRange.push(r);
	for (let c = minCol; c <= maxCol; c++) colRange.push(c);

	// Only keep rows/columns that actually contain a cell in the span, so a
	// selection brushing a colspan boundary cannot invent empty columns.
	const validCols = colRange.filter((c) =>
		rowRange.some((r) => table.rows[r]?.children[c])
	);
	return { table, rows: rowRange, cols: validCols.length ? validCols : [minCol] };
}

/** The nearest TD/TH ancestor (or self) of a node. */
function closestCell(node: Node | null): HTMLTableCellElement | null {
	let n: Node | null = node;
	while (n) {
		if (n.nodeType === Node.ELEMENT_NODE) {
			const el = n as HTMLElement;
			if (el.tagName === 'TD' || el.tagName === 'TH') return el as HTMLTableCellElement;
		}
		n = n.parentNode;
	}
	return null;
}

export const tableTools = {
	/** Merge every selected cell into the top-left one. */
	mergeCells: () => {
		const box = selectionBox();
		if (!box || box.rows.length * box.cols.length < 2) return;
		const { table, rows, cols } = box;
		const top = rows[0];
		const left = cols[0];
		// Resolve every cell *before* mutating: HTMLTableRowElement.cells is a
		// live collection, so removing during iteration skips cells.
		const targets = rows.flatMap((r) =>
			cols
				.map((c) => table.rows[r]?.children[c] as HTMLTableCellElement | undefined)
				.filter((cell): cell is HTMLTableCellElement => !!cell)
		);
		const anchor = table.rows[top]?.children[left] as HTMLTableCellElement | undefined;
		if (!anchor) return;
		const content = targets.map((cell) => cell.innerHTML.trim()).filter(Boolean).join(' ');
		anchor.rowSpan = rows.length;
		anchor.colSpan = cols.length;
		anchor.innerHTML = content || '&nbsp;';
		for (const cell of targets) {
			if (cell !== anchor) cell.remove();
		}
	},

	/** Split the active merged cell back into `rows × cols` plain cells. */
	splitCell: (rows = 2, cols = 2) => {
		const cell = activeCell();
		if (!cell || !cell.parentElement) return;
		const tr = cell.parentElement as HTMLTableRowElement;
		const span = cell.colSpan;
		cell.colSpan = 1;
		cell.rowSpan = 1;
		const table = activeTable();
		if (!table) return;
		for (let c = 1; c < Math.max(cols, span); c++) {
			const extra = document.createElement(cell.tagName.toLowerCase());
			extra.innerHTML = '&nbsp;';
			tr.insertBefore(extra, cell.nextSibling);
		}
		for (let r = 1; r < rows; r++) {
			const newRow = table.insertRow(tr.rowIndex + r);
			for (let c = 0; c < Math.max(cols, span); c++) {
				const td = newRow.insertCell();
				td.innerHTML = '&nbsp;';
			}
		}
	},

	/** Toggle repeated header rows across pages. */
	repeatHeader: (on = true) => {
		const table = activeTable();
		if (!table) return;
		for (const r of Array.from(table.rows)) {
			const cells = Array.from(r.cells);
			const isHeader = cells.length > 0 && cells.every((c) => c.tagName === 'TH');
			if (isHeader) {
				const head = table.tHead;
				if (on) {
					if (!head) {
						const thead = table.createTHead();
						while (r.querySelector('th')) void 0;
						thead.appendChild(r);
					}
					r.setAttribute('data-repeat-header', 'true');
				} else {
					r.removeAttribute('data-repeat-header');
				}
			}
		}
	},

	/** Banded rows (zebra striping) defined by the table style. */
	bandedRows: (on = true) => {
		const table = activeTable();
		if (!table) return;
		if (on) table.setAttribute('data-banded', '');
		else table.removeAttribute('data-banded');
	},

	/** First-column emphasis (Word's "First Column" table look). */
	firstColumn: (on = true) => {
		const table = activeTable();
		if (!table) return;
		if (on) table.setAttribute('data-first-column', '');
		else table.removeAttribute('data-first-column');
	},

	/** Shade the selected cells, or the whole table when nothing is selected. */
	shade: (color: string) => {
		const table = activeTable();
		if (!table) return;
		const cell = activeCell();
		if (cell) {
			const box = selectionBox();
			const cells = box
				? box.rows.flatMap((r) =>
						box.cols
							.map((c) => table.rows[r]?.children[c] as HTMLTableCellElement | undefined)
							.filter((x): x is HTMLTableCellElement => !!x)
					)
				: [cell];
			for (const c of cells) c.style.background = color;
		} else {
			table.style.background = color;
		}
	},

	/** Border style for the table. */
	borders: (spec = '1px solid #888888') => {
		const table = activeTable();
		if (!table) return;
		table.style.borderCollapse = 'collapse';
		table.querySelectorAll<HTMLElement>('td,th').forEach((c) => (c.style.border = spec));
	},

	/** Make every column the same fixed width. */
	distributeColumns: () => {
		const table = activeTable();
		if (!table) return;
		const count = table.rows[0]?.cells.length ?? 0;
		if (!count) return;
		const pct = (100 / count).toFixed(3);
		for (const row of Array.from(table.rows)) {
			for (const cell of Array.from(row.cells)) cell.style.width = `${pct}%`;
		}
	},

	/** Auto-fit: clear fixed widths so the browser sizes columns to content. */
	autoFit: () => {
		const table = activeTable();
		if (!table) return;
		table.style.width = '100%';
		for (const row of Array.from(table.rows)) {
			for (const cell of Array.from(row.cells)) cell.style.width = '';
		}
	},

	/** Sort rows by the active column. */
	sort: (ascending = true) => {
		const table = activeTable();
		const cell = activeCell();
		if (!table || !cell) return;
		const col = cell.cellIndex;
		const body = table.tBodies[0];
		const rows = Array.from(body?.rows ?? []).filter((r) => r.querySelector('td'));
		rows.sort((a, b) => {
			const av = (a.cells[col]?.textContent ?? '').trim();
			const bv = (b.cells[col]?.textContent ?? '').trim();
			const an = Number(av);
			const bn = Number(bv);
			const cmp = !Number.isNaN(an) && !Number.isNaN(bn) ? an - bn : av.localeCompare(bv, 'id');
			return ascending ? cmp : -cmp;
		});
		for (const r of rows) body?.appendChild(r);
	},

	/** Evaluate `=SUM(ABOVE)`-style formulas in every cell. */
	formulas: () => {
		const table = activeTable();
		if (!table) return;
		table.querySelectorAll<HTMLTableCellElement>('td').forEach((cell) => {
			const text = (cell.textContent ?? '').trim();
			const m = text.match(/^=(SUM|AVERAGE|COUNT|MAX|MIN)\((\w+)\)$/i);
			if (!m) return;
			const fn = m[1].toUpperCase();
			const dir = m[2].toUpperCase();
			const values = valuesInDirection(cell, dir);
			const result = compute(fn, values);
			cell.textContent = String(result);
		});
	},

	/** Convert the active table to tab-separated text. */
	toText: () => {
		const table = activeTable();
		if (!table) return null;
		const text = Array.from(table.rows)
			.map((r) => Array.from(r.cells).map((c) => (c.textContent ?? '').trim()).join('\t'))
			.join('\n');
		table.replaceWith(document.createTextNode(text));
		return text;
	},
};

function valuesInDirection(cell: HTMLTableCellElement, dir: string): number[] {
	const out: number[] = [];
	const tr = cell.parentElement as HTMLTableRowElement;
	const table = cell.closest('table');
	if (!table) return out;
	const cellIndex = cell.cellIndex;
	if (dir === 'ABOVE') {
		for (let r = tr.rowIndex - 1; r >= 0; r--) {
			const v = Number((table.rows[r]?.cells[cellIndex]?.textContent ?? '').trim());
			if (!Number.isNaN(v) && (table.rows[r]?.cells[cellIndex]?.textContent ?? '').trim() !== '') out.push(v);
		}
	} else if (dir === 'BELOW') {
		for (let r = tr.rowIndex + 1; r < table.rows.length; r++) {
			const v = Number((table.rows[r]?.cells[cellIndex]?.textContent ?? '').trim());
			if (!Number.isNaN(v)) out.push(v);
		}
	} else if (dir === 'LEFT') {
		for (let c = cellIndex - 1; c >= 0; c--) {
			const v = Number((tr.cells[c]?.textContent ?? '').trim());
			if (!Number.isNaN(v)) out.push(v);
		}
	} else if (dir === 'RIGHT') {
		for (let c = cellIndex + 1; c < tr.cells.length; c++) {
			const v = Number((tr.cells[c]?.textContent ?? '').trim());
			if (!Number.isNaN(v)) out.push(v);
		}
	}
	return out;
}

function compute(fn: string, values: number[]): number | string {
	if (!values.length) return 0;
	switch (fn) {
		case 'SUM':
			return values.reduce((a, b) => a + b, 0);
		case 'AVERAGE':
			return Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 100) / 100;
		case 'COUNT':
			return values.length;
		case 'MAX':
			return Math.max(...values);
		case 'MIN':
			return Math.min(...values);
		default:
			return 0;
	}
}

/**
 * Picture formatting: Word's Picture Format tab. Pictures carry
 * `data-object="picture"` when inserted by the ribbon so a click can select
 * them and the FormatPicturePanel can drive these operations.
 */
export const pictureTools = {
	/** Wrap the active image for later targeting. */
	ensureMarked(img: HTMLImageElement): void {
		img.setAttribute('data-object', 'image');
		img.setAttribute('tabindex', '0');
	},

	/** Change the displayed width in px (keeps the aspect ratio). */
	resize(img: HTMLImageElement, widthPx: number): void {
		const ratio = img.naturalWidth && img.naturalHeight ? img.naturalHeight / img.naturalWidth : 1;
		img.style.width = `${widthPx}px`;
		img.style.height = `${Math.round(widthPx * ratio)}px`;
		img.removeAttribute('width');
		img.removeAttribute('height');
	},

	/** Rotate by degrees. */
	rotate(img: HTMLImageElement, deg: number): void {
		img.style.transform = `rotate(${deg}deg)`;
	},

	/** Crop by clipping the image with an inset. */
	crop(img: HTMLImageElement, top: number, right: number, bottom: number, left: number): void {
		img.style.clipPath = `inset(${top}% ${right}% ${bottom}% ${left}%)`;
	},

	/** Basic brightness / contrast corrections. */
	correct(img: HTMLImageElement, brightness = 100, contrast = 100): void {
		img.style.filter = `brightness(${brightness}%) contrast(${contrast}%)`;
	},

	/** Colour wash ("Color" gallery). */
	recolor(img: HTMLImageElement, tint: string): void {
		img.style.filter = `sepia(1) hue-rotate(0deg) saturate(2)`;
		img.style.background = tint;
	},

	/** Border around the picture. */
	border(img: HTMLImageElement, spec = '2px solid #888888'): void {
		img.style.border = spec;
	},

	/** Reset every inline picture style. */
	reset(img: HTMLImageElement): void {
		img.style.cssText = '';
		img.removeAttribute('width');
		img.removeAttribute('height');
	},

	/** Set alt text (accessibility). */
	alt(img: HTMLImageElement, text: string): void {
		img.setAttribute('alt', text);
	},

	/** Text wrapping mode around the picture. */
	wrap(img: HTMLImageElement, mode: 'inline' | 'square' | 'behind' | 'front'): void {
		switch (mode) {
			case 'square':
				img.style.float = 'right';
				img.style.margin = '0 0 8px 12px';
				break;
			case 'behind':
				img.style.position = 'absolute';
				img.style.zIndex = '-1';
				img.style.opacity = '0.6';
				break;
			case 'front':
				img.style.position = 'relative';
				img.style.zIndex = '10';
				break;
			default:
				img.style.float = 'none';
				img.style.position = 'static';
		}
	},
};
