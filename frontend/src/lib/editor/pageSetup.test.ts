/**
 * Unit tests for the page-setup model and header/footer/watermark markup.
 */
import { describe, expect, it } from 'vitest';
import {
	MARGIN_PRESETS,
	PAPER_SIZES,
	defaultSection,
	footerMarkup,
	headerMarkup,
	pageDimensions,
	paperStyle,
	spacingMultiplier,
	watermarkMarkup,
} from './pageSetup';

describe('pageDimensions', () => {
	it('uses A4 portrait by default', () => {
		const s = defaultSection();
		const d = pageDimensions(s);
		expect(d.width).toBe(PAPER_SIZES.A4.w);
		expect(d.height).toBe(PAPER_SIZES.A4.h);
	});

	it('swaps width and height in landscape', () => {
		const s = { ...defaultSection(), orientation: 'landscape' as const };
		const d = pageDimensions(s);
		expect(d.width).toBe(PAPER_SIZES.A4.h);
		expect(d.height).toBe(PAPER_SIZES.A4.w);
	});

	it('honours the chosen paper size', () => {
		const s = { ...defaultSection(), paper: 'Letter' as const };
		expect(pageDimensions(s).width).toBe(PAPER_SIZES.Letter.w);
	});
});

describe('paperStyle', () => {
	it('emits the four-margin padding', () => {
		const s = defaultSection();
		s.margins = { ...MARGIN_PRESETS.Sempit };
		const css = paperStyle(s);
		expect(css).toContain(`padding:${MARGIN_PRESETS.Sempit.top}px`);
	});

	it('adds columns only when more than one', () => {
		expect(paperStyle(defaultSection())).not.toContain('column-count');
		const s = { ...defaultSection(), columns: 2 };
		expect(paperStyle(s)).toContain('column-count:2');
	});

	it('draws a page border as an outline when enabled', () => {
		const s = { ...defaultSection(), pageBorder: { on: true, width: 2, color: '#f00', style: 'double' as const } };
		expect(paperStyle(s)).toContain('outline:');
		expect(paperStyle(s)).toContain('#f00');
	});
});

describe('spacingMultiplier', () => {
	it.each([
		['none', '1.15'],
		['compact', '1.25'],
		['normal', '1.5'],
		['loose', '2'],
	])('%s → %s', (preset, expected) => {
		expect(spacingMultiplier(preset as never)).toBe(expected);
	});
});

describe('headerMarkup / footerMarkup', () => {
	it('is empty when there is nothing to show', () => {
		expect(headerMarkup(defaultSection())).toBe('');
		expect(footerMarkup(defaultSection())).toBe('');
	});

	it('renders header text and an escaped page field', () => {
		const s = { ...defaultSection(), header: 'Bab <1>', showPageNumbers: true };
		const html = headerMarkup(s, 3);
		expect(html).toContain('Bab &lt;1&gt;');
		expect(html).toContain('>3<');
	});

	it('renders a roman page field when configured', () => {
		const s = { ...defaultSection(), showPageNumbers: true, pageNumberFormat: 'roman' as const };
		expect(footerMarkup(s, 4)).toContain('>iv<');
	});
});

describe('watermarkMarkup', () => {
	it('is empty without a watermark', () => {
		expect(watermarkMarkup(defaultSection())).toBe('');
	});

	it('escapes the watermark text', () => {
		const s = { ...defaultSection(), watermark: { text: 'DRAF <x>', opacity: 0.1, rotate: -30, color: '#888' } };
		const html = watermarkMarkup(s);
		expect(html).toContain('DRAF &lt;x&gt;');
		expect(html).toContain('rotate(-30deg)');
		expect(html).toContain('opacity:0.1');
	});
});
