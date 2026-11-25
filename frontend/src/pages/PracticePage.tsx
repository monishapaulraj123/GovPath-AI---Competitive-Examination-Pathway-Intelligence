import React, { useEffect, useState } from 'react';
import { Bookmark, CheckCircle2, XCircle } from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader } from '../components/UI';

export default function PracticePage() {
  const [mode, setMode] = useState('all');
  const [subjectId, setSubjectId] = useState('ALL');
  const [questions, setQuestions] = useState<any[]>([]);
  const [revealed, setRevealed] = useState<Record<string, number | null>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.listPracticeQuestions(mode, subjectId);
      setQuestions(res.questions || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load practice bank');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [mode, subjectId]);

  const handleSave = async (qid: string) => {
    const res = await api.toggleSaveQuestion(qid);
    setQuestions((prev) => prev.map((q) => (q.id === qid ? { ...q, is_saved: res.saved } : q)));
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Practice & Revision"
        subtitle="Targeted topic drills, weak-competency practice, incorrect-question reattempts, and saved question bank."
      />

      {/* Mode & Subject Filters */}
      <div className="gov-card p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {[
            { id: 'all', label: 'All Curated Questions' },
            { id: 'weak', label: 'Weak Competencies' },
            { id: 'incorrect', label: 'Incorrect Reattempts' },
            { id: 'saved', label: 'Saved Questions' },
          ].map((m) => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                mode === m.id
                  ? 'bg-gp-primary text-white border-gp-primary'
                  : 'bg-gp-surface text-gp-ink-secondary border-gp-border hover:border-gp-primary-border hover:text-gp-primary'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        <select
          value={subjectId}
          onChange={(e) => setSubjectId(e.target.value)}
          className="gov-input px-3 py-1.5 text-xs font-semibold"
        >
          <option value="ALL">All Subjects</option>
          <option value="POLITY">Indian Polity</option>
          <option value="ECONOMY">Indian Economy</option>
          <option value="HISTORY">History & Culture</option>
          <option value="GEOGRAPHY">Geography & Environment</option>
          <option value="SCIENCE_TECH">Science & Tech</option>
          <option value="CURRENT_AFFAIRS">Current Affairs</option>
          <option value="QUANT">Quantitative Aptitude</option>
          <option value="REASONING">Reasoning</option>
          <option value="ENGLISH">English</option>
          <option value="STATE_TN">TN Heritage & Admin</option>
        </select>
      </div>

      {loading && <LoadingState label="Loading practice questions..." />}
      {error && <ErrorBanner message={error} />}

      {!loading && questions.length === 0 && (
        <div className="gov-card p-10 text-center text-sm text-gp-ink-secondary">
          No questions found for this filter. Try switching mode or saving questions during practice.
        </div>
      )}

      <div className="space-y-4">
        {questions.map((q, idx) => {
          const picked = revealed[q.id];
          const answered = picked !== undefined;
          return (
            <div key={q.id} className="gov-card p-5 space-y-3">
              <div className="flex items-center justify-between gap-2 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-bold text-gp-ink-muted">#{idx + 1}</span>
                  <span className="px-2 py-0.5 rounded bg-gp-primary-light text-gp-primary border border-gp-primary-border font-semibold">
                    {q.subject_name} · {q.topic_name}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-gp-bg border border-gp-border text-gp-ink-secondary capitalize">
                    {q.difficulty}
                  </span>
                  {q.previously_missed && (
                    <span className="px-2 py-0.5 rounded bg-gp-error-bg text-gp-error font-semibold">
                      Previously Missed
                    </span>
                  )}
                </div>
                <button
                  onClick={() => handleSave(q.id)}
                  className={`p-1.5 rounded-lg border transition ${
                    q.is_saved
                      ? 'bg-gp-warning-bg border-gp-warning/30 text-gp-warning'
                      : 'bg-gp-surface border-gp-border text-gp-ink-muted hover:text-gp-primary'
                  }`}
                  title="Bookmark question"
                >
                  <Bookmark className="w-4 h-4" />
                </button>
              </div>

              <p className="text-sm font-medium text-gp-ink whitespace-pre-line">{q.prompt}</p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {q.options.map((opt: string, optIdx: number) => {
                  const isCorrect = optIdx === q.correct_index;
                  const isPicked = picked === optIdx;
                  let cls = 'border-gp-border bg-gp-surface hover:border-gp-primary-border text-gp-ink-secondary';
                  if (answered) {
                    if (isCorrect) cls = 'border-gp-success/40 bg-gp-success-bg text-gp-success font-semibold';
                    else if (isPicked) cls = 'border-gp-error/40 bg-gp-error-bg text-gp-error';
                  }
                  return (
                    <button
                      key={optIdx}
                      onClick={() => setRevealed((prev) => ({ ...prev, [q.id]: optIdx }))}
                      className={`p-3 rounded-lg border text-left text-xs flex items-center justify-between gap-2 transition ${cls}`}
                    >
                      <span>{String.fromCharCode(65 + optIdx)}. {opt}</span>
                      {answered && isCorrect && <CheckCircle2 className="w-4 h-4 text-gp-success shrink-0" />}
                      {answered && isPicked && !isCorrect && <XCircle className="w-4 h-4 text-gp-error shrink-0" />}
                    </button>
                  );
                })}
              </div>

              {answered && (
                <div className="p-3 rounded-lg bg-gp-bg border border-gp-border text-xs text-gp-ink-secondary">
                  <strong className="text-gp-ink">Explanation ({q.competency_name}): </strong>
                  {q.explanation}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
