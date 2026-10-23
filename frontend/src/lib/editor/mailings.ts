/**
 * mailings — Word's Mailings tab: import a recipient list, insert merge fields,
 * preview one record at a time and finish by merging into a numbered set of
 * documents.
 *
 * The datasource is CSV text (Wordcraft reads CSV too). Fields appear in the
 * manuscript as `{{Nama Kolom}}` placeholders; merge replaces them per record.
 * Placeholders are kept as text rather than markup so a merged output is a plain
 * document an operator can keep editing.
 */

/** A parsed CSV table: the header row plus data rows keyed by header. */
export interface Recipients {
	fields: string[];
	rows: Record<string, string>[];
}

/** Minimal RFC-4180 CSV parser (quotes, embedded commas and newlines). */
export function parseCsv(text: string): Recipients {
	const rows: string[][] = [];
	let field = '';
	let row: string[] = [];
	let inQuotes = false;
	const pushField = () => {
		row.push(field);
		field = '';
	};
	const pushRow = () => {
		pushField();
		if (row.some((c) => c.trim() !== '')) rows.push(row);
		row = [];
	};
	for (let i = 0; i < text.length; i++) {
		const ch = text[i];
		if (inQuotes) {
			if (ch === '"') {
				if (text[i + 1] === '"') {
					field += '"';
					i++;
				} else inQuotes = false;
			} else field += ch;
		} else if (ch === '"') inQuotes = true;
		else if (ch === ',') pushField();
		else if (ch === '\r') continue;
		else if (ch === '\n') pushRow();
		else field += ch;
	}
	if (field !== '' || row.length) pushRow();

	if (!rows.length) return { fields: [], rows: [] };
	const fields = rows[0].map((h) => h.trim());
	return {
		fields,
		rows: rows.slice(1).map((r) => {
			const rec: Record<string, string> = {};
			fields.forEach((f, i) => (rec[f] = (r[i] ?? '').trim()));
			return rec;
		}),
	};
}

/** The `{{Field}}` placeholder text for one merge field. */
export function mergePlaceholder(field: string): string {
	return `{{${field}}}`;
}

/** Address block for one record, or '' when the field set is too thin. */
export function addressBlock(rec: Record<string, string>): string {
	const name = [rec['Nama'] ?? rec['Nama Depan'] ?? '', rec['Nama Belakang'] ?? ''].join(' ').trim();
	const lines = [name, rec['Alamat'] ?? rec['Jalan'] ?? '', rec['Kota'] ?? '', rec['Kode Pos'] ?? ''].filter(
		Boolean
	);
	return lines.join('\n');
}

/** Greeting line, e.g. "Kepada Yth. Budi Santoso,". */
export function greetingLine(rec: Record<string, string>, template = 'Kepada Yth. {nama},'): string {
	const fullName = `${rec['Nama Depan'] ?? ''} ${rec['Nama Belakang'] ?? ''}`.trim();
	const nama = rec['Nama'] || fullName || 'Bapak/Ibu';
	return template.replace(/\{nama\}/g, nama);
}

/** Evaluate simple Word merge rules: {IF field = value "then" "else"}. */
export function applyRules(text: string, rec: Record<string, string>): string {
	return text.replace(/\{IF\s+(\w+)\s*=\s*"?([^"\s]+)"?\s*"([^"]*)"\s*"([^"]*)"\}/gi, (_m, f, v, a, b) =>
		(rec[f] ?? '') === v ? a : b
	);
}

/** Substitute every `{{Field}}` in `source` with the record's value. */
export function mergeRecord(source: string, rec: Record<string, string>): string {
	return source.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (whole, key) => {
		const value = rec[key.trim()];
		return value === undefined ? whole : escapeHtml(value);
	});
}

/** Render every record into a paged output separated by page breaks. */
export function mergeAll(source: string, recs: Recipients): string {
	const pages = recs.rows.map((rec) => `<div data-merge-record>${mergeRecord(source, rec)}</div>`);
	return pages.join('<div class="naskah-pagebreak" contenteditable="false"></div>');
}

/** Envelope and label layouts (Word's Create group). */
export const LAYOUTS = {
	'Envelope C5': { w: '162mm', h: '114mm', count: 1, label: 'Amplop C5' },
	'Label 3×8': { w: '64mm', h: '33mm', count: 24, label: 'Label 3×8 (24)' },
	'Label 2×5': { w: '100mm', h: '50mm', count: 10, label: 'Label 2×5 (10)' },
} as const;
export type LayoutName = keyof typeof LAYOUTS;

/** A sheet of labels/envelopes, each cell containing the merged record. */
export function labelSheet(source: string, recs: Recipients, layout: LayoutName): string {
	const def = LAYOUTS[layout];
	const cells = recs.rows
		.slice(0, def.count)
		.map(
			(rec) =>
				`<td style="width:${def.w};height:${def.h};padding:4mm;border:1px dashed #ccc;vertical-align:top;font-size:9pt">${mergeRecord(
					source,
					rec
				)}</td>`
		);
	const perRow = 3;
	let rows = '';
	for (let i = 0; i < cells.length; i += perRow) {
		rows += `<tr>${cells.slice(i, i + perRow).join('')}</tr>`;
	}
	return `<table data-object="labels" style="border-collapse:collapse;margin:0 auto"><tbody>${rows}</tbody></table>`;
}

/** Highlight every merge field so the author can see where data will land. */
export function highlightFields(html: string, on = true): string {
	if (!on) {
		return html.replace(/<span class="naskah-merge-field" data-field="([^"]*)">([^<]*)<\/span>/g, (_m, _f, inner) => inner);
	}
	return html.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (_m, field) =>
		`<span class="naskah-merge-field" data-field="${escapeAttr(field.trim())}">${escapeHtml(
			field.trim()
		)}</span>`
	);
}

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}
function escapeAttr(s: string): string {
	return escapeHtml(s);
}
