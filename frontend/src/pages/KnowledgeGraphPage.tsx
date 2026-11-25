import React, { useEffect, useMemo, useState } from 'react';
import { Network } from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader } from '../components/UI';
import { GOVPATH_COLORS } from '../theme/colors';

export default function KnowledgeGraphPage() {
  const [graph, setGraph] = useState<any>(null);
  const [examFilter, setExamFilter] = useState('UPSC_CSE');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [nodeDetail, setNodeDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await api.getKnowledgeGraph(examFilter || undefined, subjectFilter || undefined);
        setGraph(res);
        setSelectedNode(null);
        setNodeDetail(null);
      } catch (err: any) {
        setError(err.message || 'Failed to load Competency Knowledge Graph');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [examFilter, subjectFilter]);

  const handleSelectNode = async (node: any) => {
    setSelectedNode(node);
    if (node.node_type === 'Competency') {
      const detail = await api.getCompetencyNode(node.raw_id);
      setNodeDetail(detail);
    } else {
      setNodeDetail(null);
    }
  };

  // Compute structured 4-column hierarchical layout (Exam -> Subject -> Topic -> Competency)
  const layout = useMemo(() => {
    if (!graph) return { positioned: [], posMap: {} as Record<string, { x: number; y: number }>, height: 520 };
    const groups: Record<string, any[]> = { Exam: [], Subject: [], Topic: [], Competency: [] };
    for (const n of graph.nodes) {
      if (groups[n.node_type]) groups[n.node_type].push(n);
    }

    const colX: Record<string, number> = { Exam: 90, Subject: 320, Topic: 570, Competency: 840 };
    const maxCount = Math.max(
      groups.Exam.length,
      groups.Subject.length,
      groups.Topic.length,
      groups.Competency.length,
      6
    );
    const height = Math.max(540, maxCount * 54 + 60);
    const posMap: Record<string, { x: number; y: number }> = {};
    const positioned: any[] = [];

    (['Exam', 'Subject', 'Topic', 'Competency'] as const).forEach((col) => {
      const list = groups[col];
      const step = height / (list.length + 1);
      list.forEach((node, idx) => {
        const pos = { x: colX[col], y: Math.round((idx + 1) * step) };
        posMap[node.id] = pos;
        positioned.push({ ...node, ...pos });
      });
    });

    return { positioned, posMap, height };
  }, [graph]);

  const nodeColor = (node: any) => {
    if (node.node_type === 'Exam') return GOVPATH_COLORS.primaryActive; // #613774
    if (node.node_type === 'Subject') return GOVPATH_COLORS.primary; // #83529B
    if (node.node_type === 'Topic') return GOVPATH_COLORS.textSecondary; // #6B6674 (neutral)
    if (node.student_score >= 70) return GOVPATH_COLORS.success; // semantic green for strong mastery
    return '#A47DB5';
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Competency Knowledge Graph"
        subtitle="Interactive Exam → Subject → Topic → Competency graph powering Knowledge Transfer and Gap Analysis."
      />

      {/* Controls */}
      <div className="gov-card p-4 flex flex-wrap items-center gap-4">
        <div>
          <label className="block text-[11px] font-semibold text-gp-ink-secondary mb-1">Exam Subgraph</label>
          <select
            value={examFilter}
            onChange={(e) => setExamFilter(e.target.value)}
            className="gov-input px-3 py-1.5 text-xs font-medium"
          >
            <option value="">All Examinations</option>
            <option value="UPSC_CSE">UPSC CSE</option>
            <option value="TNPSC_GRP1">TNPSC Group I</option>
            <option value="TNPSC_GRP2">TNPSC Group II/IIA</option>
            <option value="SSC_CGL">SSC CGL</option>
            <option value="SSC_CHSL">SSC CHSL</option>
            <option value="IBPS_PO">IBPS PO</option>
            <option value="RRB_NTPC">RRB NTPC</option>
            <option value="UPSC_CDS">UPSC CDS</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-semibold text-gp-ink-secondary mb-1">Subject Filter</label>
          <select
            value={subjectFilter}
            onChange={(e) => setSubjectFilter(e.target.value)}
            className="gov-input px-3 py-1.5 text-xs font-medium"
          >
            <option value="">All Subjects</option>
            <option value="POLITY">Indian Polity</option>
            <option value="ECONOMY">Indian Economy</option>
            <option value="HISTORY">History & Culture</option>
            <option value="GEOGRAPHY">Geography & Environment</option>
            <option value="SCIENCE_TECH">Science & Tech</option>
            <option value="CURRENT_AFFAIRS">Current Affairs</option>
            <option value="QUANT">Quantitative Aptitude</option>
            <option value="REASONING">Reasoning</option>
            <option value="ENGLISH">English</option>
            <option value="STATE_TN">Tamil Nadu Heritage & Admin</option>
          </select>
        </div>

        {graph?.stats && (
          <div className="ml-auto flex flex-wrap gap-2 text-xs">
            <span className="px-2.5 py-1 rounded-md bg-gp-bg border border-gp-border text-gp-ink-secondary font-medium">
              {graph.stats.exam_count} Exams · {graph.stats.subject_count} Subjects · {graph.stats.competency_count} Competencies
            </span>
            <span className="px-2.5 py-1 rounded-md bg-gp-primary-light border border-gp-primary-border text-gp-primary font-medium">
              {graph.stats.edge_count} Graph Edges
            </span>
          </div>
        )}
      </div>

      {loading && <LoadingState label="Traversing competency knowledge graph..." />}
      {error && <ErrorBanner message={error} />}

      {!loading && graph && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Graph SVG Canvas */}
          <div className="lg:col-span-8 gov-card p-4 overflow-x-auto">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-gp-ink-secondary mb-2 px-2">
              <div className="flex flex-wrap items-center gap-4">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: GOVPATH_COLORS.primaryActive }} /> Exam
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: GOVPATH_COLORS.primary }} /> Subject
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: GOVPATH_COLORS.textSecondary }} /> Topic
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: '#A47DB5' }} /> Competency
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: GOVPATH_COLORS.success }} /> Mastery ≥ 70%
                </span>
              </div>
              <span>Click any node to inspect links</span>
            </div>

            <svg width="1020" height={layout.height} className="w-full min-w-[780px]">
              {/* Edges */}
              {graph.edges.map((e: any) => {
                const s = layout.posMap[e.source];
                const t = layout.posMap[e.target];
                if (!s || !t) return null;
                const isSelected = selectedNode && (selectedNode.id === e.source || selectedNode.id === e.target);
                const isPrereq = e.edge_type === 'PREREQUISITE_OF';
                return (
                  <line
                    key={e.id}
                    x1={s.x}
                    y1={s.y}
                    x2={t.x}
                    y2={t.y}
                    stroke={
                      isSelected
                        ? GOVPATH_COLORS.primary
                        : isPrereq
                        ? GOVPATH_COLORS.warning
                        : GOVPATH_COLORS.primaryBorder
                    }
                    strokeWidth={isSelected ? 2.2 : 1.1}
                    strokeDasharray={isPrereq ? '4 3' : undefined}
                    opacity={selectedNode && !isSelected ? 0.25 : 0.78}
                  />
                );
              })}

              {/* Nodes */}
              {layout.positioned.map((n: any) => {
                const isSelected = selectedNode?.id === n.id;
                const fill = isSelected ? GOVPATH_COLORS.primary : nodeColor(n);
                const label = n.label.length > 26 ? n.label.slice(0, 24) + '…' : n.label;
                return (
                  <g
                    key={n.id}
                    transform={`translate(${n.x}, ${n.y})`}
                    onClick={() => handleSelectNode(n)}
                    className="cursor-pointer"
                  >
                    <circle
                      r={isSelected ? 11 : 8}
                      fill={fill}
                      stroke={isSelected ? GOVPATH_COLORS.primaryActive : '#FFFFFF'}
                      strokeWidth={2.5}
                    />
                    <rect
                      x={14}
                      y={-12}
                      width={Math.min(185, label.length * 6.4 + 14)}
                      height={24}
                      rx={6}
                      fill={isSelected ? GOVPATH_COLORS.primarySoft : '#FFFFFF'}
                      stroke={isSelected ? GOVPATH_COLORS.primary : GOVPATH_COLORS.border}
                    />
                    <text
                      x={21}
                      y={4}
                      fontSize="11"
                      fontWeight={isSelected ? '700' : '500'}
                      fill={isSelected ? GOVPATH_COLORS.primary : GOVPATH_COLORS.textPrimary}
                    >
                      {label}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Node Inspector */}
          <div className="lg:col-span-4 gov-card p-5 space-y-4">
            <div className="flex items-center gap-2 text-sm font-bold text-gp-ink">
              <Network className="w-4 h-4 text-gp-primary" />
              Node Inspector
            </div>
            {!selectedNode ? (
              <p className="text-xs text-gp-ink-secondary leading-relaxed">
                Select any Exam, Subject, Topic, or Competency node on the graph to inspect cross-exam depth requirements,
                prerequisites, and your demonstrated mastery.
              </p>
            ) : (
              <div className="space-y-3 text-xs">
                <span className="inline-block px-2 py-0.5 rounded bg-gp-primary-light text-gp-primary border border-gp-primary-border font-semibold">
                  {selectedNode.node_type}
                </span>
                <h3 className="text-base font-bold text-gp-ink">{selectedNode.full_label || selectedNode.label}</h3>

                {selectedNode.node_type === 'Competency' && (
                  <>
                    <div className="p-3 rounded-lg bg-gp-bg border border-gp-border flex justify-between">
                      <span className="text-gp-ink-secondary">Your Demonstrated Mastery</span>
                      <span className="font-bold text-gp-primary">{selectedNode.student_score}%</span>
                    </div>

                    {nodeDetail && (
                      <>
                        <div>
                          <div className="font-semibold text-gp-ink mb-1">Subtopics</div>
                          <div className="flex flex-wrap gap-1.5">
                            {(nodeDetail.subtopics || []).map((st: string) => (
                              <span
                                key={st}
                                className="px-2 py-0.5 rounded bg-gp-bg border border-gp-border text-gp-ink-secondary"
                              >
                                {st}
                              </span>
                            ))}
                          </div>
                        </div>

                        <div>
                          <div className="font-semibold text-gp-ink mb-1">Required Across Exams</div>
                          <div className="space-y-1.5">
                            {(nodeDetail.required_by_exams || []).map((ex: any) => (
                              <div
                                key={ex.exam_id}
                                className="flex justify-between p-2 rounded bg-gp-bg border border-gp-border"
                              >
                                <span className="font-medium text-gp-ink">{ex.exam_name}</span>
                                <span className="font-mono text-gp-primary">
                                  Depth {ex.required_depth} ({ex.weightage_percent}%)
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
