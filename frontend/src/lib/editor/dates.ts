/**
 * Indonesian formatters shared by the editor UI.
 *
 * `Intl` already localises numbers and dates; these helpers add the manuscript
 * specific shapes Naskah Studio needs (long date, short date, page labels) and
 * a deterministic number formatter so the status bar never flickers between
 * browser locales.
 */

const LONG_DATE: Intl.DateTimeFormatOptions = {
	weekday: 'long',
	day: 'numeric',
	month: 'long',
	year: 'numeric',
};

const SHORT_DATE: Intl.DateTimeFormatOptions = {
	day: '2-digit',
	month: '2-digit',
	year: 'numeric',
};

/** "Senin, 3 Maret 2026" */
export function longDate(d: Date = new Date()): string {
	return new Intl.DateTimeFormat('id-ID', LONG_DATE).format(d);
}

/** "03/03/2026" */
export function shortDate(d: Date = new Date()): string {
	return new Intl.DateTimeFormat('id-ID', SHORT_DATE).format(d);
}

/** "14:05" */
export function clockTime(d: Date = new Date()): string {
	return new Intl.DateTimeFormat('id-ID', { hour: '2-digit', minute: '2-digit' }).format(d);
}

/** "Senin, 3 Maret 2026 pukul 14.05" */
export function dateTimeStamp(d: Date = new Date()): string {
	return `${longDate(d)} pukul ${new Intl.DateTimeFormat('id-ID', {
		hour: '2-digit',
		minute: '2-digit',
	}).format(d).replace(':', '.')}`;
}

/** Thousands-separated integer, e.g. 12.345 */
export function formatNumber(n: number): string {
	return new Intl.NumberFormat('id-ID').format(Math.round(n));
}

/** Roman numerals used for front-matter page numbering (i, ii, iii…). */
export function roman(n: number): string {
	if (n <= 0) return '';
	const table: [number, string][] = [
		[1000, 'm'],
		[900, 'cm'],
		[500, 'd'],
		[400, 'cd'],
		[100, 'c'],
		[90, 'xc'],
		[50, 'l'],
		[40, 'xl'],
		[10, 'x'],
		[9, 'ix'],
		[5, 'v'],
		[4, 'iv'],
		[1, 'i'],
	];
	let out = '';
	let v = n;
	for (const [value, glyph] of table) {
		while (v >= value) {
			out += glyph;
			v -= value;
		}
	}
	return out;
}

export type PageNumberFormat = 'decimal' | 'roman' | 'alpha';

/** Label a page according to the chosen numbering format. */
export function pageLabel(n: number, format: PageNumberFormat = 'decimal'): string {
	if (format === 'roman') return roman(n);
	if (format === 'alpha') return String.fromCharCode(96 + Math.min(26, Math.max(1, n)));
	return String(n);
}
