import React, { useEffect, useState } from 'react';
import { BarChart3 } from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/client';
import { DemoDataBanner, ErrorBanner, LoadingState, PageHeader, StatCard } from '../components/UI';
import { GOVPATH_CHART_PALETTE, GOVPATH_COLORS } from '../theme/colors';

export default function AnalyticsPage() {
  const [examId, setExamId] = useState('');
  const [subjectId, setSubjectId] = useState('ALL');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async (ex = examId, sub = subjectId) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getAnalytics(ex || undefined, sub);
      setData(res);
      if (!ex) setExamId(res.exam_id);
    } catch (err: any) {
      setError(err.message || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <LoadingState label="Aggregating performance analytics..." />;
  if (error) return <ErrorBanner message={error} onRetry={() => load()} />;
  if (!data) return null;

  const k = data.summary_kpis;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Performance Analytics"
        subtitle="Assessment score trajectories, competency growth trends, study execution hours, and accuracy analytics."
        actions={
          <div className="flex gap-2">
            <select
              value={examId}
              onChange={(e) => {
                setExamId(e.target.value);
                load(e.target.value, subjectId);
              }}
              className="gov-input px-3 py-2 text-xs font-semibold"
            >
              <option value="UPSC_CSE">UPSC CSE</option>
              <option value="TNPSC_GRP1">TNPSC Group I</option>
              <option value="TNPSC_GRP2">TNPSC Group II/IIA</option>
              <option value="SSC_CGL">SSC CGL</option>
              <option value="SSC_CHSL">SSC CHSL</option>
              <option value="IBPS_PO">IBPS PO</option>
              <option value="RRB_NTPC">RRB NTPC</option>
              <option value="UPSC_CDS">UPSC CDS</option>
            </select>
            <select
              value={subjectId}
              onChange={(e) => {
                setSubjectId(e.target.value);
                load(examId, e.target.value);
              }}
              className="gov-input px-3 py-2 text-xs font-semibold"
            >
              <option value="ALL">All Subjects</option>
              <option value="POLITY">Polity</option>
              <option value="ECONOMY">Economy</option>
              <option value="HISTORY">History</option>
              <option value="GEOGRAPHY">Geography</option>
              <option value="CURRENT_AFFAIRS">Current Affairs</option>
              <option value="QUANT">Quant</option>
              <option value="STATE_TN">TN Heritage</option>
            </select>
          </div>
        }
      />

      <DemoDataBanner show={data.has_only_demo_data} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Readiness Index" value={`${k.readiness_index}%`} icon={<BarChart3 className="w-5 h-5" />} accent="primary" />
        <StatCard label="Overall Accuracy" value={`${k.accuracy}%`} accent="success" />
        <StatCard label="Completed Study Hours" value={`${k.completed_study_hours}h`} subtext={`of ${k.planned_study_hours}h planned`} accent="primary" />
        <StatCard label="Revision Completion" value={`${k.revision_completion_percent}%`} accent="warning" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="gov-card p-5">
          <h2 className="text-base font-bold text-gp-ink mb-4">Assessment Score & Accuracy Trend</h2>
          {data.attempt_trends.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.attempt_trends}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GOVPATH_COLORS.border} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: GOVPATH_COLORS.textSecondary }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: GOVPATH_COLORS.textSecondary }} />
                  <Tooltip />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="score_percent"
                    name="Score %"
                    stroke={GOVPATH_CHART_PALETTE[0]}
                    fill={GOVPATH_COLORS.primarySoft}
                  />
                  <Area
                    type="monotone"
                    dataKey="accuracy_percent"
                    name="Accuracy %"
                    stroke={GOVPATH_CHART_PALETTE[3]}
                    fill={GOVPATH_CHART_PALETTE[4]}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-xs text-gp-ink-muted py-12 text-center">Complete assessments to plot score trends.</p>
          )}
        </div>

        <div className="gov-card p-5">
          <h2 className="text-base font-bold text-gp-ink mb-4">Subject Mastery vs Required Depth</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.subject_performance}>
                <CartesianGrid strokeDasharray="3 3" stroke={GOVPATH_COLORS.border} />
                <XAxis dataKey="subject_id" tick={{ fontSize: 10, fill: GOVPATH_COLORS.textSecondary }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: GOVPATH_COLORS.textSecondary }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="demonstrated_score" name="Demonstrated" fill={GOVPATH_CHART_PALETTE[0]} radius={[4, 4, 0, 0]} />
                <Bar dataKey="required_depth" name="Required" fill={GOVPATH_CHART_PALETTE[4]} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
