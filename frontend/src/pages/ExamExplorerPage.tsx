import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  ExternalLink,
  Search,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader } from '../components/UI';

const CATEGORIES = [
  'All',
  'Civil Services',
  'State Civil Services',
  'Staff Selection & Central Group B/C',
  'Staff Selection & Clerical',
  'Banking & Financial Sector',
  'Railway Recruitment',
  'Defence Services',
];

export default function ExamExplorerPage() {
  const { examId } = useParams();
  const navigate = useNavigate();

  const [exams, setExams] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        if (examId) {
          const d = await api.getExam(examId);
          setDetail(d);
        } else {
          setDetail(null);
          const res = await api.listExams(search, category);
          setExams(res.exams || []);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load examination data');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [examId, search, category]);

  if (loading) return <LoadingState label="Loading examination intelligence..." />;
  if (error) return <ErrorBanner message={error} />;

  if (examId && detail) {
    return (
      <div className="space-y-6">
        <button
          onClick={() => navigate('/exams')}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-gp-primary hover:text-gp-primary-hover"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Exam Explorer
        </button>

        <PageHeader
          title={detail.name}
          subtitle={`${detail.conducting_authority} · ${detail.category}`}
          actions={
            <div className="flex gap-2">
              <button
                onClick={() => navigate(`/gap-analysis?exam=${detail.id}`)}
                className="gov-btn-secondary px-3.5 py-2 text-xs"
              >
                Analyze My Gaps
              </button>
              <button
                onClick={() => navigate(`/assessments`)}
                className="gov-btn-primary px-3.5 py-2 text-xs"
              >
                Take Exam Assessment
              </button>
            </div>
          }
        />

        <div className="rounded-xl border border-gp-warning/25 bg-gp-warning-bg p-4 flex items-start gap-3 text-xs text-gp-warning">
          <ShieldAlert className="w-4 h-4 text-gp-warning shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Official Verification Policy:</span> {detail.verification_note}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="gov-card p-5 space-y-3">
              <h2 className="text-base font-bold text-gp-ink">Overview & Eligibility</h2>
              <p className="text-sm text-gp-ink-secondary leading-relaxed">{detail.overview}</p>
              <div className="p-3.5 rounded-lg bg-gp-bg border border-gp-border text-xs text-gp-ink-secondary">
                <span className="font-semibold text-gp-ink">Eligibility Summary: </span>
                {detail.eligibility_summary}
              </div>
            </div>

            <div className="gov-card p-5">
              <h2 className="text-base font-bold text-gp-ink mb-3">Selection Stages & Pattern</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
                {(detail.stages || []).map((st: any, idx: number) => (
                  <div key={idx} className="p-3 rounded-lg bg-gp-bg border border-gp-border">
                    <div className="text-xs font-bold text-gp-primary">Stage {idx + 1}</div>
                    <div className="text-sm font-semibold text-gp-ink mt-0.5">{st.stage}</div>
                    <div className="text-xs text-gp-ink-secondary mt-1">{st.format}</div>
                    <div className="text-[11px] text-gp-ink-muted mt-1">{st.notes}</div>
                  </div>
                ))}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-gp-bg text-gp-ink-secondary border-b border-gp-border">
                    <tr>
                      <th className="py-2 px-3">Paper / Tier</th>
                      <th className="py-2 px-3">Questions</th>
                      <th className="py-2 px-3">Marks</th>
                      <th className="py-2 px-3">Duration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gp-divider">
                    {(detail.exam_pattern || []).map((p: any, i: number) => (
                      <tr key={i}>
                        <td className="py-2 px-3 font-semibold text-gp-ink">{p.paper}</td>
                        <td className="py-2 px-3 text-gp-ink-secondary">{p.questions}</td>
                        <td className="py-2 px-3 text-gp-ink-secondary">{p.marks}</td>
                        <td className="py-2 px-3 text-gp-ink-secondary">{p.duration}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="gov-card p-5">
              <h2 className="text-base font-bold text-gp-ink mb-3">Competency Syllabus Matrix & Your Alignment</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-gp-bg text-gp-ink-secondary border-b border-gp-border">
                    <tr>
                      <th className="py-2.5 px-3">Competency / Topic</th>
                      <th className="py-2.5 px-3">Exam Label</th>
                      <th className="py-2.5 px-3">Weight</th>
                      <th className="py-2.5 px-3">Required Depth</th>
                      <th className="py-2.5 px-3">Your Mastery</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gp-divider">
                    {(detail.syllabus_competencies || []).map((c: any) => (
                      <tr key={c.competency_id} className="hover:bg-gp-bg">
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-gp-ink">{c.competency_name}</div>
                          <div className="text-[11px] text-gp-ink-muted">{(c.subtopics || []).slice(0, 3).join(' · ')}</div>
                        </td>
                        <td className="py-2.5 px-3 text-gp-ink-secondary">{c.exam_subject_label}</td>
                        <td className="py-2.5 px-3 font-mono">{c.weightage_percent}%</td>
                        <td className="py-2.5 px-3 font-mono font-semibold text-gp-ink">{c.required_depth}</td>
                        <td className="py-2.5 px-3 font-mono font-semibold text-gp-primary">{c.student_mastery}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="gov-card p-5">
              <h3 className="text-sm font-bold text-gp-ink mb-3">Your Alignment Snapshot</h3>
              <div className="text-3xl font-bold text-gp-primary">
                {detail.readiness_alignment?.readiness_index}%
              </div>
              <p className="text-xs text-gp-ink-secondary mt-1">
                Measured alignment across {detail.readiness_alignment?.competency_coverage}% of mapped competencies.
              </p>
              <div className="mt-4 pt-4 border-t border-gp-divider text-xs space-y-2">
                <div className="flex justify-between">
                  <span className="text-gp-ink-secondary">Recommended Daily Hours</span>
                  <span className="font-semibold text-gp-ink">{detail.recommended_daily_hours} hrs/day</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gp-ink-secondary">Difficulty Index</span>
                  <span className="font-semibold text-gp-ink">{detail.difficulty_index}/100</span>
                </div>
              </div>
            </div>

            <div className="gov-card p-5">
              <h3 className="text-sm font-bold text-gp-ink mb-3">Recommended Core Resources</h3>
              <ul className="space-y-2 text-xs text-gp-ink-secondary">
                {(detail.preparation_resources || []).map((r: string, i: number) => (
                  <li key={i} className="flex items-start gap-2">
                    <BookOpen className="w-3.5 h-3.5 text-gp-primary shrink-0 mt-0.5" />
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="gov-card p-5">
              <h3 className="text-sm font-bold text-gp-ink mb-3">Official Portals</h3>
              <div className="space-y-2">
                {(detail.official_sources || []).map((s: any, i: number) => (
                  <a
                    key={i}
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-2.5 rounded-lg bg-gp-primary-light border border-gp-primary-border text-xs font-semibold text-gp-primary hover:bg-gp-primary-soft"
                  >
                    <span>{s.title}</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Exam Explorer"
        subtitle="Verified structural profiles, syllabus competencies, and student readiness alignment across major Indian government examinations."
      />

      {/* Search & Category Filters */}
      <div className="gov-card p-4 flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-gp-ink-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search UPSC, TNPSC, SSC, IBPS, Railway, Defence..."
            className="gov-input w-full pl-9 pr-4 py-2 text-sm"
          />
        </div>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="gov-input px-3 py-2 text-sm"
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      {/* Exam Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {exams.map((ex) => (
          <div
            key={ex.id}
            onClick={() => navigate(`/exams/${ex.id}`)}
            className="gov-card p-5 hover:border-gp-primary-border hover:bg-gp-primary-light/15 cursor-pointer transition flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="px-2.5 py-0.5 rounded-md bg-gp-primary-light text-gp-primary border border-gp-primary-border text-[11px] font-semibold">
                  {ex.category}
                </span>
                <span className="text-xs font-mono text-gp-ink-muted">{ex.stages_count} Stages</span>
              </div>
              <h3 className="text-base font-bold text-gp-ink">{ex.short_name}</h3>
              <p className="text-xs text-gp-ink-muted mt-0.5">{ex.conducting_authority}</p>
              <p className="text-xs text-gp-ink-secondary mt-3 line-clamp-3 leading-relaxed">{ex.overview}</p>
            </div>

            <div className="mt-5 pt-4 border-t border-gp-divider flex items-center justify-between">
              <div className="text-xs">
                <span className="text-gp-ink-secondary">Your Readiness: </span>
                <span className="font-bold text-gp-primary">{ex.student_readiness_index}%</span>
              </div>
              <span className="text-xs font-semibold text-gp-primary inline-flex items-center gap-1">
                Inspect <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </div>
          </div>
        ))}
      </div>

      {exams.length === 0 && (
        <div className="gov-card p-10 text-center text-sm text-gp-ink-secondary">
          <AlertCircle className="w-6 h-6 mx-auto mb-2 text-gp-ink-muted" />
          No examinations matched your filter criteria.
        </div>
      )}
    </div>
  );
}
