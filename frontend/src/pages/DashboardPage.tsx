import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  Bot,
  CalendarCheck,
  CheckCircle2,
  ClipboardCheck,
  Compass,
  Scale,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react';
import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { api } from '../api/client';
import {
  DemoDataBanner,
  ErrorBanner,
  LoadingState,
  PriorityBadge,
  StatCard,
} from '../components/UI';
import { GOVPATH_CHART_PALETTE, GOVPATH_COLORS } from '../theme/colors';

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.dashboard();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleToggleTask = async (task: any) => {
    const nextStatus = task.status === 'completed' ? 'pending' : 'completed';
    try {
      await api.updateStudyTask(task.id, { status: nextStatus });
      load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  if (loading) return <LoadingState label="Computing readiness & pathway overview..." />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!data) return null;

  const { profile, readiness, gap_overview, study_activity, insights, pathway_overview } = data;
  const radarData = (readiness.subject_breakdown || []).slice(0, 6).map((s: any) => ({
    subject: s.subject_id.replace('_', ' '),
    Demonstrated: s.demonstrated_score,
    Required: s.required_depth,
  }));

  return (
    <div className="space-y-6">
      <DemoDataBanner show={readiness.has_only_demo_data} />

      {/* Welcome / Hero Section — Clean Light Theme */}
      <div className="gov-card p-6 bg-gradient-to-br from-gp-surface via-gp-surface to-gp-primary-light/60">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-gp-primary-light border border-gp-primary-border text-gp-primary text-xs font-semibold mb-3">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Primary Target: {readiness.exam_name}</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-gp-ink">
              Welcome back, {profile?.display_name || 'Aspirant'}
            </h1>
            <p className="mt-1 text-sm text-gp-ink-secondary max-w-2xl">
              {readiness.assessments_completed > 0
                ? `Measured readiness alignment stands at ${readiness.readiness_index}% across ${readiness.competency_coverage}% of target competencies (${profile?.daily_study_hours || 4.5}h/day schedule).`
                : 'Your workspace is ready. Run a diagnostic assessment to establish your baseline competency profile.'}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => navigate('/assessments')}
              className="gov-btn-primary px-3.5 py-2 text-xs"
            >
              <ClipboardCheck className="w-3.5 h-3.5" /> Take Diagnostic
            </button>
            <button
              onClick={() => navigate('/counsellor')}
              className="gov-btn-secondary px-3.5 py-2 text-xs"
            >
              <Bot className="w-3.5 h-3.5" /> Ask AI Counsellor
            </button>
            <button
              onClick={() => navigate('/study-plan')}
              className="gov-btn-secondary px-3.5 py-2 text-xs"
            >
              <CalendarCheck className="w-3.5 h-3.5" /> Study Plan
            </button>
            <button
              onClick={() => navigate('/compare')}
              className="gov-btn-secondary px-3.5 py-2 text-xs"
            >
              <Scale className="w-3.5 h-3.5" /> Compare Exams
            </button>
            <button
              onClick={() => navigate('/gap-analysis')}
              className="gov-btn-secondary px-3.5 py-2 text-xs"
            >
              <Target className="w-3.5 h-3.5" /> Gap Analysis
            </button>
            <button
              onClick={() => navigate('/practice')}
              className="gov-btn-secondary px-3.5 py-2 text-xs"
            >
              <Compass className="w-3.5 h-3.5" /> Start Revision
            </button>
          </div>
        </div>
      </div>

      {/* Readiness KPI Grid — Consistent White Cards + Primary Icon Containers */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        <StatCard
          label="Readiness Index"
          value={`${readiness.readiness_index}%`}
          subtext={`Alignment for ${readiness.exam_short_name}`}
          icon={<ShieldCheck className="w-5 h-5" />}
          accent="primary"
        />
        <StatCard
          label="Competency Coverage"
          value={`${readiness.competency_coverage}%`}
          subtext={`${readiness.assessments_completed} assessments logged`}
          icon={<Compass className="w-5 h-5" />}
          accent="primary"
        />
        <StatCard
          label="Accuracy"
          value={`${readiness.accuracy}%`}
          subtext="Across attempted questions"
          icon={<Target className="w-5 h-5" />}
          accent="primary"
        />
        <StatCard
          label="Retention Index"
          value={`${readiness.retention_index}%`}
          subtext="Assessed within 14 days"
          icon={<TrendingUp className="w-5 h-5" />}
          accent="primary"
        />
        <StatCard
          label="Study Consistency"
          value={`${readiness.consistency}%`}
          subtext={study_activity.progress ? `${study_activity.progress.completion_percent}% plan done` : 'No active plan'}
          icon={<CalendarCheck className="w-5 h-5" />}
          accent="primary"
        />
      </div>

      {/* Middle Analytics Row: Competency Radar + Gap Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-6 gov-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-gp-ink">Readiness vs Target Depth</h2>
              <p className="text-xs text-gp-ink-secondary">
                Subject-level competency alignment for {readiness.exam_short_name}
              </p>
            </div>
            <button
              onClick={() => navigate('/readiness')}
              className="text-xs font-semibold text-gp-primary hover:text-gp-primary-hover flex items-center gap-1"
            >
              Details <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
          {radarData.length > 0 ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke={GOVPATH_COLORS.border} />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: GOVPATH_COLORS.textSecondary, fontSize: 11 }} />
                  <Radar
                    name="Required"
                    dataKey="Required"
                    stroke={GOVPATH_CHART_PALETTE[2]}
                    fill={GOVPATH_CHART_PALETTE[4]}
                    fillOpacity={0.38}
                  />
                  <Radar
                    name="Demonstrated"
                    dataKey="Demonstrated"
                    stroke={GOVPATH_CHART_PALETTE[0]}
                    fill={GOVPATH_CHART_PALETTE[1]}
                    fillOpacity={0.42}
                  />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-gp-ink-muted py-12 text-center">No subject requirement data loaded.</p>
          )}
        </div>

        <div className="lg:col-span-6 gov-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-gp-ink">Preparation Gap Overview</h2>
              <p className="text-xs text-gp-ink-secondary">Subjects ranked by depth gap against exam benchmarks</p>
            </div>
            <button
              onClick={() => navigate('/gap-analysis')}
              className="text-xs font-semibold text-gp-primary hover:text-gp-primary-hover flex items-center gap-1"
            >
              Full Gap Matrix <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-3">
            {gap_overview.map((g: any) => (
              <div key={g.subject_id} className="p-3 rounded-lg bg-gp-bg border border-gp-border">
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="text-sm font-semibold text-gp-ink">{g.subject_name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-gp-ink-secondary">Gap: {g.avg_gap} pts</span>
                    <PriorityBadge priority={g.priority} />
                  </div>
                </div>
                <div className="gov-progress-track h-2">
                  <div
                    className="gov-progress-fill"
                    style={{ width: `${Math.min(100, (g.avg_current / Math.max(1, g.avg_required)) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Row: Today's Study Activity + AI Insights + Exam Pathway Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Study Activity */}
        <div className="lg:col-span-5 gov-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-gp-ink">Today's Study Activity</h2>
              <p className="text-xs text-gp-ink-secondary">
                {study_activity.progress
                  ? `${study_activity.progress.completed_hours}h completed of ${study_activity.progress.planned_hours}h weekly plan`
                  : 'Generate a personalized weekly plan'}
              </p>
            </div>
            <button
              onClick={() => navigate('/study-plan')}
              className="text-xs font-semibold text-gp-primary hover:text-gp-primary-hover"
            >
              Open Planner
            </button>
          </div>
          {study_activity.today_tasks?.length > 0 ? (
            <div className="space-y-2.5">
              {study_activity.today_tasks.map((t: any) => (
                <div
                  key={t.id}
                  onClick={() => handleToggleTask(t)}
                  className="p-3 rounded-lg border border-gp-border hover:border-gp-primary-border hover:bg-gp-primary-light/30 cursor-pointer flex items-start gap-3 transition"
                >
                  <CheckCircle2
                    className={`w-4 h-4 mt-0.5 shrink-0 ${
                      t.status === 'completed' ? 'text-gp-success' : 'text-gp-ink-muted'
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <p
                      className={`text-sm font-medium ${
                        t.status === 'completed' ? 'line-through text-gp-ink-muted' : 'text-gp-ink'
                      }`}
                    >
                      {t.title}
                    </p>
                    <p className="text-xs text-gp-ink-secondary mt-0.5">
                      {t.subject_name} · {t.duration_minutes} mins
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-xs text-gp-ink-muted mb-3">No scheduled tasks for today yet.</p>
              <button
                onClick={() => navigate('/study-plan')}
                className="gov-btn-primary px-3.5 py-2 text-xs"
              >
                Generate Adaptive Study Plan
              </button>
            </div>
          )}
        </div>

        {/* AI Insights */}
        <div className="lg:col-span-4 gov-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-gp-ink">Evidence-Backed AI Insights</h2>
            <Sparkles className="w-4 h-4 text-gp-primary" />
          </div>
          <div className="space-y-3">
            {insights.map((ins: any, idx: number) => (
              <div
                key={idx}
                onClick={() => navigate(ins.route)}
                className="p-3 rounded-lg bg-gp-bg border border-gp-border hover:border-gp-primary-border hover:bg-gp-primary-light/30 cursor-pointer transition"
              >
                <p className="text-xs font-bold text-gp-ink">{ins.title}</p>
                <p className="text-xs text-gp-ink-secondary mt-1 leading-relaxed">{ins.detail}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Exam Pathway Overview */}
        <div className="lg:col-span-3 gov-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-gp-ink">Exam Pathways</h2>
            <button
              onClick={() => navigate('/pathway-planner')}
              className="text-xs font-semibold text-gp-primary hover:text-gp-primary-hover"
            >
              All
            </button>
          </div>
          <div className="space-y-2.5">
            {pathway_overview.map((p: any) => (
              <div key={p.exam_id} className="p-3 rounded-lg border border-gp-border bg-gp-surface">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-gp-ink">{p.short_name}</span>
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-gp-primary-light text-gp-primary border border-gp-primary-border">
                    {p.role}
                  </span>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-gp-ink-secondary">
                  <span>Alignment: {p.readiness_index}%</span>
                  <span>Gap: {p.overall_gap}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
