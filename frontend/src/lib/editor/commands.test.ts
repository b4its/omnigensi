/**
 * Unit tests for the insert-block detection that decides whether an HTML
 * payload must be placed on its own paragraph (regression: AutoText blocks were
 * nested inside the current paragraph).
 */
import { describe, expect, it } from 'vitest';
import { startsWithBlock } from './commands';

describe('startsWithBlock', () => {
	it.each([
		'<p>hi</p>',
		'<h1>Judul</h1>',
		'<H2>besar</H2>',
		'<div>x</div>',
		'<table><tr><td>1</td></tr></table>',
		'<ul><li>a</li></ul>',
		'<ol><li>a</li></ol>',
		'<blockquote>q</blockquote>',
		'<pre>code</pre>',
		'<hr/>',
		'<dl><dt>a</dt></dl>',
		'  <p>leading space</p>',
	])('treats %s as a block', (html) => {
		expect(startsWithBlock(html)).toBe(true);
	});

	it.each(['<span>x</span>', '<a href="#">x</a>', '<img src="x">', 'teks biasa', '<b>tebal</b>'])(
		'treats %s as inline',
		(html) => {
			expect(startsWithBlock(html)).toBe(false);
		}
	);
});
