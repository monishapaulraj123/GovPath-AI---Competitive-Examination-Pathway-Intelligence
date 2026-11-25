import React, { useEffect, useRef, useState } from 'react';
import {
  Bot,
  CheckCircle2,
  Cpu,
  ExternalLink,
  FilePlus2,
  MessageSquarePlus,
  Send,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { api } from '../api/client';
import { LoadingState, MarkdownProse, PageHeader } from '../components/UI';

const SUGGESTED_PROMPTS = [
  'Can my UPSC preparation transfer to TNPSC Group I?',
  'What are my biggest preparation gaps right now?',
  'Why am I losing marks in recent assessments?',
  'How can I prepare effectively with 3 hours per day?',
  'What should I revise today based on my retention tracker?',
  'Compare UPSC CSE and SSC CGL pathways.',
];

export default function CounsellorPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [llmStatus, setLlmStatus] = useState<any>(null);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [appliedMsgId, setAppliedMsgId] = useState<number | null>(null);
  const [showIngest, setShowIngest] = useState(false);
  const [ragDocs, setRagDocs] = useState<any[]>([]);
  const [docForm, setDocForm] = useState({
    title: '',
    exam_id: 'UPSC_CSE',
    source_name: '',
    source_url: '',
    content: '',
  });
  const [ingestStatus, setIngestStatus] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadSessions = async () => {
    setLoading(true);
    try {
      const res = await api.listChatSessions();
      setSessions(res.sessions || []);
      setLlmStatus(res.llm_status);
      if (res.sessions?.length > 0 && !activeSessionId) {
        const detail = await api.getChatSession(res.sessions[0].id);
        setActiveSessionId(detail.id);
        setMessages(detail.messages || []);
      }
      const docsRes = await api.listRagDocuments();
      setRagDocs(docsRes.documents || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  const selectSession = async (id: number) => {
    setActiveSessionId(id);
    const detail = await api.getChatSession(id);
    setMessages(detail.messages || []);
  };

  const handleNewSession = async () => {
    const res = await api.createChatSession();
    setActiveSessionId(res.id);
    setMessages([]);
    const listRes = await api.listChatSessions();
    setSessions(listRes.sessions || []);
  };

  const handleDeleteSession = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    await api.deleteChatSession(id);
    const listRes = await api.listChatSessions();
    setSessions(listRes.sessions || []);
    if (activeSessionId === id) {
      if (listRes.sessions?.length > 0) {
        selectSession(listRes.sessions[0].id);
      } else {
        setActiveSessionId(null);
        setMessages([]);
      }
    }
  };

  const handleSend = async (promptText?: string) => {
    const text = (promptText ?? input).trim();
    if (!text || sending) return;
    setInput('');
    setSending(true);

    const optimisticUser = {
      id: Date.now(),
      role: 'user',
      content: text,
      citations: [],
      agent_trace: [],
    };
    setMessages((prev) => [...prev, optimisticUser]);

    try {
      const res = await api.sendChat(text, activeSessionId ?? undefined);
      setActiveSessionId(res.session_id);
      setMessages((prev) => [...prev, res.message]);
      const listRes = await api.listChatSessions();
      setSessions(listRes.sessions || []);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'assistant',
          content: `Error communicating with Agent Orchestrator: ${err.message}`,
          citations: [],
          agent_trace: [],
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleApplyProposal = async (msgId: number, proposal: any) => {
    await api.applyProposal(proposal.proposal_type, proposal.payload);
    setAppliedMsgId(msgId);
  };

  const handleIngestDoc = async (e: React.FormEvent) => {
    e.preventDefault();
    setIngestStatus('Indexing chunks into RAG vector store...');
    try {
      const res = await api.ingestRagDocument(docForm);
      setIngestStatus(`Indexed "${res.title}" (${res.chunk_count} chunks).`);
      setDocForm({ title: '', exam_id: 'UPSC_CSE', source_name: '', source_url: '', content: '' });
      const docsRes = await api.listRagDocuments();
      setRagDocs(docsRes.documents || []);
    } catch (err: any) {
      setIngestStatus(`Failed: ${err.message}`);
    }
  };

  if (loading) return <LoadingState label="Initializing Agentic AI Counsellor..." />;

  return (
    <div className="space-y-4">
      <PageHeader
        title="AI Counsellor"
        subtitle="Multi-agent guidance grounded in your readiness profile, competency graph, and verified RAG documents."
        actions={
          <div className="flex items-center gap-2">
            <span className="px-3 py-1.5 rounded-lg bg-gp-primary-light border border-gp-primary-border text-xs font-medium text-gp-primary flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-gp-primary" />
              {llmStatus?.configured ? `${llmStatus.provider} (${llmStatus.model})` : 'Grounded Synthesis Mode'}
            </span>
            <button
              onClick={() => setShowIngest(!showIngest)}
              className="gov-btn-secondary px-3 py-1.5 text-xs"
            >
              <FilePlus2 className="w-3.5 h-3.5" />
              RAG Knowledge Base ({ragDocs.length})
            </button>
          </div>
        }
      />

      {showIngest && (
        <div className="gov-card p-5 grid grid-cols-1 lg:grid-cols-2 gap-6">
          <form onSubmit={handleIngestDoc} className="space-y-3">
            <h3 className="text-sm font-bold text-gp-ink">Ingest Official Syllabus / Reference Document</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                required
                placeholder="Document Title"
                value={docForm.title}
                onChange={(e) => setDocForm({ ...docForm, title: e.target.value })}
                className="gov-input px-3 py-2 text-xs"
              />
              <select
                value={docForm.exam_id}
                onChange={(e) => setDocForm({ ...docForm, exam_id: e.target.value })}
                className="gov-input px-3 py-2 text-xs"
              >
                <option value="UPSC_CSE">UPSC CSE</option>
                <option value="TNPSC_GRP1">TNPSC Group I</option>
                <option value="TNPSC_GRP2">TNPSC Group II/IIA</option>
                <option value="SSC_CGL">SSC CGL</option>
                <option value="IBPS_PO">IBPS PO</option>
                <option value="RRB_NTPC">RRB NTPC</option>
                <option value="UPSC_CDS">UPSC CDS</option>
              </select>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                required
                placeholder="Source Organization (e.g. UPSC / PIB)"
                value={docForm.source_name}
                onChange={(e) => setDocForm({ ...docForm, source_name: e.target.value })}
                className="gov-input px-3 py-2 text-xs"
              />
              <input
                placeholder="Official URL (optional)"
                value={docForm.source_url}
                onChange={(e) => setDocForm({ ...docForm, source_url: e.target.value })}
                className="gov-input px-3 py-2 text-xs"
              />
            </div>
            <textarea
              required
              rows={3}
              placeholder="Paste verified syllabus text, eligibility rules, or study notes (min 30 chars)..."
              value={docForm.content}
              onChange={(e) => setDocForm({ ...docForm, content: e.target.value })}
              className="gov-input w-full px-3 py-2 text-xs"
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-gp-primary font-medium">{ingestStatus}</span>
              <button type="submit" className="gov-btn-primary px-4 py-2 text-xs">
                Chunk & Index Document
              </button>
            </div>
          </form>

          <div>
            <h3 className="text-sm font-bold text-gp-ink mb-2">Indexed RAG Corpus</h3>
            <div className="max-h-56 overflow-y-auto space-y-2 pr-1">
              {ragDocs.map((d) => (
                <div key={d.id} className="p-2.5 rounded-lg bg-gp-bg border border-gp-border text-xs">
                  <div className="font-semibold text-gp-ink">{d.title}</div>
                  <div className="text-gp-ink-secondary mt-0.5">
                    {d.source_name} · {d.chunk_count} chunks · {d.verified_status}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Main Split Chat Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 min-h-[640px]">
        {/* Left Sessions Rail */}
        <div className="lg:col-span-3 gov-card p-3 flex flex-col">
          <button
            onClick={handleNewSession}
            className="gov-btn-primary w-full py-2.5 px-3 text-xs mb-3"
          >
            <MessageSquarePlus className="w-4 h-4" />
            New Conversation
          </button>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-gp-ink-muted px-2 mb-2">
            Saved Sessions
          </div>
          <div className="flex-1 overflow-y-auto space-y-1">
            {sessions.map((s) => (
              <div
                key={s.id}
                onClick={() => selectSession(s.id)}
                className={`group px-3 py-2.5 rounded-lg cursor-pointer flex items-center justify-between gap-2 text-xs transition ${
                  activeSessionId === s.id
                    ? 'bg-gp-primary-soft text-gp-primary font-semibold border border-gp-primary-border'
                    : 'text-gp-ink-secondary hover:bg-gp-bg hover:text-gp-ink'
                }`}
              >
                <span className="truncate">{s.title}</span>
                <button
                  onClick={(e) => handleDeleteSession(s.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-gp-ink-muted hover:text-gp-error p-0.5"
                  title="Delete conversation"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Right Conversation Thread */}
        <div className="lg:col-span-9 gov-card flex flex-col overflow-hidden h-[660px]">
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {messages.length === 0 && (
              <div className="py-10 text-center max-w-xl mx-auto">
                <div className="w-12 h-12 rounded-2xl bg-gp-primary-light text-gp-primary border border-gp-primary-border flex items-center justify-center mx-auto mb-3">
                  <Bot className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-gp-ink">Ask GovPath AI Counsellor</h3>
                <p className="text-xs text-gp-ink-secondary mt-1 mb-5">
                  Every answer invokes specialized backend agents across your assessment evidence, competency graph, and RAG knowledge base.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
                  {SUGGESTED_PROMPTS.map((p) => (
                    <button
                      key={p}
                      onClick={() => handleSend(p)}
                      className="p-3 rounded-lg border border-gp-border hover:border-gp-primary-border hover:bg-gp-primary-light/40 text-xs font-medium text-gp-ink transition"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-3xl rounded-2xl px-4 py-3.5 ${
                    m.role === 'user'
                      ? 'bg-gp-primary text-white text-sm'
                      : 'bg-gp-bg border border-gp-border text-gp-ink'
                  }`}
                >
                  {m.role === 'user' ? (
                    <p>{m.content}</p>
                  ) : (
                    <div className="space-y-3">
                      <MarkdownProse content={m.content} />

                      {/* Agent Execution Trace */}
                      {m.agent_trace?.length > 0 && (
                        <div className="pt-2 border-t border-gp-divider">
                          <div className="text-[10px] font-semibold uppercase tracking-wider text-gp-ink-muted mb-1.5">
                            Agent Orchestrator Trace
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {m.agent_trace.map((tr: any, i: number) => (
                              <span
                                key={i}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-gp-primary-light border border-gp-primary-border text-[11px] font-medium text-gp-primary"
                              >
                                <Sparkles className="w-3 h-3" />
                                {tr.agent}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Confirmable State Proposal */}
                      {m.proposed_action && (
                        <div className="p-3 rounded-xl bg-gp-primary-light border border-gp-primary-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                          <div>
                            <div className="text-xs font-bold text-gp-ink">{m.proposed_action.label}</div>
                            <div className="text-[11px] text-gp-ink-secondary">{m.proposed_action.description}</div>
                          </div>
                          {appliedMsgId === m.id ? (
                            <span className="inline-flex items-center gap-1 text-xs font-semibold text-gp-success shrink-0">
                              <CheckCircle2 className="w-4 h-4" /> Plan Activated
                            </span>
                          ) : (
                            <button
                              onClick={() => handleApplyProposal(m.id, m.proposed_action)}
                              className="gov-btn-primary px-3 py-1.5 text-xs shrink-0"
                            >
                              Confirm & Apply
                            </button>
                          )}
                        </div>
                      )}

                      {/* RAG Source Citations */}
                      {m.citations?.length > 0 && (
                        <div className="pt-2 border-t border-gp-divider">
                          <div className="text-[10px] font-semibold uppercase tracking-wider text-gp-ink-muted mb-1.5">
                            Verified RAG Sources
                          </div>
                          <div className="space-y-1.5">
                            {m.citations.map((c: any, idx: number) => (
                              <div key={idx} className="p-2 rounded-lg bg-gp-surface border border-gp-border text-[11px]">
                                <div className="flex items-center justify-between gap-2 font-semibold text-gp-ink">
                                  <span>{c.title}</span>
                                  {c.source_url && (
                                    <a
                                      href={c.source_url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="text-gp-primary hover:underline inline-flex items-center gap-1 shrink-0"
                                    >
                                      Portal <ExternalLink className="w-3 h-3" />
                                    </a>
                                  )}
                                </div>
                                <div className="text-gp-ink-secondary mt-0.5">
                                  {c.source_name} · {c.verified_status}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {sending && (
              <div className="flex justify-start">
                <div className="rounded-2xl px-4 py-3 bg-gp-bg border border-gp-border text-xs text-gp-ink-secondary flex items-center gap-2">
                  <Sparkles className="w-4 h-4 animate-pulse text-gp-primary" />
                  Orchestrating specialized agents & querying competency graph...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Quick Prompt Bar + Input */}
          <div className="p-4 border-t border-gp-border bg-gp-surface space-y-2.5">
            {messages.length > 0 && (
              <div className="flex gap-2 overflow-x-auto pb-1">
                {SUGGESTED_PROMPTS.slice(0, 4).map((p) => (
                  <button
                    key={p}
                    onClick={() => handleSend(p)}
                    className="shrink-0 px-2.5 py-1 rounded-full bg-gp-bg hover:bg-gp-primary-light hover:text-gp-primary text-[11px] font-medium text-gp-ink-secondary border border-gp-border transition"
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex gap-2"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about exam transfer, readiness gaps, study schedules, or syllabus comparisons..."
                className="gov-input flex-1 px-4 py-2.5 text-sm rounded-xl"
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="gov-btn-primary px-4 py-2.5 rounded-xl text-sm"
              >
                <Send className="w-4 h-4" />
                Send
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
