/**
 * Insert-tab building blocks: the ready-made snippets the ribbon drops into the
 * manuscript — cover pages, blank pages, quick tables, shapes, icons, charts,
 * SmartArt, text boxes, WordArt, drop caps, signature lines, equations and
 * non-breaking characters.
 *
 * Each builder returns an HTML string with `data-` hooks so the object layer
 * (resizing, alt text, styles) can find and edit the object after insertion.
 */

function esc(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}

export const COVER_TEMPLATES = ['Formal', 'Minimal', 'Laporan'] as const;
export type CoverTemplate = (typeof COVER_TEMPLATES)[number];

/** A full-page cover block that ends with a page break. */
export function coverPage(title: string, subtitle = '', template: CoverTemplate = 'Formal'): string {
	const body =
		template === 'Minimal'
			? `<div class="naskah-cover naskah-cover-minimal" data-object="cover">
          <h1 style="font-size:32pt;font-weight:300;margin-top:35%">${esc(title)}</h1>
          <p style="font-size:13pt;color:#777">${esc(subtitle)}</p>
        </div>`
			: template === 'Laporan'
				? `<div class="naskah-cover naskah-cover-report" data-object="cover">
          <p style="text-transform:uppercase;letter-spacing:.2em;font-size:10pt;color:#666">Laporan</p>
          <hr style="width:40%;margin:12px auto;border-color:#999"/>
          <h1 style="font-size:26pt;margin-top:8%">${esc(title)}</h1>
          <p style="font-size:12pt;color:#555">${esc(subtitle)}</p>
          <p style="margin-top:30%;font-size:10pt;color:#888">Disusun oleh: ______________</p>
        </div>`
				: `<div class="naskah-cover naskah-cover-formal" data-object="cover">
          <div style="border-top:4px solid currentColor;border-bottom:1px solid currentColor;padding:18px 0;margin-top:22%">
            <h1 style="font-size:30pt;margin:0">${esc(title)}</h1>
            <p style="font-size:13pt;margin:6px 0 0;color:#555">${esc(subtitle)}</p>
          </div>
          <p style="margin-top:35%;font-size:11pt;line-height:1.9">
            Nama Penulis<br/>Institusi / Organisasi<br/>${new Date().getFullYear()}
          </p>
        </div>`;
	return `${body}<div class="naskah-pagebreak" contenteditable="false"></div><p><br/></p>`;
}

/** A blank filler page. */
export function blankPage(): string {
	return '<div class="naskah-pagebreak" contenteditable="false"></div><p><br/></p>';
}

export const QUICK_TABLES: Record<string, { headers: string[]; sample: string[][] }> = {
	'Kalender': {
		headers: ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min'],
		sample: [
			['', '', '', '', '', '', ''],
			['', '', '', '', '', '', ''],
			['', '', '', '', '', '', ''],
			['', '', '', '', '', '', ''],
		],
	},
	'Daftar Tugas': {
		headers: ['No', 'Tugas', 'Penanggung Jawab', 'Tenggat', 'Status'],
		sample: [
			['1', '', '', '', ''],
			['2', '', '', '', ''],
			['3', '', '', '', ''],
		],
	},
	'Matriks 2×2': {
		headers: ['', 'Kolom A', 'Kolom B'],
		sample: [
			['Baris 1', '', ''],
			['Baris 2', '', ''],
		],
	},
	'Perbandingan': {
		headers: ['Kriteria', 'Opsi A', 'Opsi B'],
		sample: [
			['Biaya', '', ''],
			['Waktu', '', ''],
			['Risiko', '', ''],
		],
	},
};

/** Render a quick table. */
export function quickTable(name: keyof typeof QUICK_TABLES): string {
	const def = QUICK_TABLES[name];
	let html = '<table class="naskah-table"><thead><tr>';
	for (const h of def.headers) html += `<th>${esc(h)}</th>`;
	html += '</tr></thead><tbody>';
	for (const row of def.sample) {
		html += '<tr>';
		for (const cell of row) html += `<td>${esc(cell) || '&nbsp;'}</td>`;
		html += '</tr>';
	}
	html += '</tbody></table><p><br/></p>';
	return html;
}

export const SHAPES = [
	{ key: 'rect', label: 'Persegi', path: '' },
	{ key: 'round', label: 'Lingkaran', path: '' },
	{ key: 'triangle', label: 'Segitiga', path: 'polygon(50% 0%, 100% 100%, 0% 100%)' },
	{ key: 'diamond', label: 'Belah Ketupat', path: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)' },
	{ key: 'arrow', label: 'Panah', path: 'polygon(0% 30%, 60% 30%, 60% 0%, 100% 50%, 60% 100%, 60% 70%, 0% 70%)' },
	{ key: 'star', label: 'Bintang', path: 'polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%)' },
] as const;

/** An inline SVG-free shape drawn with CSS, so it survives text export. */
export function shape(key: (typeof SHAPES)[number]['key'], color = '#0066FF'): string {
	const def = SHAPES.find((s) => s.key === key) ?? SHAPES[0];
	if (key === 'star' || key === 'triangle' || key === 'diamond' || key === 'arrow') {
		return `<svg data-object="shape" width="140" height="110" viewBox="0 0 140 110" style="vertical-align:middle">
          <polygon points="${starPoints(key)}" fill="${esc(color)}" stroke="${esc(color)}"/>
        </svg>&nbsp;`;
	}
	const radius = key === 'round' ? '50%' : '2px';
	return `<span data-object="shape" contenteditable="false" style="display:inline-block;width:120px;height:80px;background:${esc(
		color
	)};border-radius:${radius};vertical-align:middle;margin:4px"></span>&nbsp;`;
}

function starPoints(key: string): string {
	if (key === 'triangle') return '70,5 135,105 5,105';
	if (key === 'diamond') return '70,5 135,55 70,105 5,55';
	if (key === 'arrow') return '5,40 80,40 80,15 135,55 80,95 80,70 5,70';
	// five-point star
	const pts: string[] = [];
	for (let i = 0; i < 10; i++) {
		const r = i % 2 === 0 ? 52 : 22;
		const a = (Math.PI / 5) * i - Math.PI / 2;
		pts.push(`${(70 + r * Math.cos(a)).toFixed(1)},${(55 + r * Math.sin(a)).toFixed(1)}`);
	}
	return pts.join(' ');
}

/** Common icon glyphs rendered as inline SVG (Word's Icons picker). */
export const ICONS = ['★', '✓', '➜', '☎', '✉', '⚑', '♥', '⚙', '☀', '☁', '⌂', '⚠'] as const;

export function icon(glyph: string): string {
	return `<span data-object="icon" style="font-size:18pt;line-height:1;vertical-align:middle">${esc(glyph)}</span>&nbsp;`;
}

/** A text box (floating paragraph with a border). */
export function textBox(text = 'Teks kotak'): string {
	return `<div data-object="textbox" style="border:1px solid #888;padding:8px 12px;margin:8px 0;max-width:320px;min-height:48px">${esc(
		text
	)}</div><p><br/></p>`;
}

/** WordArt: large, traced-looking text. */
export function wordArt(text = 'WordArt'): string {
	return `<p data-object="wordart" style="font-size:34pt;font-weight:800;letter-spacing:-1px;background:linear-gradient(90deg,#0066FF,#00F0FF);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;text-align:center">${esc(
		text
	)}</p>`;
}

/** Drop cap: enlarge the first letter of the current paragraph. */
export function dropCap(lines = 3): string {
	return `<span data-object="dropcap" style="float:left;font-size:${3 * lines}em;line-height:0.9;padding-right:.08em;font-weight:700">`;
}

/** A signature line block. */
export function signatureLine(name = 'Nama Penanda Tangan', title = 'Jabatan'): string {
	return `<div data-object="signature" style="margin:14px 0">
      <div style="border-bottom:1px solid #333;width:240px;height:32px"></div>
      <div style="font-size:10pt;color:#444;margin-top:2px">${esc(name)}</div>
      <div style="font-size:9pt;color:#777">${esc(title)}</div>
    </div>`;
}

/** A simple bar/line chart, drawn as SVG and mostly self-contained. */
export function chart(kind: 'bar' | 'line' | 'pie', data: number[] = [4, 7, 3, 8, 5]): string {
	const max = Math.max(...data, 1);
	const w = 260;
	const h = 140;
	const bw = w / data.length - 8;
	if (kind === 'pie') {
		const total = data.reduce((a, b) => a + b, 0) || 1;
		let acc = 0;
		const colors = ['#0066FF', '#00F0FF', '#FFB800', '#FF0055', '#7C4DFF'];
		const slices = data
			.map((v, i) => {
				const start = (acc / total) * 2 * Math.PI;
				acc += v;
				const end = (acc / total) * 2 * Math.PI;
				const large = end - start > Math.PI ? 1 : 0;
				const x1 = 70 + 60 * Math.cos(start);
				const y1 = 70 + 60 * Math.sin(start);
				const x2 = 70 + 60 * Math.cos(end);
				const y2 = 70 + 60 * Math.sin(end);
				return `<path d="M70,70 L${x1},${y1} A60,60 0 ${large} 1 ${x2},${y2} Z" fill="${colors[i % colors.length]}"/>`;
			})
			.join('');
		return `<svg data-object="chart" width="140" height="140" viewBox="0 0 140 140">${slices}</svg>&nbsp;`;
	}
	if (kind === 'line') {
		const pts = data
			.map((v, i) => `${16 + (i * (w - 32)) / (data.length - 1)},${h - 10 - (v / max) * (h - 30)}`)
			.join(' ');
		return `<svg data-object="chart" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="#0066FF" stroke-width="2"/></svg>&nbsp;`;
	}
	const bars = data
		.map((v, i) => {
			const bh = (v / max) * (h - 30);
			return `<rect x="${i * (bw + 8)}" y="${h - 10 - bh}" width="${bw}" height="${bh}" fill="#0066FF"/>`;
		})
		.join('');
	return `<svg data-object="chart" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${bars}</svg>&nbsp;`;
}

/** SmartArt: a horizontal chevron process diagram. */
export function smartArt(steps: string[] = ['Langkah 1', 'Langkah 2', 'Langkah 3']): string {
	const items = steps
		.map(
			(s, i) =>
				`<div style="display:flex;align-items:center;flex:1;min-width:0">
          <span style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:#0066FF;color:#fff;font-size:11pt;margin-right:6px">${i + 1}</span>
          <span style="font-size:11pt;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s)}</span>
        </div>`
		)
		.join('<span style="color:#0066FF;margin:0 6px">➜</span>');
	return `<div data-object="smartart" style="display:flex;gap:4px;padding:10px;border:1px solid #ddd;border-radius:4px;margin:8px 0">${items}</div>`;
}

/** A display equation built from an inline LaTeX-ish subset. */
export function equation(latex: string): string {
	return `<div data-object="equation" contenteditable="false" style="text-align:center;margin:8px 0;font-family:'Cambria Math',serif;font-size:14pt">${renderMath(
		latex
	)}</div><p><br/></p>`;
}

/**
 * Minimal LaTeX-ish → HTML renderer for the equation gallery: fractions,
 * superscripts, subscripts and radicals. Enough for the ready-made samples.
 */
export function renderMath(src: string): string {
	let out = esc(src);
	out = out.replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, (_m, a, b) => fraction(a, b));
	out = out.replace(/\\sqrt\{([^}]*)\}/g, (_m, a) => `√(${a})`);
	out = out.replace(/\^\{([^}]*)\}/g, (_m, a) => `<sup>${a}</sup>`);
	out = out.replace(/\^(\w)/g, (_m, a) => `<sup>${a}</sup>`);
	out = out.replace(/_\{([^}]*)\}/g, (_m, a) => `<sub>${a}</sub>`);
	out = out.replace(/_(\w)/g, (_m, a) => `<sub>${a}</sub>`);
	out = out.replace(/\\alpha/g, 'α').replace(/\\beta/g, 'β').replace(/\\pi/g, 'π').replace(/\\times/g, '×');
	out = out.replace(/\\pm/g, '±').replace(/\\le/g, '≤').replace(/\\ge/g, '≥').replace(/\\cdot/g, '·');
	out = out.replace(/\\sum/g, '∑').replace(/\\int/g, '∫').replace(/\\infty/g, '∞');
	return out;
}

function fraction(a: string, b: string): string {
	return `<span style="display:inline-block;vertical-align:middle;text-align:center;margin:0 .15em">
      <span style="display:block;border-bottom:1px solid currentColor;padding:0 .2em">${a}</span>
      <span style="display:block">${b}</span>
    </span>`;
}

/** Characters that WordPress / Word put on the Symbols menu. */
export const SYMBOL_SETS: Record<string, string[]> = {
	Umum: ['©', '®', '™', '§', '¶', '†', '‡', '•', '–', '—', '…', '′', '″', '·'],
	Matematika: ['±', '×', '÷', '≈', '≠', '≤', '≥', '∞', '∑', '∏', '∫', '√', '∂', 'µ', 'π', '°'],
	Panah: ['←', '→', '↑', '↓', '↔', '⇒', '⇐', '⇔', '↦', '⟶', '↩', '↪'],
	MataUang: ['$', '€', '£', '¥', '₩', '₹', '₽', '₺', '₴', '฿', 'Rp', '¢'],
	Yunani: ['α', 'β', 'γ', 'δ', 'ε', 'θ', 'λ', 'μ', 'ρ', 'σ', 'τ', 'φ', 'ω', 'Ω'],
	Bentuk: ['★', '☆', '♥', '♦', '♣', '♠', '✓', '✗', '☑', '☐', '◉', '●', '■', '▲'],
};

export const NONBREAKING = {
	/** Non-breaking space (U+00A0). */
	nbsp: '\u00A0',
	/** Non-breaking hyphen (U+2011). */
	nbHyphen: '\u2011',
	/** Optional (soft) hyphen (U+00AD). */
	optionalHyphen: '\u00AD',
};

export const EQUATION_PRESETS: { label: string; latex: string }[] = [
	{ label: 'Kuadrat', latex: 'ax^2 + bx + c = 0' },
	{ label: 'Pecahan', latex: '\\frac{a+b}{c}' },
	{ label: 'Akar', latex: '\\sqrt{x^2 + y^2}' },
	{ label: 'Jumlah', latex: '\\sum_{i=1}^{n} x_i' },
	{ label: 'Integral', latex: '\\int_{a}^{b} f(x) dx' },
	{ label: 'Limit', latex: '\\lim_{x \\to 0} \\frac{1}{x}' },
	{ label: 'Rumus Lingkaran', latex: 'A = \\pi r^2' },
	{ label: 'Turunan', latex: '\\frac{dy}{dx} = f(x)' },
];
