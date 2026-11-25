import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { api } from '../api/client';
import { DemoDataBanner, ErrorBanner, LoadingState, PageHeader, StatCard } from '../components/UI';

export default function ErrorAnalysisPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getDiagnosis();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load performance diagnosis');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <LoadingState label="Running rule-based error diagnosis engine..." />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Error Analysis & Diagnosis"
        subtitle="Rule-based diagnostic classification of mistakes, timing overruns, difficulty patterns, and repeated competency errors."
      />

      <DemoDataBanner show={data.has_only_demo_data} />

      {!data.has_data ? (
        <div className="gov-card p-10 text-center text-sm text-gp-ink-secondary">
          {data.recommendations?.[0]}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total Mistakes Analyzed" value={data.total_mistakes} subtext={`Across ${data.total_questions_answered} responses`} accent="error" icon={<AlertTriangle className="w-5 h-5" />} />
            {(['easy', 'medium', 'hard'] as const).map((diff) => (
              <StatCard
                key={diff}
                label={`${diff.toUpperCase()} Accuracy`}
                value={`${data.difficulty_performance?.[diff]?.accuracy_percent ?? 0}%`}
                subtext={`${data.difficulty_performance?.[diff]?.correct ?? 0}/${data.difficulty_performance?.[diff]?.total ?? 0} correct`}
                accent={diff === 'easy' ? 'success' : diff === 'medium' ? 'primary' : 'warning'}
              />
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Error Categories */}
            <div className="gov-card p-5">
              <h2 className="text-base font-bold text-gp-ink mb-3">Diagnostic Error Categories</h2>
              <div className="space-y-2.5">
                {Object.entries(data.error_category_breakdown || {}).map(([cat, count]: any) => (
                  <div key={cat} className="p-3 rounded-lg bg-gp-bg border border-gp-border flex items-center justify-between">
                    <span className="text-sm font-semibold text-gp-ink">{cat}</span>
                    <span className="px-2.5 py-0.5 rounded-full bg-gp-error-bg text-gp-error font-mono text-xs font-bold">
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Corrective Recommendations */}
            <div className="gov-card p-5">
              <h2 className="text-base font-bold text-gp-ink mb-3">Evidence-Grounded Corrective Actions</h2>
              <div className="space-y-2.5">
                {data.recommendations.map((rec: string, i: number) => (
                  <div key={i} className="p-3 rounded-lg bg-gp-primary-light/60 border border-gp-primary-border flex items-start gap-2.5 text-xs text-gp-ink">
                    <CheckCircle2 className="w-4 h-4 text-gp-primary shrink-0 mt-0.5" />
                    <span>{rec}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Detailed Mistake Log */}
          <div className="gov-card p-5 space-y-4">
            <h2 className="text-base font-bold text-gp-ink">Detailed Mistake & Explanation Log</h2>
            {data.detailed_mistakes.map((m: any) => (
              <div key={m.answer_id} className="p-4 rounded-xl border border-gp-border bg-gp-surface space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span className="font-bold text-gp-ink">
                    {m.competency_name} ({m.subject_name})
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-gp-error-bg text-gp-error font-semibold border border-gp-error/20">
                      {m.error_category}
                    </span>
                    <span className="font-mono text-gp-ink-muted">
                      {m.time_spent_sec}s (exp {m.expected_time_sec}s)
                    </span>
                  </div>
                </div>
                <p className="text-xs sm:text-sm text-gp-ink whitespace-pre-line">{m.question_prompt}</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  <div className="p-2 rounded bg-gp-error-bg text-gp-error">
                    <strong>Your Answer:</strong> {m.selected_text}
                  </div>
                  <div className="p-2 rounded bg-gp-success-bg text-gp-success">
                    <strong>Correct Answer:</strong> {m.correct_text}
                  </div>
                </div>
                <p className="text-xs text-gp-ink-secondary bg-gp-bg p-2.5 rounded-lg border border-gp-divider">
                  {m.explanation}
                </p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
