/**
 * Unit tests for the review library: comments, track changes, word count,
 * spelling, thesaurus and the accessibility inspector.
 */
import { describe, expect, it, beforeEach } from 'vitest';
import {
	acceptAll,
	collectComments,
	collectRevisions,
	deleteComment,
	inspectDocument,
	lookupSynonyms,
	markComment,
	rejectAll,
	resolveComment,
	tracking,
	trackInsert,
	wordCount,
	spellCheck,
} from './review';

function doc(html: string): HTMLElement {
	const div = document.createElement('div');
	div.innerHTML = html;
	document.body.appendChild(div);
	return div;
}

describe('comments', () => {
	it('collects existing anchors', () => {
		const root = doc('<p>a<span data-comment="c1" data-author="Ani" data-comment-text="cek">b</span></p>');
		const list = collectComments(root);
		expect(list).toHaveLength(1);
		expect(list[0]).toMatchObject({ id: 'c1', author: 'Ani', text: 'cek' });
	});

	it('resolves a comment but keeps the text', () => {
		const root = doc('<p><span data-comment="c1">kata</span></p>');
		resolveComment(root, 'c1');
		expect(root.querySelector('[data-comment]')).toBeNull();
		expect(root.textContent).toContain('kata');
	});

	it('deletes the comment and its text', () => {
		const root = doc('<p><span data-comment="c1">kata</span> sisa</p>');
		deleteComment(root, 'c1');
		expect(root.textContent).not.toContain('kata');
		expect(root.textContent).toContain('sisa');
	});
});

describe('track changes', () => {
	beforeEach(() => {
		tracking.enabled = false;
	});

	it('does nothing when tracking is off', () => {
		expect(trackInsert('x')).toBe(false);
	});

	it('accept keeps insertions and drops deletions', () => {
		const root = doc('<p>a<ins data-revision="insert">baru</ins><del data-revision="delete">lama</del>c</p>');
		const n = acceptAll(root);
		expect(n).toBe(2);
		expect(root.innerHTML).toContain('baru');
		expect(root.innerHTML).not.toContain('lama');
		expect(root.querySelector('[data-revision]')).toBeNull();
	});

	it('reject drops insertions and keeps deletions', () => {
		const root = doc('<p><ins data-revision="insert">baru</ins><del data-revision="delete">lama</del></p>');
		rejectAll(root);
		expect(root.innerHTML).not.toContain('baru');
		expect(root.innerHTML).toContain('lama');
	});

	it('counts every revision', () => {
		const root = doc('<ins data-revision="insert">a</ins><del data-revision="delete">b</del>');
		expect(collectRevisions(root)).toHaveLength(2);
	});
});

describe('wordCount', () => {
	it('counts words, characters and paragraphs', () => {
		const root = doc('<p>satu dua tiga</p><p>empat lima</p>');
		const wc = wordCount(root);
		expect(wc.words).toBe(5);
		expect(wc.charactersNoSpaces).toBeGreaterThan(10);
		expect(wc.paragraphs).toBeGreaterThanOrEqual(1);
		expect(wc.pages).toBeGreaterThanOrEqual(1);
	});
});

describe('spellCheck', () => {
	it('flags implausible letter runs but accepts common words', () => {
		const issues = spellCheck('yang dan asddd');
		const words = issues.map((i) => i.word);
		expect(words).toContain('asddd');
		expect(words).not.toContain('yang');
	});

	it('accepts capitalised proper nouns', () => {
		expect(spellCheck('Jakrrta').map((i) => i.word)).not.toContain('Jakrrta');
	});
});

describe('thesaurus', () => {
	it('returns known synonyms', () => {
		expect(lookupSynonyms('bagus')).toContain('baik');
	});

	it('returns an empty list for unknown words', () => {
		expect(lookupSynonyms('zzzz')).toEqual([]);
	});
});

describe('inspectDocument', () => {
	it('flags images without alt text and tables without headers', () => {
		const root = doc('<img src="x.png"><table><tr><td>1</td></tr></table>');
		const msgs = inspectDocument(root).map((f) => f.message);
		expect(msgs.some((m) => m.includes('teks alternatif'))).toBe(true);
		expect(msgs.some((m) => m.includes('header'))).toBe(true);
	});

	it('reports a heading-level jump', () => {
		const root = doc('<h1>a</h1><h3>b</h3>');
		expect(inspectDocument(root).some((f) => f.message.includes('H1'))).toBe(true);
	});
});

// markComment needs a real selection; it is exercised in the browser smoke test.
void markComment;
