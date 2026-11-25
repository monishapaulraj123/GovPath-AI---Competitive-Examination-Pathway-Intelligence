import React, { useEffect, useState } from 'react';
import { CheckCircle2, Save } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { ErrorBanner, LoadingState, PageHeader } from '../components/UI';

const ALL_EXAMS = [
  { id: 'UPSC_CSE', label: 'UPSC CSE' },
  { id: 'TNPSC_GRP1', label: 'TNPSC Group I' },
  { id: 'TNPSC_GRP2', label: 'TNPSC Group II/IIA' },
  { id: 'SSC_CGL', label: 'SSC CGL' },
  { id: 'SSC_CHSL', label: 'SSC CHSL' },
  { id: 'IBPS_PO', label: 'IBPS PO' },
  { id: 'RRB_NTPC', label: 'RRB NTPC' },
  { id: 'UPSC_CDS', label: 'UPSC CDS' },
];

const JOB_CATEGORIES = [
  'Civil Services',
  'State Civil Services',
  'Staff Selection & Central Group B/C',
  'Banking & Financial Sector',
  'Railway Recruitment',
  'Defence Services',
];

export default function ProfilePage() {
  const { refreshUser } = useAuth();
  const [form, setForm] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .getProfile()
      .then((res) => setForm(res))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSavedMsg('');
    setError('');
    try {
      const updated = await api.updateProfile({
        display_name: form.display_name,
        age_range: form.age_range,
        educational_qualification: form.educational_qualification,
        degree_discipline: form.degree_discipline,
        graduation_status: form.graduation_status,
        state: form.state,
        preferred_language: form.preferred_language,
        current_occupation: form.current_occupation,
        aspirant_category: form.aspirant_category,
        daily_study_hours: Number(form.daily_study_hours),
        days_per_week: Number(form.days_per_week),
        timeline_months: Number(form.timeline_months),
        previous_attempts: Number(form.previous_attempts),
        previous_experience: form.previous_experience,
        preferred_job_categories: form.preferred_job_categories,
        career_preferences: form.career_preferences,
        primary_target_exam: form.primary_target_exam,
        secondary_target_exams: form.secondary_target_exams,
        constraints: form.constraints,
      });
      setForm(updated);
      await refreshUser();
      setSavedMsg('Profile updated! Pathway & study planning engines will now use your new parameters.');
    } catch (err: any) {
      setError(err.message || 'Validation failed while saving profile');
    } finally {
      setSaving(false);
    }
  };

  const toggleSecondary = (id: string) => {
    const curr = form.secondary_target_exams || [];
    setForm({
      ...form,
      secondary_target_exams: curr.includes(id) ? curr.filter((x: string) => x !== id) : [...curr, id],
    });
  };

  const toggleCategory = (cat: string) => {
    const curr = form.preferred_job_categories || [];
    setForm({
      ...form,
      preferred_job_categories: curr.includes(cat) ? curr.filter((x: string) => x !== cat) : [...curr, cat],
    });
  };

  if (loading) return <LoadingState label="Loading aspirant profile..." />;
  if (!form) return <ErrorBanner message={error || 'Profile unavailable'} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Aspirant Profile"
        subtitle="Editable profile feeding directly into the Pathway Planner, Gap Analysis, and Adaptive Study Schedule engines."
      />

      {error && <ErrorBanner message={error} />}
      {savedMsg && (
        <div className="p-4 rounded-xl bg-gp-success-bg border border-gp-success/25 text-gp-success text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          {savedMsg}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Basic & Academic Info */}
        <div className="gov-card p-6 space-y-4">
          <h2 className="text-base font-bold text-gp-ink">Academic & Personal Context</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Display Name *</label>
              <input
                required
                minLength={2}
                value={form.display_name || ''}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                className="gov-input w-full px-3 py-2"
              />
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Age Range</label>
              <select
                value={form.age_range || '21-25'}
                onChange={(e) => setForm({ ...form, age_range: e.target.value })}
                className="gov-input w-full px-3 py-2"
              >
                <option value="18-20">18–20</option>
                <option value="21-25">21–25</option>
                <option value="26-30">26–30</option>
                <option value="31-35">31–35</option>
                <option value="36+">36+</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">State / UT</label>
              <input
                value={form.state || ''}
                onChange={(e) => setForm({ ...form, state: e.target.value })}
                className="gov-input w-full px-3 py-2"
              />
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Educational Qualification</label>
              <input
                value={form.educational_qualification || ''}
                onChange={(e) => setForm({ ...form, educational_qualification: e.target.value })}
                className="gov-input w-full px-3 py-2"
              />
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Degree / Discipline</label>
              <input
                value={form.degree_discipline || ''}
                onChange={(e) => setForm({ ...form, degree_discipline: e.target.value })}
                className="gov-input w-full px-3 py-2"
              />
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Graduation Status</label>
              <select
                value={form.graduation_status || 'Completed'}
                onChange={(e) => setForm({ ...form, graduation_status: e.target.value })}
                className="gov-input w-full px-3 py-2"
              >
                <option value="Completed">Completed</option>
                <option value="Final Year">Final Year</option>
                <option value="Pursuing">Pursuing (Undergraduate)</option>
                <option value="12th Pass">Higher Secondary (10+2)</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Current Occupation</label>
              <select
                value={form.current_occupation || 'Full-time Aspirant'}
                onChange={(e) => setForm({ ...form, current_occupation: e.target.value })}
                className="gov-input w-full px-3 py-2"
              >
                <option value="Student">Student</option>
                <option value="Graduate / Full-time Aspirant">Graduate / Full-time Aspirant</option>
                <option value="Working Professional">Working Professional</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Preferred Language</label>
              <select
                value={form.preferred_language || 'English'}
                onChange={(e) => setForm({ ...form, preferred_language: e.target.value })}
                className="gov-input w-full px-3 py-2"
              >
                <option value="English">English</option>
                <option value="Tamil">Tamil</option>
                <option value="Hindi">Hindi</option>
                <option value="Bilingual (English + Regional)">Bilingual (English + Regional)</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Previous Exam Attempts</label>
              <input
                type="number"
                min={0}
                max={20}
                value={form.previous_attempts ?? 0}
                onChange={(e) => setForm({ ...form, previous_attempts: Number(e.target.value) })}
                className="gov-input w-full px-3 py-2"
              />
            </div>
          </div>
        </div>

        {/* Study Capacity & Targets */}
        <div className="gov-card p-6 space-y-4">
          <h2 className="text-base font-bold text-gp-ink">Preparation Capacity & Examination Targets</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Daily Study Hours (0.5–16)</label>
              <input
                type="number"
                step="0.5"
                min={0.5}
                max={16}
                required
                value={form.daily_study_hours ?? 4.5}
                onChange={(e) => setForm({ ...form, daily_study_hours: Number(e.target.value) })}
                className="gov-input w-full px-3 py-2"
              />
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Study Days / Week (1–7)</label>
              <input
                type="number"
                min={1}
                max={7}
                required
                value={form.days_per_week ?? 6}
                onChange={(e) => setForm({ ...form, days_per_week: Number(e.target.value) })}
                className="gov-input w-full px-3 py-2"
              />
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Timeline (Months)</label>
              <input
                type="number"
                min={1}
                max={60}
                required
                value={form.timeline_months ?? 12}
                onChange={(e) => setForm({ ...form, timeline_months: Number(e.target.value) })}
                className="gov-input w-full px-3 py-2"
              />
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Primary Target Exam</label>
              <select
                value={form.primary_target_exam || 'UPSC_CSE'}
                onChange={(e) => setForm({ ...form, primary_target_exam: e.target.value })}
                className="gov-input w-full px-3 py-2 font-semibold"
              >
                {ALL_EXAMS.map((ex) => (
                  <option key={ex.id} value={ex.id}>{ex.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="text-xs">
            <label className="block font-semibold text-gp-ink-secondary mb-1.5">Secondary / Backup Examinations</label>
            <div className="flex flex-wrap gap-2">
              {ALL_EXAMS.filter((e) => e.id !== form.primary_target_exam).map((ex) => {
                const active = (form.secondary_target_exams || []).includes(ex.id);
                return (
                  <button
                    type="button"
                    key={ex.id}
                    onClick={() => toggleSecondary(ex.id)}
                    className={`px-3 py-1.5 rounded-lg border font-semibold transition ${
                      active
                        ? 'bg-gp-primary text-white border-gp-primary'
                        : 'bg-gp-surface text-gp-ink-secondary border-gp-border hover:border-gp-primary-border hover:text-gp-primary'
                    }`}
                  >
                    {ex.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="text-xs">
            <label className="block font-semibold text-gp-ink-secondary mb-1.5">Preferred Government Job Categories</label>
            <div className="flex flex-wrap gap-2">
              {JOB_CATEGORIES.map((cat) => {
                const active = (form.preferred_job_categories || []).includes(cat);
                return (
                  <button
                    type="button"
                    key={cat}
                    onClick={() => toggleCategory(cat)}
                    className={`px-3 py-1.5 rounded-lg border font-semibold transition ${
                      active
                        ? 'bg-gp-primary-soft text-gp-primary border-gp-primary'
                        : 'bg-gp-surface text-gp-ink-secondary border-gp-border hover:border-gp-primary-border'
                    }`}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Previous Preparation Experience</label>
              <textarea
                rows={2}
                value={form.previous_experience || ''}
                onChange={(e) => setForm({ ...form, previous_experience: e.target.value })}
                className="gov-input w-full px-3 py-2"
              />
            </div>
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Career Preferences & Optional Constraints</label>
              <textarea
                rows={2}
                value={form.constraints || ''}
                onChange={(e) => setForm({ ...form, constraints: e.target.value })}
                className="gov-input w-full px-3 py-2"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="gov-btn-primary px-6 py-2.5 text-sm"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving Changes...' : 'Save Profile'}
          </button>
        </div>
      </form>
    </div>
  );
}
