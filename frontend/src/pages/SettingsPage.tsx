import React, { useEffect, useState } from 'react';
import { CheckCircle2, Cpu, Database, Save } from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader } from '../components/UI';

export default function SettingsPage() {
  const [profile, setProfile] = useState<any>(null);
  const [sysStatus, setSysStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.getProfile(), api.getSystemStatus()])
      .then(([p, s]) => {
        setProfile(p);
        setSysStatus(s);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSavedMsg('');
    try {
      const updated = await api.updateProfile({
        ai_preferences: profile.ai_preferences,
        notification_preferences: profile.notification_preferences,
        privacy_preferences: profile.privacy_preferences,
      });
      setProfile(updated);
      setSavedMsg('Preferences saved.');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState label="Loading system settings..." />;
  if (!profile) return <ErrorBanner message={error || 'Unable to load settings'} />;

  const aiPref = profile.ai_preferences || {};
  const notifPref = profile.notification_preferences || {};
  const privPref = profile.privacy_preferences || {};

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings & System Architecture"
        subtitle="Configure AI counsellor behavior, notification alerts, privacy preferences, and inspect active backend infrastructure."
      />

      {savedMsg && (
        <div className="p-3.5 rounded-xl bg-gp-success-bg border border-gp-success/25 text-gp-success text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" /> {savedMsg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AI Preferences */}
        <div className="gov-card p-5 space-y-4">
          <h2 className="text-base font-bold text-gp-ink">AI Counsellor Preferences</h2>
          <div className="space-y-3 text-xs">
            <div>
              <label className="block font-semibold text-gp-ink-secondary mb-1">Explanation Depth</label>
              <select
                value={aiPref.explanation_depth || 'balanced'}
                onChange={(e) =>
                  setProfile({ ...profile, ai_preferences: { ...aiPref, explanation_depth: e.target.value } })
                }
                className="gov-input w-full px-3 py-2"
              >
                <option value="concise">Concise Actionable Bullet Points</option>
                <option value="balanced">Balanced Evidence + Rationale</option>
                <option value="deep">Deep Conceptual Breakdown</option>
              </select>
            </div>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={!!aiPref.socratic_hints}
                onChange={(e) =>
                  setProfile({ ...profile, ai_preferences: { ...aiPref, socratic_hints: e.target.checked } })
                }
                className="rounded border-gp-border"
              />
              <span className="text-gp-ink-secondary font-medium">
                Provide guided reasoning hints before revealing answers
              </span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={!!aiPref.auto_suggest_plan_updates}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    ai_preferences: { ...aiPref, auto_suggest_plan_updates: e.target.checked },
                  })
                }
                className="rounded border-gp-border"
              />
              <span className="text-gp-ink-secondary font-medium">
                Propose confirmable study plan updates when gaps shift
              </span>
            </label>
          </div>
        </div>

        {/* Notification & Privacy Preferences */}
        <div className="gov-card p-5 space-y-4">
          <h2 className="text-base font-bold text-gp-ink">Notification & Privacy Controls</h2>
          <div className="space-y-2.5 text-xs">
            {[
              { key: 'revision_reminders', label: 'Scheduled spaced-revision reminders' },
              { key: 'plan_alerts', label: 'Adaptive study plan adjustment proposals' },
              { key: 'exam_updates', label: 'Official verification & exam structure notices' },
              { key: 'weekly_digest', label: 'Weekly readiness & error diagnosis digest' },
            ].map((item) => (
              <label key={item.key} className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!notifPref[item.key]}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      notification_preferences: { ...notifPref, [item.key]: e.target.checked },
                    })
                  }
                  className="rounded border-gp-border"
                />
                <span className="text-gp-ink-secondary font-medium">{item.label}</span>
              </label>
            ))}

            <div className="pt-3 border-t border-gp-divider">
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!privPref.retain_chat_history}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      privacy_preferences: { ...privPref, retain_chat_history: e.target.checked },
                    })
                  }
                  className="rounded border-gp-border"
                />
                <span className="text-gp-ink-secondary font-medium">
                  Persist AI Counsellor conversation history
                </span>
              </label>
            </div>
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className="gov-btn-primary px-5 py-2.5 text-xs"
        >
          <Save className="w-4 h-4" /> {saving ? 'Saving...' : 'Save Preferences'}
        </button>
      </div>

      {/* Live Infrastructure & LLM Status */}
      {sysStatus && (
        <div className="gov-card p-5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-gp-ink">
            <Database className="w-4 h-4 text-gp-primary" />
            Active Backend & AI Runtime Diagnostics
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-gp-bg border border-gp-border">
              <div className="text-gp-ink-secondary">Database Engine</div>
              <div className="font-semibold text-gp-ink mt-0.5">{sysStatus.database_backend}</div>
            </div>
            <div className="p-3 rounded-lg bg-gp-bg border border-gp-border">
              <div className="text-gp-ink-secondary">Knowledge Graph</div>
              <div className="font-semibold text-gp-ink mt-0.5">{sysStatus.graph_backend}</div>
            </div>
            <div className="p-3 rounded-lg bg-gp-bg border border-gp-border">
              <div className="text-gp-ink-secondary">RAG Vector Store</div>
              <div className="font-semibold text-gp-ink mt-0.5">
                {sysStatus.rag_backend} ({sysStatus.rag_document_count} docs)
              </div>
            </div>
            <div className="p-3 rounded-lg bg-gp-bg border border-gp-border">
              <div className="text-gp-ink-secondary flex items-center gap-1">
                <Cpu className="w-3 h-3 text-gp-primary" /> LLM Synthesis
              </div>
              <div className="font-semibold text-gp-ink mt-0.5">
                {sysStatus.llm_status.configured
                  ? `${sysStatus.llm_status.provider} · ${sysStatus.llm_status.model}`
                  : 'Grounded Deterministic Mode (Set OPENAI_API_KEY or GEMINI_API_KEY in backend/.env to enable external LLM)'}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
