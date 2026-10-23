<script lang="ts">
  /**
   * ReviewPane — the right-hand dock for Word's Review tools:
   *   • Comments  — every comment thread with jump / resolve / delete,
   *   • Spelling  — flagged words with suggestions,
   *   • Thesaurus — synonyms for the selected word,
   *   • Inspect   — accessibility and document-inspector findings,
   *   • Word count — the full statistics dialog.
   */
  import { X, MessageSquare, SpellCheck, BookOpen, ShieldCheck, Tally5, Check } from 'lucide-svelte';
  import type { Comment, SpellingIssue, InspectionFinding } from './review';
  import type { WordCount } from './review';
  import { formatNumber } from './dates';

  export type ReviewTab = 'comments' | 'spelling' | 'thesaurus' | 'inspect' | 'wordcount';

  interface Props {
    tab: ReviewTab;
    comments: Comment[];
    spelling: SpellingIssue[];
    inspector: InspectionFinding[];
    counts: WordCount;
    thesaurusWord: string;
    synonyms: string[];
    ontab: (t: ReviewTab) => void;
    onjumpcomment: (id: string) => void;
    onresolve: (id: string) => void;
    ondelete: (id: string) => void;
    onreplacespelling: (word: string, withWord: string) => void;
    onapplysynonym: (word: string) => void;
    onexit: () => void;
  }
  let {
    tab,
    comments,
    spelling,
    inspector,
    counts,
    thesaurusWord,
    synonyms,
    ontab,
    onjumpcomment,
    onresolve,
    ondelete,
    onreplacespelling,
    onapplysynonym,
    onexit,
  }: Props = $props();

  const tabs: { key: ReviewTab; icon: typeof X; label: string }[] = [
    { key: 'comments', icon: MessageSquare, label: 'Komentar' },
    { key: 'spelling', icon: SpellCheck, label: 'Ejaan' },
    { key: 'thesaurus', icon: BookOpen, label: 'Tesisaurus' },
    { key: 'inspect', icon: ShieldCheck, label: 'Inspeksi' },
    { key: 'wordcount', icon: Tally5, label: 'Statistik' },
  ];
</script>

<aside class="w-72 shrink-0 border-l border-[var(--border-color)] bg-[var(--bg-surface)] flex flex-col" aria-label="Panel tinjauan">
  <div class="flex items-center justify-between px-2 py-1.5 border-b border-[var(--border-color)]">
    <div class="flex items-center gap-0.5">
      {#each tabs as t}
        <button
          type="button"
          title={t.label}
          onclick={() => ontab(t.key)}
          class="p-1.5 rounded-sm transition-colors
            {tab === t.key ? 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}"
        >
          <t.icon class="w-3.5 h-3.5" />
        </button>
      {/each}
    </div>
    <button type="button" onclick={onexit} class="text-[var(--text-muted)] hover:text-[var(--text-primary)]" aria-label="Tutup panel tinjauan">
      <X class="w-3.5 h-3.5" />
    </button>
  </div>

  <div class="overflow-y-auto flex-1 p-2">
    {#if tab === 'comments'}
      {#if comments.length === 0}
        <p class="text-[10px] font-code text-[var(--text-muted)] px-1 py-2">
          Belum ada komentar. Pilih teks lalu klik "Komentar Baru" di tab Review.
        </p>
      {:else}
        <div class="space-y-2">
          {#each comments as c}
            <div class="border border-[var(--border-color)] rounded-sm p-2" style:border-left-color={c.color} style:border-left-width="3px">
              <div class="flex items-center justify-between mb-1">
                <span class="text-[10px] font-code text-[var(--accent-primary)]">{c.author}</span>
                <div class="flex items-center gap-1">
                  <button type="button" title="Selesaikan" onclick={() => onresolve(c.id)} class="text-[var(--status-success)] hover:opacity-70">
                    <Check class="w-3 h-3" />
                  </button>
                  <button type="button" title="Hapus" onclick={() => ondelete(c.id)} class="text-[var(--status-danger)] hover:opacity-70">
                    <X class="w-3 h-3" />
                  </button>
                </div>
              </div>
              <button type="button" onclick={() => onjumpcomment(c.id)} class="text-left text-[11px] text-[var(--text-primary)] hover:underline">
                {c.text}
              </button>
            </div>
          {/each}
        </div>
      {/if}
    {:else if tab === 'spelling'}
      {#if spelling.length === 0}
        <p class="text-[10px] font-code text-[var(--status-success)] px-1 py-2">Tidak ada kata yang ditandai.</p>
      {:else}
        <div class="space-y-2">
          {#each spelling as issue}
            <div class="border border-[var(--border-color)] rounded-sm p-2">
              <div class="text-[11px] font-code text-[var(--status-warning)] mb-1">{issue.word}</div>
              {#if issue.suggestions.length === 0}
                <p class="text-[10px] text-[var(--text-muted)]">Tidak ada saran.</p>
              {:else}
                <div class="flex flex-wrap gap-1">
                  {#each issue.suggestions as s}
                    <button
                      type="button"
                      onclick={() => onreplacespelling(issue.word, s)}
                      class="px-1.5 py-0.5 text-[10px] font-code border border-[var(--border-color)] rounded-sm hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]"
                    >
                      {s}
                    </button>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    {:else if tab === 'thesaurus'}
      <p class="text-[10px] font-code text-[var(--text-muted)] px-1 mb-2">
        Kata terpilih: <span class="text-[var(--text-primary)]">{thesaurusWord || '—'}</span>
      </p>
      {#if synonyms.length === 0}
        <p class="text-[10px] text-[var(--text-muted)] px-1">Tidak ada sinonim ditemukan untuk kata ini.</p>
      {:else}
        <div class="flex flex-wrap gap-1">
          {#each synonyms as s}
            <button
              type="button"
              onclick={() => onapplysynonym(s)}
              class="px-2 py-1 text-[11px] border border-[var(--border-color)] rounded-sm hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]"
            >
              {s}
            </button>
          {/each}
        </div>
      {/if}
    {:else if tab === 'inspect'}
      {#if inspector.length === 0}
        <p class="text-[10px] font-code text-[var(--status-success)] px-1 py-2">Tidak ada temuan. Dokumen bersih.</p>
      {:else}
        <ul class="space-y-1.5">
          {#each inspector as f}
            <li class="flex items-start gap-1.5 text-[11px]">
              <span
                class="mt-1 w-1.5 h-1.5 rounded-full shrink-0"
                style:background={f.level === 'error' ? 'var(--status-danger)' : f.level === 'warning' ? 'var(--status-warning)' : 'var(--accent-primary)'}
              ></span>
              <span class="text-[var(--text-primary)]">{f.message}</span>
            </li>
          {/each}
        </ul>
      {/if}
    {:else}
      <table class="w-full text-[11px]">
        <tbody>
          {#each [
            ['Kata', counts.words],
            ['Karakter', counts.characters],
            ['Karakter (tanpa spasi)', counts.charactersNoSpaces],
            ['Paragraf', counts.paragraphs],
            ['Baris', counts.lines],
            ['Perkiraan halaman', counts.pages],
          ] as [label, value]}
            <tr class="border-b border-[var(--border-color)]/40">
              <td class="py-1 text-[var(--text-muted)]">{label}</td>
              <td class="py-1 text-right font-code text-[var(--text-primary)]">{formatNumber(Number(value))}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</aside>
