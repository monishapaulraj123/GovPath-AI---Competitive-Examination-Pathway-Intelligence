import React, { useEffect, useState } from 'react';
import {
  CalendarClock,
  CheckCircle2,
  Plus,
  RefreshCw,
  SkipForward,
  Trash2,
} from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader, StatCard } from '../components/UI';

export default function StudyPlanPage() {
  const [plan, setPlan] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Generation & Confirmation state
  const [genHours, setGenHours] = useState(4.5);
  const [genDays, setGenDays] = useState(6);
  const [pendingPreview, setPendingPreview] = useState<any>(null);

  // Add custom task form
  const [showAdd, setShowAdd] = useState(false);
  const [newTask, setNewTask] = useState({
    scheduled_date: new Date().toISOString().slice(0, 10),
    title: '',
    subject_name: 'Indian Polity & Governance',
    topic_name: 'Constitution',
    task_type: 'concept_study',
    duration_minutes: 60,
    priority: 'high',
    notes: '',
  });

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getStudyPlan();
      setPlan(res.plan);
      if (res.plan) {
        setGenHours(res.plan.daily_hours);
        setGenDays(res.plan.days_per_week);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load study plan');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleGenerate = async (confirmReplace = false) => {
    setError('');
    try {
      const res = await api.generateStudyPlan({
        daily_hours: genHours,
        days_per_week: genDays,
        confirm_replace: confirmReplace,
      });
      if (res.requires_confirmation) {
        setPendingPreview(res.preview_plan);
      } else {
        setPendingPreview(null);
        setPlan(res.plan);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to generate plan');
    }
  };

  const handleTaskStatus = async (taskId: number, status: string) => {
    const updated = await api.updateStudyTask(taskId, { status });
    setPlan(updated);
  };

  const handleDeleteTask = async (taskId: number) => {
    const updated = await api.deleteStudyTask(taskId);
    setPlan(updated);
  };

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    const updated = await api.addStudyTask(newTask);
    setPlan(updated);
    setShowAdd(false);
    setNewTask({ ...newTask, title: '', notes: '' });
  };

  if (loading) return <LoadingState label="Loading Adaptive Study Planner..." />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Adaptive Study Plan"
        subtitle="Dynamically allocates your daily study hours across priority competency gaps, practice drills, and overdue revisions."
        actions={
          <button
            onClick={() => setShowAdd(!showAdd)}
            className="gov-btn-secondary px-3.5 py-2 text-xs"
          >
            <Plus className="w-3.5 h-3.5" /> Add Task
          </button>
        }
      />

      {error && <ErrorBanner message={error} />}

      {/* Generate / Adapt Bar */}
      <div className="gov-card p-5 flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Daily Study Hours</label>
          <input
            type="number"
            step="0.5"
            min="1"
            max="14"
            value={genHours}
            onChange={(e) => setGenHours(Number(e.target.value))}
            className="gov-input w-28 px-3 py-2 text-xs font-semibold"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Days / Week</label>
          <input
            type="number"
            min="1"
            max="7"
            value={genDays}
            onChange={(e) => setGenDays(Number(e.target.value))}
            className="gov-input w-24 px-3 py-2 text-xs font-semibold"
          />
        </div>
        <button
          onClick={() => handleGenerate(false)}
          className="gov-btn-primary px-4 py-2 text-xs"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Generate / Adapt Weekly Plan
        </button>
      </div>

      {/* Confirmation Banner if active plan exists */}
      {pendingPreview && (
        <div className="gov-card p-5 border-gp-warning/30 bg-gp-warning-bg space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-gp-ink">Confirm Plan Replacement</h3>
              <p className="text-xs text-gp-ink-secondary mt-0.5">
                {pendingPreview.generation_rationale} Replacing your active plan will archive current pending tasks.
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                onClick={() => setPendingPreview(null)}
                className="gov-btn-secondary px-3 py-1.5 text-xs"
              >
                Keep Existing
              </button>
              <button
                onClick={() => handleGenerate(true)}
                className="gov-btn-primary px-3.5 py-1.5 text-xs"
              >
                Confirm & Activate New Plan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Custom Task Modal/Panel */}
      {showAdd && (
        <form onSubmit={handleAddTask} className="gov-card p-5 space-y-3">
          <h3 className="text-sm font-bold text-gp-ink">Add Custom Study Task</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input
              required
              placeholder="Task Title (e.g., Revise Monetary Policy)"
              value={newTask.title}
              onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
              className="gov-input px-3 py-2 text-xs"
            />
            <input
              required
              placeholder="Subject"
              value={newTask.subject_name}
              onChange={(e) => setNewTask({ ...newTask, subject_name: e.target.value })}
              className="gov-input px-3 py-2 text-xs"
            />
            <input
              type="date"
              value={newTask.scheduled_date}
              onChange={(e) => setNewTask({ ...newTask, scheduled_date: e.target.value })}
              className="gov-input px-3 py-2 text-xs"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input
              required
              placeholder="Topic"
              value={newTask.topic_name}
              onChange={(e) => setNewTask({ ...newTask, topic_name: e.target.value })}
              className="gov-input px-3 py-2 text-xs"
            />
            <input
              type="number"
              min="15"
              max="300"
              value={newTask.duration_minutes}
              onChange={(e) => setNewTask({ ...newTask, duration_minutes: Number(e.target.value) })}
              className="gov-input px-3 py-2 text-xs"
            />
            <button type="submit" className="gov-btn-primary px-4 py-2 text-xs">
              Save Task to Schedule
            </button>
          </div>
        </form>
      )}

      {plan ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Plan Completion" value={`${plan.progress.completion_percent}%`} icon={<CalendarClock className="w-5 h-5" />} accent="primary" />
            <StatCard label="Tasks Completed" value={`${plan.progress.completed_tasks} / ${plan.progress.total_tasks}`} accent="success" />
            <StatCard label="Completed Hours" value={`${plan.progress.completed_hours}h`} subtext={`of ${plan.progress.planned_hours}h planned`} accent="primary" />
            <StatCard label="Skipped Tasks" value={plan.progress.skipped_tasks} accent="warning" />
          </div>

          <div className="gov-card p-5 space-y-3">
            <div>
              <h2 className="text-base font-bold text-gp-ink">{plan.title}</h2>
              <p className="text-xs text-gp-ink-secondary mt-0.5">{plan.generation_rationale}</p>
            </div>

            <div className="divide-y divide-gp-divider">
              {plan.tasks.map((t: any) => (
                <div key={t.id} className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-gp-bg border border-gp-border text-gp-ink-secondary font-mono text-[11px] font-semibold">
                        Day {t.day_index} · {t.scheduled_date}
                      </span>
                      <span className="px-2 py-0.5 rounded bg-gp-primary-light text-gp-primary border border-gp-primary-border text-[11px] font-semibold capitalize">
                        {t.task_type.replace('_', ' ')}
                      </span>
                      <span className="text-xs text-gp-ink-muted">{t.duration_minutes} mins</span>
                    </div>
                    <p
                      className={`text-sm font-semibold ${
                        t.status === 'completed'
                          ? 'line-through text-gp-ink-muted'
                          : t.status === 'skipped'
                          ? 'text-gp-ink-muted'
                          : 'text-gp-ink'
                      }`}
                    >
                      {t.title}
                    </p>
                    <p className="text-xs text-gp-ink-secondary">
                      {t.subject_name} — {t.notes}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleTaskStatus(t.id, t.status === 'completed' ? 'pending' : 'completed')}
                      className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border flex items-center gap-1 transition ${
                        t.status === 'completed'
                          ? 'bg-gp-success-bg border-gp-success/25 text-gp-success'
                          : 'bg-gp-surface border-gp-border text-gp-ink-secondary hover:bg-gp-primary-light hover:text-gp-primary'
                      }`}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {t.status === 'completed' ? 'Completed' : 'Complete'}
                    </button>
                    <button
                      onClick={() => handleTaskStatus(t.id, t.status === 'skipped' ? 'pending' : 'skipped')}
                      className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border flex items-center gap-1 transition ${
                        t.status === 'skipped'
                          ? 'bg-gp-warning-bg border-gp-warning/25 text-gp-warning'
                          : 'bg-gp-surface border-gp-border text-gp-ink-secondary hover:bg-gp-bg'
                      }`}
                    >
                      <SkipForward className="w-3.5 h-3.5" /> Skip
                    </button>
                    <button
                      onClick={() => handleDeleteTask(t.id)}
                      className="p-1.5 rounded-lg border border-gp-border text-gp-ink-muted hover:text-gp-error hover:bg-gp-error-bg transition"
                      title="Delete task"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : (
        <div className="gov-card p-10 text-center text-sm text-gp-ink-secondary">
          No active study plan yet. Click <strong className="text-gp-ink">Generate / Adapt Weekly Plan</strong> above to create one from your gap analysis.
        </div>
      )}
    </div>
  );
}
