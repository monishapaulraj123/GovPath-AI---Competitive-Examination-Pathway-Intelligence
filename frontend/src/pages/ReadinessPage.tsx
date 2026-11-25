import React, { useEffect, useState } from 'react';
import { Info, ShieldCheck } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api/client';
import { DemoDataBanner, ErrorBanner, LoadingState, PageHeader, StatCard } from '../components/UI';
import { GOVPATH_CHART_PALETTE, GOVPATH_COLORS } from '../theme/colors';

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

export default function ReadinessPage() {
  const [examId, setExamId] = useState<string>('');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async (target?: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getReadiness(target || undefined);
      setData(res);
      if (!target) setExamId(res.exam_id);
    } catch (err: any) {
      setError(err.message || 'Failed to compute readiness profile');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <LoadingState label="Aggregating weighted competency evidence..." />;
  if (error) return <ErrorBanner message={error} onRetry={() => load(examId)} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Student Readiness Profile"
        subtitle="Evidence-weighted competency alignment across diagnostic, mock, topic quiz, and revision observations."
        actions={
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
                Target: {ex.label}
              </option>
            ))}
          </select>
        }
      />

      <DemoDataBanner show={data.has_only_demo_data} />

      {/* Methodology Note */}
      <div className="gov-card p-4 bg-gp-primary-light/50 border-gp-primary-border flex items-start gap-3 text-xs text-gp-ink-secondary">
        <Info className="w-4 h-4 text-gp-primary shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-gp-ink">Explainable Readiness Methodology: </span>
          {data.methodology?.description} Evidence weights: Mock Test (1.35×), Diagnostic (1.15×), Subject Test (1.10×),
          Topic Quiz (1.0×), Revision (0.85×), with 21-day exponential recency decay and confidence scaling.
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard label="Readiness Alignment" value={`${data.readiness_index}%`} icon={<ShieldCheck className="w-5 h-5" />} accent="primary" />
        <StatCard label="Competency Coverage" value={`${data.competency_coverage}%`} accent="primary" />
        <StatCard label="Accuracy" value={`${data.accuracy}%`} accent="success" />
        <StatCard label="Retention Index" value={`${data.retention_index}%`} accent="warning" />
        <StatCard label="Consistency" value={`${data.consistency}%`} accent="primary" />
      </div>

      {/* Subject Comparison Chart */}
      <div className="gov-card p-5">
        <h2 className="text-base font-bold text-gp-ink mb-4">Subject Mastery vs Required Exam Depth</h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.subject_breakdown}>
              <CartesianGrid strokeDasharray="3 3" stroke={GOVPATH_COLORS.border} />
              <XAxis dataKey="subject_id" tick={{ fontSize: 11, fill: GOVPATH_COLORS.textSecondary }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: GOVPATH_COLORS.textSecondary }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="demonstrated_score" name="Demonstrated Mastery" fill={GOVPATH_CHART_PALETTE[0]} radius={[4, 4, 0, 0]} />
              <Bar dataKey="required_depth" name="Target Required Depth" fill={GOVPATH_CHART_PALETTE[4]} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Competency Evidence Table */}
      <div className="gov-card p-5">
        <h2 className="text-base font-bold text-gp-ink mb-3">Granular Competency Evidence Ledger</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-gp-bg text-gp-ink-secondary border-b border-gp-border">
              <tr>
                <th className="py-2.5 px-3">Competency</th>
                <th className="py-2.5 px-3">Subject</th>
                <th className="py-2.5 px-3">Mastery</th>
                <th className="py-2.5 px-3">Accuracy</th>
                <th className="py-2.5 px-3">Speed Eff.</th>
                <th className="py-2.5 px-3">Confidence</th>
                <th className="py-2.5 px-3">Observations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gp-divider">
              {data.competencies.map((c: any) => (
                <tr key={c.competency_id} className="hover:bg-gp-bg">
                  <td className="py-2.5 px-3 font-semibold text-gp-ink">{c.name}</td>
                  <td className="py-2.5 px-3 text-gp-ink-secondary">{c.subject_name}</td>
                  <td className="py-2.5 px-3 font-mono font-bold text-gp-primary">{c.mastery_score}</td>
                  <td className="py-2.5 px-3 font-mono text-gp-ink">{c.accuracy}%</td>
                  <td className="py-2.5 px-3 font-mono text-gp-ink">{c.speed_efficiency}%</td>
                  <td className="py-2.5 px-3 font-mono text-gp-ink">{c.confidence}%</td>
                  <td className="py-2.5 px-3 font-mono text-gp-ink">{c.evidence_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
