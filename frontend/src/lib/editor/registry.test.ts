/**
 * Unit tests for the command registry and the styles model.
 */
import { describe, expect, it } from 'vitest';
import { CommandRegistry } from './commandRegistry';
import { BUILTIN_STYLES, findStyle } from './styles';

function registry() {
	const r = new CommandRegistry();
	r.registerAll([
		{ id: 'format.bold', label: 'Tebal', tab: 'Home', group: 'Font', keywords: ['bold'], run: () => {} },
		{ id: 'insert.table', label: 'Sisipkan tabel', tab: 'Insert', group: 'Tabel', run: () => {} },
		{ id: 'references.toc', label: 'Daftar isi', tab: 'References', group: 'Daftar Isi', run: () => {} },
	]);
	return r;
}

describe('CommandRegistry', () => {
	it('stores and retrieves commands by id', () => {
		expect(registry().get('format.bold')?.tab).toBe('Home');
	});

	it('returns every command for an empty query', () => {
		expect(registry().search('')).toHaveLength(3);
	});

	it('matches on label, tab and keywords', () => {
		const r = registry();
		expect(r.search('tebal').map((c) => c.id)).toEqual(['format.bold']);
		expect(r.search('bold').map((c) => c.id)).toEqual(['format.bold']);
		expect(r.search('insert').map((c) => c.id)).toEqual(['insert.table']);
	});

	it('requires every token to match', () => {
		expect(registry().search('tabel insert')).toHaveLength(1);
		expect(registry().search('tabel home')).toHaveLength(0);
	});

	it('ranks prefix label matches first', () => {
		const r = new CommandRegistry();
		r.registerAll([
			{ id: 'a', label: 'Sorotan tabel', tab: 'Home', group: 'X', run: () => {} },
			{ id: 'b', label: 'Tabel baru', tab: 'Home', group: 'X', run: () => {} },
		]);
		expect(r.search('tabel')[0].id).toBe('b');
	});

	it('groups by tab', () => {
		const groups = registry().byTab();
		expect(groups.get('Home')?.[0].id).toBe('format.bold');
	});
});

describe('styles', () => {
	it('exposes Word-like built-in styles', () => {
		const names = BUILTIN_STYLES.map((s) => s.name);
		expect(names).toContain('Normal');
		expect(names).toContain('Heading 1');
		expect(names).toContain('Quote');
	});

	it('findStyle returns the matching style or Normal', () => {
		expect(findStyle('Heading 2').tag).toBe('h2');
		expect(findStyle('Nope').name).toBe('Normal');
	});
});
