import React, { useState } from 'react';
import { ArrowRight, BrainCircuit, GitBranch, Layers, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login, register, loginDemo } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [primaryExam, setPrimaryExam] = useState('UPSC_CSE');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, password, fullName, primaryExam);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDemo = async () => {
    setError('');
    setSubmitting(true);
    try {
      await loginDemo();
    } catch (err: any) {
      setError(err.message || 'Failed to launch demo workspace');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gp-bg flex flex-col lg:flex-row">
      {/* Left Intelligence Overview Panel (Clean Light Theme) */}
      <div className="lg:w-1/2 bg-gp-surface border-b lg:border-b-0 lg:border-r border-gp-border p-8 sm:p-12 lg:p-16 flex flex-col justify-between">
        <div>
          <div className="flex items-center gap-3 mb-10">
            <div className="w-10 h-10 rounded-xl bg-gp-primary flex items-center justify-center shadow-sm">
              <GitBranch className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-gp-ink">GovPath AI</h1>
              <p className="text-xs font-medium text-gp-primary">Government Exam Intelligence</p>
            </div>
          </div>

          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight leading-tight text-gp-ink max-w-xl">
            Adaptive Readiness, Knowledge Transfer & Career Pathway Optimization
          </h2>
          <p className="mt-4 text-gp-ink-secondary text-sm sm:text-base max-w-lg leading-relaxed">
            An evidence-driven multi-agent platform mapping your demonstrated competencies across UPSC, TNPSC, SSC,
            Banking, Railway, and Defence examinations.
          </p>

          <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-xl">
            <div className="p-4 rounded-xl bg-gp-primary-light/60 border border-gp-primary-border">
              <BrainCircuit className="w-5 h-5 text-gp-primary mb-2" />
              <h3 className="text-sm font-semibold text-gp-ink">Agentic AI Orchestrator</h3>
              <p className="text-xs text-gp-ink-secondary mt-1">
                6 specialized agents grounded in your competency evidence, knowledge graph, and verified RAG documents.
              </p>
            </div>
            <div className="p-4 rounded-xl bg-gp-primary-light/60 border border-gp-primary-border">
              <Layers className="w-5 h-5 text-gp-primary mb-2" />
              <h3 className="text-sm font-semibold text-gp-ink">Cross-Exam Knowledge Transfer</h3>
              <p className="text-xs text-gp-ink-secondary mt-1">
                Quantifies transferable preparation, depth mismatches, and bridge hours across exams.
              </p>
            </div>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-gp-divider flex items-center gap-2 text-xs text-gp-ink-secondary">
          <ShieldCheck className="w-4 h-4 text-gp-success shrink-0" />
          <span>Explainable readiness modeling · Verified source attribution · Zero fabricated exam claims</span>
        </div>
      </div>

      {/* Right Auth Form Panel */}
      <div className="lg:w-1/2 flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md gov-card p-7 sm:p-8">
          <div className="flex gap-2 p-1 bg-gp-bg rounded-lg border border-gp-border mb-6">
            <button
              type="button"
              onClick={() => { setMode('login'); setError(''); }}
              className={`flex-1 py-2 text-xs font-semibold rounded-md transition ${
                mode === 'login'
                  ? 'bg-gp-surface text-gp-primary shadow-sm border border-gp-primary-border'
                  : 'text-gp-ink-secondary hover:text-gp-ink'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setMode('register'); setError(''); }}
              className={`flex-1 py-2 text-xs font-semibold rounded-md transition ${
                mode === 'register'
                  ? 'bg-gp-surface text-gp-primary shadow-sm border border-gp-primary-border'
                  : 'text-gp-ink-secondary hover:text-gp-ink'
              }`}
            >
              Create Account
            </button>
          </div>

          <h2 className="text-xl font-bold text-gp-ink">
            {mode === 'login' ? 'Enter GovPath AI Workspace' : 'Create Your Aspirant Profile'}
          </h2>
          <p className="text-xs text-gp-ink-secondary mt-1 mb-6">
            {mode === 'login'
              ? 'Access your dashboard, diagnostics, and adaptive study plan.'
              : 'Jump straight into the workspace and complete optional details anytime.'}
          </p>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-gp-error-bg border border-gp-error/25 text-xs text-gp-error">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-xs font-semibold text-gp-ink mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g., Priya Natarajan"
                  className="gov-input w-full px-3.5 py-2.5 text-sm"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-gp-ink mb-1">Email Address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="gov-input w-full px-3.5 py-2.5 text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gp-ink mb-1">Password</label>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimum 6 characters"
                className="gov-input w-full px-3.5 py-2.5 text-sm"
              />
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-xs font-semibold text-gp-ink mb-1">Primary Target Examination</label>
                <select
                  value={primaryExam}
                  onChange={(e) => setPrimaryExam(e.target.value)}
                  className="gov-input w-full px-3.5 py-2.5 text-sm"
                >
                  <option value="UPSC_CSE">UPSC Civil Services (CSE)</option>
                  <option value="TNPSC_GRP1">TNPSC Group I</option>
                  <option value="TNPSC_GRP2">TNPSC Group II / IIA</option>
                  <option value="SSC_CGL">SSC CGL</option>
                  <option value="SSC_CHSL">SSC CHSL</option>
                  <option value="IBPS_PO">IBPS PO (Banking)</option>
                  <option value="RRB_NTPC">RRB NTPC (Railway)</option>
                  <option value="UPSC_CDS">UPSC CDS (Defence)</option>
                </select>
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="gov-btn-primary w-full py-2.5 px-4 text-sm"
            >
              {submitting ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account & Enter'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-gp-divider" />
            <span className="text-[11px] font-medium uppercase text-gp-ink-muted">or explore instantly</span>
            <div className="h-px flex-1 bg-gp-divider" />
          </div>

          <button
            type="button"
            onClick={handleDemo}
            disabled={submitting}
            className="gov-btn-secondary w-full py-2.5 px-4 text-sm"
          >
            Enter Demonstration Student Workspace (Arjun Krishnan)
          </button>
          <p className="mt-2 text-[11px] text-center text-gp-ink-muted">
            Includes seeded demonstration assessments, knowledge graph evidence, and adaptive plans.
          </p>
        </div>
      </div>
    </div>
  );
}
