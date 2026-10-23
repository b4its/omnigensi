/**
 * Unit tests for the LibreOffice layout helpers and the Writer hyperlink model.
 */
import { describe, expect, it } from 'vitest';
import {
	breakMarkup,
	collectMarginNotes,
	pageFieldMarkup,
	pageOfTotal,
	refreshPageFields,
	writerStatus,
} from './loLayout';
import { emptyLink, linkMarkup, resolveTarget, validateLink } from './loLinks';

describe('page fields', () => {
	const ctx = { format: 'decimal' as const, start: 1 };

	it('renders a page number field', () => {
		expect(pageFieldMarkup(ctx, 3)).toContain('>3<');
	});

	it('renders a "page x of y" field', () => {
		expect(pageOfTotal(ctx, 2, 9)).toContain('/ 9');
	});

	it('applies a start offset', () => {
		expect(pageFieldMarkup({ format: 'decimal', start: 10 }, 5)).toContain('>14<');
	});

	it('refreshes every page field', () => {
		const root = document.createElement('div');
		root.innerHTML =
			'<span data-object="pagefield" data-value="1">x</span>' +
			'<span data-object="pagefield" data-value="2">x</span>';
		expect(refreshPageFields(root, ctx, 2)).toBe(2);
		expect(root.textContent).toContain('1');
		expect(root.textContent).toContain('2');
	});
});

describe('margin notes', () => {
	it('collects comments in document order', () => {
		const root = document.createElement('div');
		root.innerHTML =
			'<p><span data-comment="a" data-author="Ani" data-comment-text="satu">x</span></p>' +
			'<p><span data-comment="b" data-author="Budi" data-comment-text="dua">y</span></p>';
		const notes = collectMarginNotes(root);
		expect(notes.map((n) => n.id)).toEqual(['a', 'b']);
		expect(notes[1].author).toBe('Budi');
	});
});

describe('writerStatus', () => {
	it('formats pages and words in Indonesian', () => {
		const s = writerStatus(1, 7, 1234);
		expect(s.pages).toBe('Halaman 1 dari 7');
		expect(s.words).toBe('Kata 1.234');
	});
});

describe('breakMarkup', () => {
	it('emits the right marker for each break kind', () => {
		expect(breakMarkup('page')).toContain('naskah-pagebreak');
		expect(breakMarkup('column')).toContain('naskah-columnbreak');
		expect(breakMarkup('section')).toContain('naskah-sectionbreak');
	});
});

describe('loLinks', () => {
	it('starts as an empty internet link', () => {
		const link = emptyLink();
		expect(link.kind).toBe('internet');
	});

	it('resolves mail targets with a mailto prefix', () => {
		const link = { ...emptyLink(), kind: 'mail' as const, target: 'a@b.id' };
		expect(resolveTarget(link)).toBe('mailto:a@b.id');
	});

	it('resolves document targets to an anchor', () => {
		const link = { ...emptyLink(), kind: 'document' as const, bookmark: 'bab-1' };
		expect(resolveTarget(link)).toBe('#bab-1');
	});

	it('builds an anchor with a named target and new-window behaviour', () => {
		const html = linkMarkup({ ...emptyLink(), text: 'Situs', target: 'https://x', name: 'tautan-1' });
		expect(html).toContain('href="https://x"');
		expect(html).toContain('name="tautan-1"');
		expect(html).toContain('target="_blank"');
		expect(html).toContain('>Situs</a>');
	});

	it('validates an empty target and a document without a bookmark', () => {
		expect(validateLink({ ...emptyLink(), target: '' })).not.toBeNull();
		expect(validateLink({ ...emptyLink(), kind: 'document' })).not.toBeNull();
		expect(validateLink({ ...emptyLink(), kind: 'document', bookmark: 'x' })).toBeNull();
	});
});
