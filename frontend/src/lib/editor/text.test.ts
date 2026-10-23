/**
 * Unit tests for the engine-independent plain-text helpers that back word
 * counts and the .txt export (jsdom has no `innerText`).
 */
import { describe, expect, it } from 'vitest';
import { countText, plainText, textOf } from './text';

function el(html: string): HTMLElement {
	const div = document.createElement('div');
	div.innerHTML = html;
	return div;
}

describe('textOf / plainText', () => {
	it('separates block elements with newlines', () => {
		expect(plainText(el('<p>satu</p><p>dua</p>'))).toBe('satu\ndua');
	});

	it('turns <br> into a newline', () => {
		expect(plainText(el('<p>a<br>b</p>'))).toBe('a\nb');
	});

	it('joins table cells with tabs', () => {
		expect(plainText(el('<table><tr><td>1</td><td>2</td></tr></table>'))).toBe('1\t2');
	});

	it('keeps inline runs glued without spurious spaces in block mode', () => {
		expect(plainText(el('<p>Ha<b>lo</b> dunia</p>'))).toBe('Halo dunia');
	});

	it('adds spacing at tag boundaries in spaced mode', () => {
		expect(textOf(el('<p>a<b>b</b></p>'), 'spaced')).toContain('a b');
	});

	it('normalises non-breaking spaces', () => {
		expect(plainText(el('<p>a\u00a0b</p>'))).toBe('a b');
	});

	it('returns empty for null', () => {
		expect(plainText(null)).toBe('');
	});
});

describe('countText', () => {
	const root = el('<p>satu dua tiga</p><p>empat lima</p>');

	it('counts words across paragraphs', () => {
		expect(countText(root).words).toBe(5);
	});

	it('counts characters with and without spaces', () => {
		const c = countText(root);
		expect(c.characters).toBeGreaterThan(c.charactersNoSpaces);
	});

	it('counts one paragraph per line run', () => {
		expect(countText(root).paragraphs).toBe(2);
	});

	it('estimates pages from the word capacity', () => {
		expect(countText(root, 2).pages).toBe(3);
	});
});
