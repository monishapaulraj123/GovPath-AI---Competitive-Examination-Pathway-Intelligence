import React, { useEffect, useState } from 'react';
import { Check, Scale } from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader } from '../components/UI';

const EXAM_OPTIONS = [
  { id: 'UPSC_CSE', label: 'UPSC CSE' },
  { id: 'TNPSC_GRP1', label: 'TNPSC Group I' },
  { id: 'TNPSC_GRP2', label: 'TNPSC Group II/IIA' },
  { id: 'SSC_CGL', label: 'SSC CGL' },
  { id: 'SSC_CHSL', label: 'SSC CHSL' },
  { id: 'IBPS_PO', label: 'IBPS PO' },
  { id: 'RRB_NTPC', label: 'RRB NTPC' },
  { id: 'UPSC_CDS', label: 'UPSC CDS' },
];

export default function ExamComparePage() {
  const [selected, setSelected] = useState<string[]>(['UPSC_CSE', 'TNPSC_GRP1', 'SSC_CGL']);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async (ids: string[]) => {
    if (ids.length < 2) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.compareExams(ids);
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Comparison failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(selected);
  }, [selected]);

  const toggleExam = (id: string) => {
    if (selected.includes(id)) {
      if (selected.length <= 2) return;
      setSelected(selected.filter((x) => x !== id));
    } else {
      if (selected.length >= 4) return;
      setSelected([...selected, id]);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Exam Comparison"
        subtitle="Compare syllabus coverage, competency depth requirements, stages, readiness, and transferable overlap across 2 to 4 exams."
      />

      {/* Exam Selector */}
      <div className="gov-card p-4">
        <div className="text-xs font-semibold text-gp-ink-secondary mb-2.5 flex items-center gap-2">
          <Scale className="w-4 h-4 text-gp-primary" />
          Select 2–4 Examinations to Compare:
        </div>
        <div className="flex flex-wrap gap-2">
          {EXAM_OPTIONS.map((ex) => {
            const active = selected.includes(ex.id);
            return (
              <button
                key={ex.id}
                onClick={() => toggleExam(ex.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border flex items-center gap-1.5 transition ${
                  active
                    ? 'bg-gp-primary text-white border-gp-primary'
                    : 'bg-gp-surface text-gp-ink-secondary border-gp-border hover:border-gp-primary-border hover:text-gp-primary'
                }`}
              >
                {active && <Check className="w-3.5 h-3.5" />}
                {ex.label}
              </button>
            );
          })}
        </div>
      </div>

      {loading && <LoadingState label="Computing cross-exam comparison matrix..." />}
      {error && <ErrorBanner message={error} />}

      {!loading && data && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {data.exams.map((ex: any) => (
              <div key={ex.id} className="gov-card p-5 space-y-2.5">
                <div className="text-xs font-semibold text-gp-primary">{ex.category}</div>
                <h3 className="text-base font-bold text-gp-ink">{ex.short_name}</h3>
                <p className="text-xs text-gp-ink-muted">{ex.conducting_authority}</p>
                <div className="pt-2 border-t border-gp-divider space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gp-ink-secondary">Your Readiness</span>
                    <span className="font-bold text-gp-primary">{ex.readiness_index}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gp-ink-secondary">Weighted Gap</span>
                    <span className="font-semibold text-gp-ink">{ex.overall_gap} pts</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gp-ink-secondary">Recommended Study</span>
                    <span className="font-semibold text-gp-ink">{ex.recommended_daily_hours}h/day</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gp-ink-secondary">Stages</span>
                    <span className="font-semibold text-gp-ink">{ex.stages?.length || 0}</span>
                  </div>
                </div>
                <p className="text-[11px] text-gp-ink-muted pt-1">{ex.eligibility_summary}</p>
              </div>
            ))}
          </div>

          {/* Transfer Highlights */}
          {data.pairwise_transfer?.length > 0 && (
            <div className="gov-card p-5">
              <h2 className="text-base font-bold text-gp-ink mb-3">
                Transferable Knowledge from {data.exams[0]?.short_name}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {data.pairwise_transfer.map((pt: any) => (
                  <div key={pt.target_exam_id} className="p-4 rounded-xl bg-gp-bg border border-gp-border">
                    <div className="text-xs font-semibold text-gp-ink-secondary">Target: {pt.target_exam_name}</div>
                    <div className="text-2xl font-bold text-gp-primary mt-1">
                      {pt.structural_overlap_percent}% Overlap
                    </div>
                    <div className="text-xs text-gp-ink-secondary mt-1">
                      Effective Transfer: <strong className="text-gp-ink">{pt.effective_transfer_index}%</strong> · Bridge Estimate: ~
                      <strong className="text-gp-ink">{pt.estimated_additional_hours}h</strong>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Competency Matrix */}
          <div className="gov-card p-5">
            <h2 className="text-base font-bold text-gp-ink mb-3">Competency Depth Comparison Matrix</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-gp-bg text-gp-ink-secondary border-b border-gp-border">
                  <tr>
                    <th className="py-2.5 px-3">Competency</th>
                    <th className="py-2.5 px-3">Subject</th>
                    {data.exams.map((ex: any) => (
                      <th key={ex.id} className="py-2.5 px-3 text-center">
                        {ex.short_name} (Depth / Wt)
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gp-divider">
                  {data.competency_matrix.map((row: any) => (
                    <tr key={row.competency_id} className="hover:bg-gp-bg">
                      <td className="py-2.5 px-3 font-semibold text-gp-ink">{row.competency_name}</td>
                      <td className="py-2.5 px-3 text-gp-ink-secondary">{row.subject_name}</td>
                      {data.exams.map((ex: any) => {
                        const req = row.requirements[ex.id];
                        return (
                          <td key={ex.id} className="py-2.5 px-3 text-center">
                            {req ? (
                              <span className="inline-block px-2 py-0.5 rounded bg-gp-primary-light text-gp-primary border border-gp-primary-border font-mono font-semibold">
                                {req.required_depth} ({req.weightage_percent}%)
                              </span>
                            ) : (
                              <span className="text-gp-ink-muted">—</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
