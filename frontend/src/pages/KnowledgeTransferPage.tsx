import React, { useEffect, useState } from 'react';
import { ArrowRight, Info } from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader, PriorityBadge, StatCard } from '../components/UI';

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

export default function KnowledgeTransferPage() {
  const [sourceExam, setSourceExam] = useState('UPSC_CSE');
  const [targetExam, setTargetExam] = useState('TNPSC_GRP1');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async (src: string, tgt: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getKnowledgeTransfer(src, tgt);
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Transfer calculation failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(sourceExam, targetExam);
  }, [sourceExam, targetExam]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Transfer Analysis"
        subtitle="Graph-driven evaluation of transferable competencies, depth mismatches, and additional bridge effort between examinations."
      />

      {/* Source -> Target Selector */}
      <div className="gov-card p-5 flex flex-wrap items-center gap-4">
        <div>
          <label className="block text-[11px] font-semibold text-gp-ink-secondary mb-1">
            Source Examination (Prepared For)
          </label>
          <select
            value={sourceExam}
            onChange={(e) => setSourceExam(e.target.value)}
            className="gov-input px-3.5 py-2 text-sm font-semibold"
          >
            {EXAM_LIST.map((ex) => (
              <option key={ex.id} value={ex.id}>{ex.label}</option>
            ))}
          </select>
        </div>

        <ArrowRight className="w-5 h-5 text-gp-primary mt-5 hidden sm:block" />

        <div>
          <label className="block text-[11px] font-semibold text-gp-ink-secondary mb-1">
            Target Examination (Evaluating Transfer To)
          </label>
          <select
            value={targetExam}
            onChange={(e) => setTargetExam(e.target.value)}
            className="gov-input px-3.5 py-2 text-sm font-semibold"
          >
            {EXAM_LIST.map((ex) => (
              <option key={ex.id} value={ex.id}>{ex.label}</option>
            ))}
          </select>
        </div>
      </div>

      {loading && <LoadingState label="Analyzing graph overlap & depth deltas..." />}
      {error && <ErrorBanner message={error} />}

      {!loading && data && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Structural Graph Overlap"
              value={`${data.structural_overlap_percent}%`}
              subtext="Shared competencies in syllabus"
              accent="primary"
            />
            <StatCard
              label="Effective Student Transfer"
              value={`${data.effective_transfer_index}%`}
              subtext="Weighted by demonstrated mastery"
              accent="success"
            />
            <StatCard
              label="Fully / Partially Transferable"
              value={
                (data.classification_counts['Fully Transferable'] || 0) +
                (data.classification_counts['Partially Transferable'] || 0)
              }
              subtext={`${data.classification_counts['Not Covered'] || 0} newly required`}
              accent="primary"
            />
            <StatCard
              label="Model-Estimated Bridge Effort"
              value={`~${data.estimated_additional_hours} hrs`}
              subtext="Transparent depth-gap approximation"
              accent="warning"
            />
          </div>

          <div className="gov-card p-4 bg-gp-primary-light/50 border-gp-primary-border flex items-start gap-3 text-xs text-gp-ink-secondary">
            <Info className="w-4 h-4 text-gp-primary shrink-0 mt-0.5" />
            <span>{data.effort_model_note}</span>
          </div>

          <div className="gov-card p-5">
            <h2 className="text-base font-bold text-gp-ink mb-3">
              Competency Transfer Classification ({data.source_exam_name} → {data.target_exam_name})
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-gp-bg text-gp-ink-secondary border-b border-gp-border">
                  <tr>
                    <th className="py-2.5 px-3">Competency</th>
                    <th className="py-2.5 px-3">Classification</th>
                    <th className="py-2.5 px-3">Source Depth</th>
                    <th className="py-2.5 px-3">Target Depth</th>
                    <th className="py-2.5 px-3">Your Mastery</th>
                    <th className="py-2.5 px-3">Depth Δ</th>
                    <th className="py-2.5 px-3">Est. Effort</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gp-divider">
                  {data.competencies.map((c: any) => (
                    <tr key={c.competency_id} className="hover:bg-gp-bg">
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-gp-ink">{c.competency_name}</div>
                        <div className="text-[11px] text-gp-ink-muted">
                          {c.topic_name} · Weight {c.weightage_percent}%
                        </div>
                      </td>
                      <td className="py-2.5 px-3"><PriorityBadge priority={c.classification} /></td>
                      <td className="py-2.5 px-3 font-mono text-gp-ink">{c.source_required_depth || '—'}</td>
                      <td className="py-2.5 px-3 font-mono text-gp-ink">{c.target_required_depth}</td>
                      <td className="py-2.5 px-3 font-mono font-semibold text-gp-primary">{c.student_mastery}</td>
                      <td className="py-2.5 px-3 font-mono text-gp-ink">
                        {c.depth_mismatch > 0 ? `+${c.depth_mismatch}` : c.depth_mismatch}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-gp-ink">~{c.estimated_additional_hours}h</td>
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
