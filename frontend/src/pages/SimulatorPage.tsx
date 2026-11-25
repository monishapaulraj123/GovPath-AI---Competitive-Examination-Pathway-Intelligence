import React, { useEffect, useState } from 'react';
import { Info, Play, SlidersHorizontal } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader, StatCard } from '../components/UI';
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

const SUBJECT_TAGS = ['POLITY', 'ECONOMY', 'HISTORY', 'GEOGRAPHY', 'CURRENT_AFFAIRS', 'QUANT', 'REASONING', 'ENGLISH', 'STATE_TN'];

export default function SimulatorPage() {
  const [targetExam, setTargetExam] = useState('TNPSC_GRP1');
  const [sourceExam, setSourceExam] = useState('UPSC_CSE');
  const [dailyHours, setDailyHours] = useState(4.5);
  const [daysPerWeek, setDaysPerWeek] = useState(6);
  const [durationMonths, setDurationMonths] = useState(6);
  const [focusSubjects, setFocusSubjects] = useState<string[]>(['ECONOMY', 'STATE_TN']);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const runSim = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.runSimulator({
        target_exam_id: targetExam,
        source_exam_id: sourceExam,
        daily_hours: dailyHours,
        days_per_week: daysPerWeek,
        duration_months: durationMonths,
        focus_subject_ids: focusSubjects,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runSim();
  }, []);

  const toggleFocus = (sid: string) => {
    setFocusSubjects((prev) => (prev.includes(sid) ? prev.filter((x) => x !== sid) : [...prev, sid]));
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="What-If Scenario Simulator"
        subtitle="Test exam switching, daily study hours, timeline changes, and focus allocations with transparent estimation modeling."
      />

      {/* Controls */}
      <div className="gov-card p-5 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div>
            <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Current / Source Track</label>
            <select
              value={sourceExam}
              onChange={(e) => setSourceExam(e.target.value)}
              className="gov-input w-full px-3 py-2 text-xs font-semibold"
            >
              {EXAM_LIST.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Simulated Target Exam</label>
            <select
              value={targetExam}
              onChange={(e) => setTargetExam(e.target.value)}
              className="gov-input w-full px-3 py-2 text-xs font-semibold"
            >
              {EXAM_LIST.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Daily Hours: {dailyHours}h</label>
            <input
              type="range"
              min="1"
              max="12"
              step="0.5"
              value={dailyHours}
              onChange={(e) => setDailyHours(Number(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Days/Week: {daysPerWeek}</label>
            <input
              type="range"
              min="2"
              max="7"
              step="1"
              value={daysPerWeek}
              onChange={(e) => setDaysPerWeek(Number(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Duration: {durationMonths} months</label>
            <input
              type="range"
              min="1"
              max="24"
              step="1"
              value={durationMonths}
              onChange={(e) => setDurationMonths(Number(e.target.value))}
              className="w-full"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-gp-divider">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-semibold text-gp-ink-secondary mr-1">Priority Focus Subjects:</span>
            {SUBJECT_TAGS.map((sid) => {
              const active = focusSubjects.includes(sid);
              return (
                <button
                  key={sid}
                  type="button"
                  onClick={() => toggleFocus(sid)}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-semibold border transition ${
                    active
                      ? 'bg-gp-primary text-white border-gp-primary'
                      : 'bg-gp-surface text-gp-ink-secondary border-gp-border hover:border-gp-primary-border hover:text-gp-primary'
                  }`}
                >
                  {sid}
                </button>
              );
            })}
          </div>
          <button
            onClick={runSim}
            className="gov-btn-primary px-4 py-2 text-xs"
          >
            <Play className="w-3.5 h-3.5" /> Run Simulation
          </button>
        </div>
      </div>

      {loading && <LoadingState label="Running scenario model..." />}
      {error && <ErrorBanner message={error} />}

      {!loading && result && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Projected Readiness"
              value={`${result.baseline_comparison.projected_readiness_index}%`}
              subtext={`+${result.baseline_comparison.readiness_delta} pts from ${result.baseline_comparison.current_readiness_index}%`}
              icon={<SlidersHorizontal className="w-5 h-5" />}
              accent="primary"
            />
            <StatCard
              label="Projected Weighted Gap"
              value={`${result.baseline_comparison.projected_weighted_gap} pts`}
              subtext={`Reduced by ${result.baseline_comparison.gap_reduction} pts`}
              accent="success"
            />
            <StatCard
              label="Available Study Capacity"
              value={`${result.workload_assessment.total_available_hours}h`}
              subtext={`Need ~${result.workload_assessment.estimated_required_hours}h to close gaps`}
              accent="primary"
            />
            <StatCard
              label="Workload Feasibility"
              value={result.workload_assessment.feasibility_status}
              subtext={`Capacity ratio ${result.workload_assessment.capacity_to_need_ratio}×`}
              accent="warning"
            />
          </div>

          <div className="gov-card p-4 bg-gp-primary-light/50 border-gp-primary-border flex items-start gap-3 text-xs text-gp-ink-secondary">
            <Info className="w-4 h-4 text-gp-primary shrink-0 mt-0.5" />
            <span>{result.disclaimer}</span>
          </div>

          <div className="gov-card p-5">
            <h2 className="text-base font-bold text-gp-ink mb-4">Current vs Projected Competency Alignment</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={result.projected_competencies.slice(0, 10)}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GOVPATH_COLORS.border} />
                  <XAxis dataKey="subject_id" tick={{ fontSize: 10, fill: GOVPATH_COLORS.textSecondary }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: GOVPATH_COLORS.textSecondary }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="current_mastery" name="Current Mastery" fill={GOVPATH_CHART_PALETTE[2]} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="projected_mastery" name="Projected Mastery" fill={GOVPATH_CHART_PALETTE[0]} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="required_depth" name="Required Depth" fill={GOVPATH_CHART_PALETTE[4]} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
