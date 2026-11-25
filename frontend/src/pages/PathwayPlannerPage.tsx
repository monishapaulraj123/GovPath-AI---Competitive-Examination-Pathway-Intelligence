import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Route } from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader } from '../components/UI';

export default function PathwayPlannerPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getPathways();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to compute career pathways');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const setAsPrimary = async (examId: string) => {
    setUpdatingId(examId);
    try {
      await api.updateProfile({ primary_target_exam: examId });
      await load();
    } finally {
      setUpdatingId(null);
    }
  };

  if (loading) return <LoadingState label="Ranking optimal examination pathways..." />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Pathway Planner"
        subtitle="Multi-criteria examination pathway optimization based on readiness alignment, cross-exam knowledge transfer, and daily time constraints."
      />

      {/* Constraints Summary */}
      <div className="gov-card p-4 bg-gp-bg flex flex-wrap items-center justify-between gap-4 text-xs text-gp-ink-secondary">
        <div className="flex flex-wrap gap-4">
          <span>
            <strong className="text-gp-ink">Primary Target:</strong> {data.primary_exam_id.replace('_', ' ')}
          </span>
          <span>
            <strong className="text-gp-ink">Availability:</strong> {data.student_constraints.daily_study_hours}h/day ×{' '}
            {data.student_constraints.days_per_week} days/week
          </span>
          <span>
            <strong className="text-gp-ink">Timeline:</strong> {data.student_constraints.timeline_months} months
          </span>
          {data.student_constraints.state && (
            <span>
              <strong className="text-gp-ink">State:</strong> {data.student_constraints.state}
            </span>
          )}
        </div>
        <button
          onClick={() => navigate('/profile')}
          className="text-gp-primary font-semibold hover:underline"
        >
          Edit Constraints
        </button>
      </div>

      {/* Ranked Pathways */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {data.pathways.map((p: any) => {
          const isPrimary = p.role === 'Primary Target';
          return (
            <div
              key={p.exam_id}
              className={`gov-card p-5 space-y-4 ${
                isPrimary ? 'bg-gp-primary-soft/30 border-gp-primary' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-gp-primary-light text-gp-primary border border-gp-primary-border mb-1.5">
                    <Route className="w-3 h-3" /> {p.role}
                  </span>
                  <h3 className="text-base font-bold text-gp-ink">{p.exam_name}</h3>
                  <p className="text-xs text-gp-ink-muted">{p.category}</p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-gp-primary">{p.suitability_score}</div>
                  <div className="text-[10px] uppercase font-semibold text-gp-ink-muted">Fit Score</div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="p-2.5 rounded-lg bg-gp-bg border border-gp-border">
                  <div className="text-[11px] text-gp-ink-secondary">Readiness</div>
                  <div className="text-sm font-bold text-gp-ink">{p.readiness_index}%</div>
                </div>
                <div className="p-2.5 rounded-lg bg-gp-success-bg border border-gp-success/20">
                  <div className="text-[11px] text-gp-success">Transfer</div>
                  <div className="text-sm font-bold text-gp-success">{p.transfer_from_primary_percent}%</div>
                </div>
                <div className="p-2.5 rounded-lg bg-gp-warning-bg border border-gp-warning/20">
                  <div className="text-[11px] text-gp-warning">Est. Bridge</div>
                  <div className="text-sm font-bold text-gp-warning">~{p.estimated_additional_hours}h</div>
                </div>
              </div>

              <p className="text-xs text-gp-ink-secondary leading-relaxed">{p.rationale}</p>

              <div className="pt-3 border-t border-gp-divider flex flex-wrap items-center justify-between gap-2">
                {p.exam_id === data.primary_exam_id ? (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-gp-success">
                    <CheckCircle2 className="w-4 h-4" /> Active Primary Target
                  </span>
                ) : (
                  <button
                    onClick={() => setAsPrimary(p.exam_id)}
                    disabled={updatingId === p.exam_id}
                    className="gov-btn-secondary px-3 py-1.5 text-xs"
                  >
                    {updatingId === p.exam_id ? 'Updating...' : 'Set as Primary Target'}
                  </button>
                )}

                <button
                  onClick={() => navigate(`/knowledge-transfer`)}
                  className="text-xs font-semibold text-gp-primary hover:underline inline-flex items-center gap-1"
                >
                  Inspect Transfer <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
