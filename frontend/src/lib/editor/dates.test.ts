/**
 * Unit tests for the Indonesian formatters and page labels.
 */
import { describe, expect, it } from 'vitest';
import { dateTimeStamp, formatNumber, longDate, pageLabel, roman, shortDate } from './dates';

describe('dates', () => {
	it('formats a long Indonesian date', () => {
		const out = longDate(new Date(2026, 2, 3)); // 3 March 2026
		expect(out.toLowerCase()).toContain('maret');
		expect(out).toContain('2026');
	});

	it('formats a short numeric date with two-digit parts', () => {
		expect(shortDate(new Date(2026, 0, 5))).toMatch(/05.*01.*2026/);
	});

	it('builds a date-time stamp with "pukul"', () => {
		expect(dateTimeStamp(new Date(2026, 0, 5, 14, 5))).toContain('pukul 14.05');
	});

	it('groups thousands with dots', () => {
		expect(formatNumber(1234567)).toBe('1.234.567');
	});
});

describe('roman numerals', () => {
	it.each([
		[1, 'i'],
		[4, 'iv'],
		[9, 'ix'],
		[14, 'xiv'],
		[40, 'xl'],
		[1990, 'mcmxc'],
	])('%i → %s', (n, expected) => {
		expect(roman(n)).toBe(expected);
	});

	it('returns empty for non-positive input', () => {
		expect(roman(0)).toBe('');
	});
});

describe('pageLabel', () => {
	it('uses decimal by default', () => {
		expect(pageLabel(7)).toBe('7');
	});
	it('supports roman and alpha numbering', () => {
		expect(pageLabel(4, 'roman')).toBe('iv');
		expect(pageLabel(1, 'alpha')).toBe('a');
		expect(pageLabel(3, 'alpha')).toBe('c');
	});
});
