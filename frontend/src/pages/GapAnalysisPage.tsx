import React, { useEffect, useState } from 'react';
import { RefreshCw, Target } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api/client';
import { DemoDataBanner, ErrorBanner, LoadingState, PageHeader, PriorityBadge, StatCard } from '../components/UI';
import { GOVPATH_COLORS } from '../theme/colors';

const EXAM_LIST = [
  { id: 'UPSC_CSE', label: 'UPSC CSE' },
  { id: 'TNPSC_GRP1', label: 'TNPSC Group I' },
  { id: 'TNPSC_GRP2', label: 'TNPSC Group II/IIA' },
  { id: 'SSC_CGL', label: 'SSC CGL' },
  { id: 'SSC_CHSL', label: 'SSC CHSL' },
  { id: 'IBPS_PO', label: 'IBPS PO' },
  { id: 'RRB_NTPC', label: 'RRB NTPC' },
  { id: 'UPSC_CDS', label: 'UPSC CDS' },
];

export default function GapAnalysisPage() {
  const [examId, setExamId] = useState('');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async (target?: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getGapAnalysis(target || undefined);
      setData(res);
      if (!target) setExamId(res.exam_id);
    } catch (err: any) {
      setError(err.message || 'Gap calculation failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <LoadingState label="Running backend Gap Analysis Engine..." />;
  if (error) return <ErrorBanner message={error} onRetry={() => load(examId)} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Gap Analysis Engine"
        subtitle="Deterministic comparison of target examination competency requirements against demonstrated student evidence."
        actions={
          <div className="flex items-center gap-2">
            <select
              value={examId}
              onChange={(e) => {
                setExamId(e.target.value);
                load(e.target.value);
              }}
              className="gov-input px-3 py-2 text-xs font-semibold"
            >
              {EXAM_LIST.map((ex) => (
                <option key={ex.id} value={ex.id}>
                  {ex.label}
                </option>
              ))}
            </select>
            <button
              onClick={() => load(examId)}
              className="gov-btn-primary px-3 py-2 text-xs"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Recalculate
            </button>
          </div>
        }
      />

      <DemoDataBanner show={data.has_only_demo_data} />

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard label="Overall Weighted Gap" value={`${data.overall_weighted_gap} pts`} icon={<Target className="w-5 h-5" />} accent="error" />
        <StatCard label="Critical Gaps" value={data.priority_counts?.Critical ?? 0} accent="error" />
        <StatCard label="High Priority" value={data.priority_counts?.High ?? 0} accent="warning" />
        <StatCard label="Moderate" value={data.priority_counts?.Moderate ?? 0} accent="primary" />
        <StatCard label="On Track / Low" value={(data.priority_counts?.Low ?? 0) + (data.priority_counts?.['On Track'] ?? 0)} accent="success" />
      </div>

      {/* Subject Gap BarChart */}
      <div className="gov-card p-5">
        <h2 className="text-base font-bold text-gp-ink mb-4">Subject-Level Average Competency Gap</h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.subject_gaps}>
              <CartesianGrid strokeDasharray="3 3" stroke={GOVPATH_COLORS.border} />
              <XAxis dataKey="subject_id" tick={{ fontSize: 11, fill: GOVPATH_COLORS.textSecondary }} />
              <YAxis tick={{ fontSize: 11, fill: GOVPATH_COLORS.textSecondary }} />
              <Tooltip />
              <Bar dataKey="avg_gap" name="Average Gap (pts)" fill={GOVPATH_COLORS.primary} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Detailed Competency Gap Matrix */}
      <div className="gov-card p-5">
        <h2 className="text-base font-bold text-gp-ink mb-3">Competency-Level Gap & Interventions ({data.exam_short_name})</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-gp-bg text-gp-ink-secondary border-b border-gp-border">
              <tr>
                <th className="py-2.5 px-3">Competency</th>
                <th className="py-2.5 px-3">Subject</th>
                <th className="py-2.5 px-3">Required</th>
                <th className="py-2.5 px-3">Evidence</th>
                <th className="py-2.5 px-3">Gap</th>
                <th className="py-2.5 px-3">Priority</th>
                <th className="py-2.5 px-3">Recommended Intervention</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gp-divider">
              {data.competency_gaps.map((g: any) => (
                <tr key={g.competency_id} className="hover:bg-gp-bg">
                  <td className="py-2.5 px-3 font-semibold text-gp-ink">{g.competency_name}</td>
                  <td className="py-2.5 px-3 text-gp-ink-secondary">{g.subject_name}</td>
                  <td className="py-2.5 px-3 font-mono text-gp-ink">{g.required_level}</td>
                  <td className="py-2.5 px-3 font-mono text-gp-primary">{g.current_evidence}</td>
                  <td className="py-2.5 px-3 font-mono font-bold text-gp-error">{g.gap}</td>
                  <td className="py-2.5 px-3"><PriorityBadge priority={g.priority} /></td>
                  <td className="py-2.5 px-3 text-gp-ink-secondary max-w-xs">{g.recommended_intervention}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
