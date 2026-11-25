import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { History, Info, Play } from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader, PriorityBadge, StatCard } from '../components/UI';

export default function RetentionPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getRetention();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load retention tracker');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <LoadingState label="Evaluating competency retention intervals..." />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Retention Tracker"
        subtitle="Tracks observed performance trends over time and prioritizes spaced retrieval practice."
        actions={
          <button
            onClick={() => navigate('/assessments')}
            className="gov-btn-primary px-4 py-2 text-xs"
          >
            <Play className="w-3.5 h-3.5" /> Start Retrieval Check
          </button>
        }
      />

      <div className="gov-card p-4 bg-gp-primary-light/50 border-gp-primary-border flex items-start gap-3 text-xs text-gp-ink-secondary">
        <Info className="w-4 h-4 text-gp-primary shrink-0 mt-0.5" />
        <span>{data.methodology_note}</span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Revision Overdue" value={data.summary.overdue_count} accent="error" icon={<History className="w-5 h-5" />} />
        <StatCard label="Due Soon" value={data.summary.due_soon_count} accent="warning" />
        <StatCard label="Retained" value={data.summary.retained_count} accent="success" />
        <StatCard label="Baseline Needed" value={data.summary.baseline_needed_count} accent="neutral" />
      </div>

      <div className="gov-card p-5">
        <h2 className="text-base font-bold text-gp-ink mb-3">Competency Revision Schedule</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-gp-bg text-gp-ink-secondary border-b border-gp-border">
              <tr>
                <th className="py-2.5 px-3">Competency</th>
                <th className="py-2.5 px-3">Last Assessed</th>
                <th className="py-2.5 px-3">Previous</th>
                <th className="py-2.5 px-3">Current</th>
                <th className="py-2.5 px-3">Observed Trend</th>
                <th className="py-2.5 px-3">Next Revision</th>
                <th className="py-2.5 px-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gp-divider">
              {data.items.map((item: any) => (
                <tr key={item.competency_id} className="hover:bg-gp-bg">
                  <td className="py-2.5 px-3">
                    <div className="font-semibold text-gp-ink">{item.competency_name}</div>
                    <div className="text-[11px] text-gp-ink-muted">{item.subject_name}</div>
                  </td>
                  <td className="py-2.5 px-3 font-mono text-gp-ink-secondary">
                    {item.last_assessed_date ? `${item.last_assessed_date} (${item.days_since_assessed}d ago)` : 'Never'}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-gp-ink">
                    {item.previous_performance !== null ? `${item.previous_performance}%` : '—'}
                  </td>
                  <td className="py-2.5 px-3 font-mono font-bold text-gp-primary">{item.current_estimate}%</td>
                  <td className="py-2.5 px-3 text-gp-ink-secondary">{item.retention_trend}</td>
                  <td className="py-2.5 px-3 font-mono text-gp-ink-secondary">{item.upcoming_revision_date}</td>
                  <td className="py-2.5 px-3"><PriorityBadge priority={item.revision_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
