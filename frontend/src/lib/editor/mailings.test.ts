/**
 * Unit tests for the mail-merge helpers: CSV parsing, record merging, labels
 * and field highlighting.
 */
import { describe, expect, it } from 'vitest';
import { applyRules, addressBlock, greetingLine, highlightFields, labelSheet, mergeAll, mergePlaceholder, mergeRecord, parseCsv } from './mailings';

const CSV = `Nama,Kota,Nilai
"Budi, S.Pd",Jakarta,90
Rina,Bandung,85
"Sari""Sari""",Surabaya,70`;

describe('parseCsv', () => {
	const rec = parseCsv(CSV);

	it('reads the header row', () => {
		expect(rec.fields).toEqual(['Nama', 'Kota', 'Nilai']);
	});

	it('handles quoted fields with a comma', () => {
		expect(rec.rows[0]['Nama']).toBe('Budi, S.Pd');
	});

	it('handles escaped double quotes', () => {
		expect(rec.rows[2]['Nama']).toBe('Sari"Sari"');
	});

	it('returns empty for blank input', () => {
		expect(parseCsv('').fields).toEqual([]);
	});

	it('ignores blank lines', () => {
		expect(parseCsv('A,B\n\n1,2\n').rows).toHaveLength(1);
	});
});

describe('mergePlaceholder / mergeRecord', () => {
	it('wraps a field in double braces', () => {
		expect(mergePlaceholder('Nama')).toBe('{{Nama}}');
	});

	it('substitutes known fields', () => {
		expect(mergeRecord('Halo {{Nama}}!', { Nama: 'Budi' })).toBe('Halo Budi!');
	});

	it('leaves unknown fields untouched', () => {
		expect(mergeRecord('Halo {{X}}', {})).toBe('Halo {{X}}');
	});

	it('escapes HTML in values', () => {
		expect(mergeRecord('{{Nama}}', { Nama: '<b>' })).toBe('&lt;b&gt;');
	});

	it('greeting falls back when no name is present', () => {
		expect(greetingLine({})).toContain('Bapak/Ibu');
	});

	it('address block joins non-empty lines', () => {
		const block = addressBlock({ Nama: 'Budi', Alamat: 'Jl. A', Kota: 'Jakarta' });
		expect(block.split('\n')).toHaveLength(3);
	});
});

describe('mergeAll / labelSheet', () => {
	const rec = parseCsv(CSV);

	it('merges every record separated by page breaks', () => {
		const out = mergeAll('<p>{{Nama}}</p>', rec);
		expect(out).toContain('Budi, S.Pd');
		expect((out.match(/naskah-pagebreak/g) ?? []).length).toBe(rec.rows.length - 1);
	});

	it('lays out at most one label sheet worth of cells', () => {
		const out = labelSheet('<p>{{Nama}}</p>', rec, 'Label 3×8');
		expect(out).toContain('<table');
		expect(out).toContain('Budi');
	});
});

describe('applyRules', () => {
	it('evaluates an IF rule', () => {
		expect(applyRules('{IF Kota = "Jakarta" "ibu kota" "daerah"}', { Kota: 'Jakarta' })).toBe('ibu kota');
		expect(applyRules('{IF Kota = "Jakarta" "ibu kota" "daerah"}', { Kota: 'Bandung' })).toBe('daerah');
	});
});

describe('highlightFields', () => {
	it('wraps merge fields in a span', () => {
		const html = highlightFields('<p>Halo {{Nama}}</p>');
		expect(html).toContain('class="naskah-merge-field"');
		expect(html).toContain('data-field="Nama"');
	});

	it('unwraps previously highlighted fields', () => {
		const html = highlightFields('<p>Halo <span class="naskah-merge-field" data-field="Nama">Nama</span></p>', false);
		expect(html).not.toContain('naskah-merge-field');
		expect(html).toContain('Halo Nama');
	});
});
