import React, { useEffect, useState } from 'react';
import {
  CheckCircle2,
  Clock,
  Flag,
  Play,
  RotateCcw,
  XCircle,
} from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader } from '../components/UI';

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

export default function AssessmentsPage({ mockMode = false }: { mockMode?: boolean }) {
  const [attempts, setAttempts] = useState<any[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [competencies, setCompetencies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Config state
  const [examId, setExamId] = useState('UPSC_CSE');
  const [assessmentType, setAssessmentType] = useState(mockMode ? 'mock_test' : 'diagnostic');
  const [subjectId, setSubjectId] = useState('');
  const [competencyId, setCompetencyId] = useState('');
  const [questionCount, setQuestionCount] = useState(mockMode ? 15 : 8);

  // Active test runner state
  const [activeTest, setActiveTest] = useState<any>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<string, { selected_index: number | null; marked: boolean; time_spent: number }>>({});
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [elapsedTotal, setElapsedTotal] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  // Review state
  const [reviewDetail, setReviewDetail] = useState<any>(null);

  useEffect(() => {
    setAssessmentType(mockMode ? 'mock_test' : 'diagnostic');
    setQuestionCount(mockMode ? 15 : 8);
  }, [mockMode]);

  const loadHistory = async () => {
    setLoading(true);
    setError('');
    try {
      const [res, prof] = await Promise.all([
        api.listAssessments(),
        api.getProfile().catch(() => null),
      ]);
      setAttempts(res.attempts || []);
      setSubjects(res.subjects || []);
      setCompetencies(res.competencies || []);
      if (prof?.primary_target_exam) {
        setExamId(prof.primary_target_exam);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load assessments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  // Countdown + question timer
  useEffect(() => {
    if (!activeTest) return;
    const timer = setInterval(() => {
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0));
      setElapsedTotal((prev) => prev + 1);
      const q = activeTest.questions[currentIdx];
      if (q) {
        setAnswers((prev) => ({
          ...prev,
          [q.id]: {
            selected_index: prev[q.id]?.selected_index ?? null,
            marked: prev[q.id]?.marked ?? false,
            time_spent: (prev[q.id]?.time_spent ?? 0) + 1,
          },
        }));
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [activeTest, currentIdx]);

  const handleStart = async () => {
    setError('');
    try {
      const res = await api.startAssessment({
        exam_id: examId,
        assessment_type: assessmentType,
        subject_id: subjectId || undefined,
        competency_id: competencyId || undefined,
        question_count: questionCount,
      });
      setActiveTest(res);
      setReviewDetail(null);
      setCurrentIdx(0);
      setAnswers({});
      setSecondsLeft(res.time_limit_sec);
      setElapsedTotal(0);
    } catch (err: any) {
      setError(err.message || 'Failed to start assessment');
    }
  };

  const handleSubmit = async () => {
    if (!activeTest || submitting) return;
    setSubmitting(true);
    try {
      const payloadAnswers = activeTest.questions.map((q: any) => ({
        question_id: q.id,
        selected_index: answers[q.id]?.selected_index ?? null,
        marked_for_review: answers[q.id]?.marked ?? false,
        time_spent_sec: Math.max(1, answers[q.id]?.time_spent ?? 30),
      }));
      const result = await api.submitAssessment(activeTest.attempt_id, {
        answers: payloadAnswers,
        total_time_sec: Math.max(1, elapsedTotal),
      });
      setActiveTest(null);
      setReviewDetail(result);
      loadHistory();
    } catch (err: any) {
      setError(err.message || 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  const openAttemptReview = async (id: number) => {
    const detail = await api.getAssessmentDetail(id);
    setReviewDetail(detail);
    setActiveTest(null);
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${String(m).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
  };

  if (loading) return <LoadingState label="Loading assessment engine..." />;

  // Active Test Runner View
  if (activeTest) {
    const q = activeTest.questions[currentIdx];
    const ans = answers[q.id] || { selected_index: null, marked: false, time_spent: 0 };

    return (
      <div className="space-y-5">
        <div className="gov-card p-4 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-gp-ink">{activeTest.title}</h2>
            <p className="text-xs text-gp-ink-secondary">
              Question {currentIdx + 1} of {activeTest.questions.length} · {q.source_type}
            </p>
            {activeTest.selection_note && (
              <p className="text-[11px] text-gp-primary mt-0.5">{activeTest.selection_note}</p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="px-3 py-1.5 rounded-lg bg-gp-primary-light border border-gp-primary-border text-gp-primary font-mono text-sm font-bold flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-gp-primary" />
              {formatTime(secondsLeft)}
            </div>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-gp-success hover:opacity-90 text-white text-xs font-semibold"
            >
              {submitting ? 'Scoring...' : 'Submit Test'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Question Card */}
          <div className="lg:col-span-8 gov-card p-6 space-y-5">
            <div className="flex items-center justify-between text-xs text-gp-ink-secondary">
              <span className="px-2.5 py-0.5 rounded bg-gp-primary-light text-gp-primary border border-gp-primary-border font-semibold">
                {q.subject_name} · {q.topic_name}
              </span>
              <span className="uppercase font-semibold">{q.difficulty}</span>
            </div>

            <div className="text-sm sm:text-base font-medium text-gp-ink whitespace-pre-line leading-relaxed">
              {q.prompt}
            </div>

            <div className="space-y-2.5">
              {q.options.map((opt: string, idx: number) => {
                const chosen = ans.selected_index === idx;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() =>
                      setAnswers((prev) => ({
                        ...prev,
                        [q.id]: { ...ans, selected_index: idx },
                      }))
                    }
                    className={`w-full text-left p-3.5 rounded-xl border text-sm flex items-start gap-3 transition ${
                      chosen
                        ? 'border-gp-primary bg-gp-primary-soft text-gp-ink font-medium'
                        : 'border-gp-border hover:border-gp-primary-border bg-gp-surface text-gp-ink-secondary'
                    }`}
                  >
                    <span
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                        chosen ? 'bg-gp-primary text-white' : 'bg-gp-bg text-gp-ink-secondary border border-gp-border'
                      }`}
                    >
                      {String.fromCharCode(65 + idx)}
                    </span>
                    <span>{opt}</span>
                  </button>
                );
              })}
            </div>

            <div className="pt-4 border-t border-gp-divider flex flex-wrap items-center justify-between gap-2">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setAnswers((prev) => ({
                      ...prev,
                      [q.id]: { ...ans, marked: !ans.marked },
                    }))
                  }
                  className={`px-3 py-1.5 rounded-lg border text-xs font-semibold flex items-center gap-1.5 ${
                    ans.marked
                      ? 'bg-gp-warning-bg border-gp-warning/30 text-gp-warning'
                      : 'bg-gp-surface border-gp-border text-gp-ink-secondary hover:bg-gp-bg'
                  }`}
                >
                  <Flag className="w-3.5 h-3.5" />
                  {ans.marked ? 'Marked for Review' : 'Mark for Review'}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setAnswers((prev) => ({
                      ...prev,
                      [q.id]: { ...ans, selected_index: null },
                    }))
                  }
                  className="gov-btn-ghost px-3 py-1.5 text-xs"
                >
                  Clear Response
                </button>
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={currentIdx === 0}
                  onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
                  className="gov-btn-secondary px-3.5 py-1.5 text-xs"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={currentIdx === activeTest.questions.length - 1}
                  onClick={() => setCurrentIdx((i) => Math.min(activeTest.questions.length - 1, i + 1))}
                  className="gov-btn-primary px-4 py-1.5 text-xs"
                >
                  Next Question
                </button>
              </div>
            </div>
          </div>

          {/* Question Navigation Palette */}
          <div className="lg:col-span-4 gov-card p-5">
            <h3 className="text-sm font-bold text-gp-ink mb-3">Question Navigator</h3>
            <div className="grid grid-cols-5 gap-2">
              {activeTest.questions.map((item: any, idx: number) => {
                const st = answers[item.id];
                const isCurr = idx === currentIdx;
                let cls = 'bg-gp-bg text-gp-ink-secondary border-gp-border';
                if (st?.marked) cls = 'bg-gp-warning-bg text-gp-warning border-gp-warning/30';
                else if (st?.selected_index !== null && st?.selected_index !== undefined)
                  cls = 'bg-gp-success-bg text-gp-success border-gp-success/30';
                return (
                  <button
                    key={item.id}
                    onClick={() => setCurrentIdx(idx)}
                    className={`py-2 rounded-lg border text-xs font-bold ${cls} ${
                      isCurr ? 'ring-2 ring-gp-primary' : ''
                    }`}
                  >
                    {idx + 1}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={mockMode ? 'Simulated Mock Tests' : 'Assessments & Diagnostics'}
        subtitle={
          mockMode
            ? 'Full-timed objective mock evaluations feeding weighted evidence into your Readiness & Error engines.'
            : 'Launch diagnostic baselines, topic quizzes, subject tests, or spaced revision checks.'
        }
      />

      {error && <ErrorBanner message={error} />}

      {/* Launch Assessment Builder */}
      <div className="gov-card p-5">
        <h2 className="text-base font-bold text-gp-ink mb-4">
          {mockMode ? 'Configure Simulated Mock Test' : 'Launch New Assessment'}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 items-end">
          <div>
            <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Target Exam</label>
            <select
              value={examId}
              onChange={(e) => setExamId(e.target.value)}
              className="gov-input w-full px-3 py-2 text-xs font-medium"
            >
              {EXAM_LIST.map((ex) => (
                <option key={ex.id} value={ex.id}>
                  {ex.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Assessment Type</label>
            <select
              value={assessmentType}
              onChange={(e) => setAssessmentType(e.target.value)}
              className="gov-input w-full px-3 py-2 text-xs font-medium"
            >
              <option value="diagnostic">Diagnostic Baseline</option>
              <option value="topic_quiz">Topic Quiz</option>
              <option value="subject_test">Subject Assessment</option>
              <option value="mock_test">Timed Mock Test</option>
              <option value="revision">Spaced Revision Check</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Subject Focus (Optional)</label>
            <select
              value={subjectId}
              onChange={(e) => {
                const nextSubj = e.target.value;
                setSubjectId(nextSubj);
                if (nextSubj && competencyId) {
                  const matched = competencies.find((c) => c.id === competencyId);
                  if (matched && matched.subject_id !== nextSubj) {
                    setCompetencyId('');
                  }
                }
              }}
              className="gov-input w-full px-3 py-2 text-xs font-medium"
            >
              <option value="">All Mapped Subjects</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Topic Focus (Optional)</label>
            <select
              value={competencyId}
              onChange={(e) => {
                const nextCid = e.target.value;
                setCompetencyId(nextCid);
                if (nextCid) {
                  const matched = competencies.find((c) => c.id === nextCid);
                  if (matched && matched.subject_id !== subjectId) {
                    setSubjectId(matched.subject_id);
                  }
                }
              }}
              className="gov-input w-full px-3 py-2 text-xs font-medium"
            >
              <option value="">All Topics in Scope</option>
              {competencies
                .filter((c) => !subjectId || c.subject_id === subjectId)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gp-ink-secondary mb-1">Questions</label>
            <select
              value={questionCount}
              onChange={(e) => setQuestionCount(Number(e.target.value))}
              className="gov-input w-full px-3 py-2 text-xs font-medium"
            >
              <option value={3}>3 Questions (~4 mins)</option>
              <option value={5}>5 Questions (~6 mins)</option>
              <option value={8}>8 Questions (~10 mins)</option>
              <option value={12}>12 Questions (~15 mins)</option>
              <option value={15}>15 Questions (~19 mins)</option>
              <option value={25}>25 Questions (~31 mins)</option>
            </select>
          </div>
          <button
            onClick={handleStart}
            className="gov-btn-primary py-2.5 px-4 text-xs"
          >
            <Play className="w-3.5 h-3.5" /> Start Assessment
          </button>
        </div>
        <p className="mt-2.5 text-[11px] text-gp-ink-muted">
          Questions are curated academic demonstration items mapped to competencies — clearly distinguished from official past-year question papers.
        </p>
      </div>

      {/* Assessment Result Review */}
      {reviewDetail && (
        <div className="gov-card p-6 space-y-5 border-gp-primary-border">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="text-xs font-semibold text-gp-primary uppercase">Assessment Breakdown</span>
              <h2 className="text-lg font-bold text-gp-ink">{reviewDetail.attempt.title}</h2>
            </div>
            <button
              onClick={() => setReviewDetail(null)}
              className="gov-btn-ghost px-3 py-1.5 text-xs"
            >
              Close Review
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <div className="p-3 rounded-lg bg-gp-primary-light border border-gp-primary-border">
              <div className="text-[11px] text-gp-primary font-semibold">Score</div>
              <div className="text-xl font-bold text-gp-ink">{reviewDetail.attempt.score_percent}%</div>
            </div>
            <div className="p-3 rounded-lg bg-gp-success-bg border border-gp-success/20">
              <div className="text-[11px] text-gp-success font-semibold">Correct</div>
              <div className="text-xl font-bold text-gp-success">{reviewDetail.attempt.correct_count}</div>
            </div>
            <div className="p-3 rounded-lg bg-gp-error-bg border border-gp-error/20">
              <div className="text-[11px] text-gp-error font-semibold">Incorrect</div>
              <div className="text-xl font-bold text-gp-error">{reviewDetail.attempt.incorrect_count}</div>
            </div>
            <div className="p-3 rounded-lg bg-gp-bg border border-gp-border">
              <div className="text-[11px] text-gp-ink-secondary font-semibold">Accuracy</div>
              <div className="text-xl font-bold text-gp-ink">{reviewDetail.attempt.accuracy_percent}%</div>
            </div>
            <div className="p-3 rounded-lg bg-gp-bg border border-gp-border">
              <div className="text-[11px] text-gp-ink-secondary font-semibold">Time Taken</div>
              <div className="text-xl font-bold text-gp-ink">{formatTime(reviewDetail.attempt.time_taken_sec)}</div>
            </div>
          </div>

          {/* Topic & Competency Performance */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-gp-bg border border-gp-border">
              <h3 className="text-xs font-bold uppercase text-gp-ink-secondary mb-2">Topic Performance</h3>
              <div className="space-y-1.5 text-xs">
                {reviewDetail.topic_performance.map((tp: any) => (
                  <div key={tp.topic} className="flex justify-between">
                    <span className="font-medium text-gp-ink">{tp.topic}</span>
                    <span className="font-mono font-semibold text-gp-primary">
                      {tp.correct}/{tp.total} ({tp.accuracy_percent}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="p-4 rounded-xl bg-gp-bg border border-gp-border">
              <h3 className="text-xs font-bold uppercase text-gp-ink-secondary mb-2">Competency Impact</h3>
              <div className="space-y-1.5 text-xs">
                {reviewDetail.competency_performance.map((cp: any) => (
                  <div key={cp.competency_id} className="flex justify-between">
                    <span className="font-medium text-gp-ink truncate pr-2">{cp.competency_name}</span>
                    <span className="font-mono font-semibold text-gp-primary shrink-0">
                      {cp.accuracy_percent}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Question-by-Question Review */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-gp-ink">Question-Level Review & Explanations</h3>
            {reviewDetail.questions.map((q: any, i: number) => (
              <div key={q.question_id} className="p-4 rounded-xl border border-gp-border bg-gp-surface space-y-2">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-bold text-gp-ink">
                    Q{i + 1} · {q.competency_name}
                  </span>
                  {q.is_correct ? (
                    <span className="inline-flex items-center gap-1 text-gp-success font-semibold">
                      <CheckCircle2 className="w-4 h-4" /> Correct ({q.time_spent_sec}s)
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-gp-error font-semibold">
                      <XCircle className="w-4 h-4" /> {q.error_category || 'Incorrect'} ({q.time_spent_sec}s)
                    </span>
                  )}
                </div>
                <p className="text-xs sm:text-sm text-gp-ink whitespace-pre-line">{q.prompt}</p>
                <div className="text-xs space-y-1">
                  <div className="text-gp-success font-semibold">
                    Correct Answer: {q.options[q.correct_index]}
                  </div>
                  {!q.is_correct && q.selected_index !== null && (
                    <div className="text-gp-error">Your Selection: {q.options[q.selected_index]}</div>
                  )}
                  <p className="text-gp-ink-secondary bg-gp-bg p-2.5 rounded-lg border border-gp-divider mt-1">
                    {q.explanation}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Attempt History */}
      <div className="gov-card p-5">
        <h2 className="text-base font-bold text-gp-ink mb-3">Assessment History</h2>
        {attempts.length === 0 ? (
          <p className="text-xs text-gp-ink-muted py-6 text-center">
            No assessments taken yet. Launch a Diagnostic Baseline above to populate your competency profile.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-gp-bg text-gp-ink-secondary border-b border-gp-border">
                <tr>
                  <th className="py-2.5 px-3">Assessment</th>
                  <th className="py-2.5 px-3">Exam</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Score</th>
                  <th className="py-2.5 px-3">Accuracy</th>
                  <th className="py-2.5 px-3">Questions</th>
                  <th className="py-2.5 px-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gp-divider">
                {attempts.map((a) => (
                  <tr key={a.id} className="hover:bg-gp-bg">
                    <td className="py-2.5 px-3 font-semibold text-gp-ink">
                      {a.title}{' '}
                      {a.is_demo_seed && (
                        <span className="ml-1 px-1.5 py-0.5 rounded bg-gp-bg border border-gp-border text-[10px] text-gp-ink-secondary">
                          Demo
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-gp-ink-secondary">{a.exam_short_name}</td>
                    <td className="py-2.5 px-3 capitalize text-gp-ink-secondary">{a.assessment_type.replace('_', ' ')}</td>
                    <td className="py-2.5 px-3 font-mono font-bold text-gp-primary">{a.score_percent}%</td>
                    <td className="py-2.5 px-3 font-mono text-gp-ink">{a.accuracy_percent}%</td>
                    <td className="py-2.5 px-3 font-mono text-gp-ink">
                      {a.correct_count}/{a.total_questions}
                    </td>
                    <td className="py-2.5 px-3">
                      <button
                        onClick={() => openAttemptReview(a.id)}
                        className="text-gp-primary hover:underline font-semibold inline-flex items-center gap-1"
                      >
                        <RotateCcw className="w-3 h-3" /> Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
