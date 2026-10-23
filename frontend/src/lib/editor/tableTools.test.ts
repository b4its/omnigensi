/**
 * Unit tests for the table operations, driven through a real selection in jsdom.
 * These cover the regressions that a live `row.cells` collection causes when
 * cells are removed during iteration.
 */
import { describe, expect, it, beforeEach } from 'vitest';
import { activeCell, activeTable, selectionBox, tableTools } from './tableTools';

const TABLE = `<table><tbody>
  <tr><td>a</td><td>b</td><td>c</td></tr>
  <tr><td>d</td><td>e</td><td>f</td></tr>
</tbody></table>`;

function mount(html = TABLE): HTMLElement {
	document.body.innerHTML = `<div class="naskah-content">${html}<p>after</p></div>`;
	return document.querySelector('.naskah-content') as HTMLElement;
}

/** Put the caret inside a cell and (optionally) select up to another cell. */
function caretIn(root: HTMLElement, row: number, col: number, endCol = col): void {
	const table = root.querySelector('table') as HTMLTableElement;
	const start = table.rows[row].cells[col];
	const end = table.rows[row].cells[endCol];
	const range = document.createRange();
	range.setStart(start, 0);
	range.setEnd(end, end.childNodes.length);
	const sel = window.getSelection();
	sel?.removeAllRanges();
	sel?.addRange(range);
}

beforeEach(() => {
	document.body.innerHTML = '';
});

describe('activeTable / activeCell', () => {
	it('finds the table and cell under the caret', () => {
		const root = mount();
		caretIn(root, 1, 1);
		expect(activeTable()).not.toBeNull();
		expect(activeCell()?.textContent).toBe('e');
	});

	it('is null outside a table', () => {
		mount();
		const sel = window.getSelection();
		const range = document.createRange();
		range.selectNodeContents(document.querySelector('p') as HTMLElement);
		sel?.removeAllRanges();
		sel?.addRange(range);
		expect(activeCell()).toBeNull();
	});
});

describe('selectionBox', () => {
	it('reports the selected column span', () => {
		const root = mount();
		caretIn(root, 0, 0, 1);
		const box = selectionBox();
		expect(box?.rows).toEqual([0]);
		expect(box?.cols).toEqual([0, 1]);
	});
});

describe('mergeCells', () => {
	it('merges the selected cells into the first one', () => {
		const root = mount();
		caretIn(root, 0, 0, 1);
		tableTools.mergeCells();
		const row = (root.querySelector('table') as HTMLTableElement).rows[0];
		expect(row.cells[0].colSpan).toBe(2);
		expect(row.cells).toHaveLength(2); // merged + "c"
		expect(row.cells[0].textContent).toContain('a');
		expect(row.cells[0].textContent).toContain('b');
	});

	it('merges a rectangular block across rows', () => {
		const root = mount();
		const table = root.querySelector('table') as HTMLTableElement;
		const range = document.createRange();
		range.setStart(table.rows[0].cells[0], 0);
		range.setEnd(table.rows[1].cells[1], 1);
		window.getSelection()?.removeAllRanges();
		window.getSelection()?.addRange(range);

		tableTools.mergeCells();
		const anchor = (root.querySelector('table') as HTMLTableElement).rows[0].cells[0];
		expect(anchor.colSpan).toBe(2);
		expect(anchor.rowSpan).toBe(2);
	});

	it('does nothing with a single cell', () => {
		const root = mount();
		caretIn(root, 0, 0);
		tableTools.mergeCells();
		expect((root.querySelector('td') as HTMLTableCellElement).colSpan).toBe(1);
	});
});

describe('splitCell', () => {
	it('splits a merged cell back into plain cells', () => {
		const root = mount();
		caretIn(root, 0, 0, 1);
		tableTools.mergeCells();
		const table = root.querySelector('table') as HTMLTableElement;
		const range = document.createRange();
		range.selectNodeContents(table.rows[0].cells[0]);
		window.getSelection()?.removeAllRanges();
		window.getSelection()?.addRange(range);
		tableTools.splitCell(1, 2);
		expect((root.querySelector('td') as HTMLTableCellElement).colSpan).toBe(1);
	});
});

describe('banded rows / repeat header', () => {
	it('toggles the banded attribute', () => {
		const root = mount();
		caretIn(root, 0, 0);
		tableTools.bandedRows(true);
		expect(root.querySelector('table')?.hasAttribute('data-banded')).toBe(true);
	});

	it('marks a header row for repetition', () => {
		const root = mount('<table><thead><tr><th>H</th></tr></thead><tbody><tr><td>x</td></tr></tbody></table>');
		caretIn(root, 0, 0);
		tableTools.repeatHeader(true);
		expect(root.querySelector('table thead')).not.toBeNull();
	});
});

describe('shade / borders / distribute', () => {
	it('shades the active cell', () => {
		const root = mount();
		caretIn(root, 0, 1);
		tableTools.shade('#FFF3CD');
		expect(activeCell()?.style.background).toContain('255');
	});

	it('applies a border to every cell', () => {
		const root = mount();
		caretIn(root, 0, 0);
		tableTools.borders('1px solid #000');
		expect(root.querySelector('td')?.style.border).toContain('1px');
	});

	it('distributes column widths evenly', () => {
		const root = mount();
		caretIn(root, 0, 0);
		tableTools.distributeColumns();
		expect(root.querySelector('td')?.style.width).toBe('33.333%');
	});
});

describe('sort / formulas', () => {
	it('sorts rows by the active column', () => {
		const root = mount('<table><tbody><tr><td>3</td></tr><tr><td>1</td></tr><tr><td>2</td></tr></tbody></table>');
		caretIn(root, 0, 0);
		tableTools.sort(true);
		const values = Array.from(root.querySelectorAll('td')).map((c) => c.textContent);
		expect(values).toEqual(['1', '2', '3']);
	});

	it('evaluates SUM(ABOVE)', () => {
		const root = mount('<table><tbody><tr><td>10</td></tr><tr><td>5</td></tr><tr><td>=SUM(ABOVE)</td></tr></tbody></table>');
		caretIn(root, 2, 0);
		tableTools.formulas();
		expect(root.querySelectorAll('td')[2].textContent).toBe('15');
	});
});

describe('toText', () => {
	it('replaces the table with tab-separated text', () => {
		const root = mount();
		caretIn(root, 0, 0);
		tableTools.toText();
		expect(root.querySelector('table')).toBeNull();
		expect(root.textContent).toContain('a\tb\tc');
	});
});
