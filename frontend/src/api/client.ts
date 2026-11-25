const API_BASE = '/api';

export function getToken(): string | null {
  return localStorage.getItem('govpath_token');
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem('govpath_token', token);
  } else {
    localStorage.removeItem('govpath_token');
  }
}

export async function apiRequest<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event('govpath:unauthorized'));
    const err = await res.json().catch(() => ({ detail: 'Authentication required' }));
    throw new Error(err.detail || 'Authentication required');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Request failed (${res.status})` }));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }

  return res.json();
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    apiRequest('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  register: (data: { email: string; password: string; full_name: string; primary_target_exam: string }) =>
    apiRequest('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  demoLogin: () => apiRequest('/auth/demo', { method: 'POST' }),
  me: () => apiRequest('/auth/me'),

  // Dashboard & Profile
  dashboard: () => apiRequest('/dashboard'),
  getProfile: () => apiRequest('/profile'),
  updateProfile: (data: Record<string, any>) =>
    apiRequest('/profile', { method: 'PUT', body: JSON.stringify(data) }),

  // Exams & Graph
  listExams: (search = '', category = 'all') =>
    apiRequest(`/exams?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}`),
  getExam: (examId: string) => apiRequest(`/exams/${examId}`),
  compareExams: (examIds: string[]) =>
    apiRequest(`/exams/compare?exam_ids=${encodeURIComponent(examIds.join(','))}`),
  getKnowledgeGraph: (examId?: string, subjectId?: string) => {
    const params = new URLSearchParams();
    if (examId) params.set('exam_id', examId);
    if (subjectId) params.set('subject_id', subjectId);
    const qs = params.toString();
    return apiRequest(`/knowledge-graph${qs ? `?${qs}` : ''}`);
  },
  getCompetencyNode: (compId: string) => apiRequest(`/knowledge-graph/competency/${compId}`),

  // Assessments & Practice
  listAssessments: () => apiRequest('/assessments'),
  startAssessment: (data: {
    exam_id: string;
    assessment_type: string;
    subject_id?: string;
    competency_id?: string;
    question_count?: number;
    time_limit_sec?: number;
  }) => apiRequest('/assessments/start', { method: 'POST', body: JSON.stringify(data) }),
  submitAssessment: (attemptId: number, data: { answers: any[]; total_time_sec: number }) =>
    apiRequest(`/assessments/${attemptId}/submit`, { method: 'POST', body: JSON.stringify(data) }),
  getAssessmentDetail: (attemptId: number) => apiRequest(`/assessments/${attemptId}`),
  listPracticeQuestions: (mode = 'all', subjectId = 'ALL', competencyId = '') => {
    const params = new URLSearchParams({ mode, subject_id: subjectId });
    if (competencyId) params.set('competency_id', competencyId);
    return apiRequest(`/practice/questions?${params.toString()}`);
  },
  toggleSaveQuestion: (questionId: string, note = '') =>
    apiRequest('/practice/save', { method: 'POST', body: JSON.stringify({ question_id: questionId, note }) }),

  // Intelligence Engines
  getReadiness: (examId?: string) =>
    apiRequest(`/readiness${examId ? `?exam_id=${encodeURIComponent(examId)}` : ''}`),
  getGapAnalysis: (examId?: string) =>
    apiRequest(`/gap-analysis${examId ? `?exam_id=${encodeURIComponent(examId)}` : ''}`),
  getKnowledgeTransfer: (sourceExamId: string, targetExamId: string) =>
    apiRequest(
      `/knowledge-transfer?source_exam_id=${encodeURIComponent(sourceExamId)}&target_exam_id=${encodeURIComponent(targetExamId)}`
    ),
  getDiagnosis: () => apiRequest('/diagnosis'),
  getRetention: (examId?: string) =>
    apiRequest(`/retention${examId ? `?exam_id=${encodeURIComponent(examId)}` : ''}`),
  getAnalytics: (examId?: string, subjectId?: string) => {
    const params = new URLSearchParams();
    if (examId) params.set('exam_id', examId);
    if (subjectId) params.set('subject_id', subjectId);
    const qs = params.toString();
    return apiRequest(`/analytics${qs ? `?${qs}` : ''}`);
  },

  // Planning & Simulator
  getPathways: () => apiRequest('/pathways'),
  getStudyPlan: () => apiRequest('/study-plan'),
  generateStudyPlan: (data: {
    exam_id?: string;
    daily_hours?: number;
    days_per_week?: number;
    confirm_replace?: boolean;
    focus_subjects?: string[];
  }) => apiRequest('/study-plan/generate', { method: 'POST', body: JSON.stringify(data) }),
  addStudyTask: (data: any) =>
    apiRequest('/study-plan/tasks', { method: 'POST', body: JSON.stringify(data) }),
  updateStudyTask: (taskId: number, data: any) =>
    apiRequest(`/study-plan/tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteStudyTask: (taskId: number) =>
    apiRequest(`/study-plan/tasks/${taskId}`, { method: 'DELETE' }),
  runSimulator: (data: any) =>
    apiRequest('/simulator', { method: 'POST', body: JSON.stringify(data) }),

  // AI Counsellor & RAG
  listChatSessions: () => apiRequest('/counsellor/sessions'),
  createChatSession: () => apiRequest('/counsellor/sessions', { method: 'POST' }),
  getChatSession: (id: number) => apiRequest(`/counsellor/sessions/${id}`),
  deleteChatSession: (id: number) => apiRequest(`/counsellor/sessions/${id}`, { method: 'DELETE' }),
  sendChat: (message: string, sessionId?: number) =>
    apiRequest('/counsellor/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
  applyProposal: (proposalType: string, payload: Record<string, any>) =>
    apiRequest('/counsellor/apply-proposal', {
      method: 'POST',
      body: JSON.stringify({ proposal_type: proposalType, payload }),
    }),
  listRagDocuments: () => apiRequest('/rag/documents'),
  ingestRagDocument: (data: any) =>
    apiRequest('/rag/ingest', { method: 'POST', body: JSON.stringify(data) }),
  queryRag: (q: string, examId?: string) =>
    apiRequest(`/rag/query?q=${encodeURIComponent(q)}${examId ? `&exam_id=${encodeURIComponent(examId)}` : ''}`),

  // Notifications & System
  listNotifications: () => apiRequest('/notifications'),
  markNotificationRead: (id: number) => apiRequest(`/notifications/${id}/read`, { method: 'POST' }),
  markAllNotificationsRead: () => apiRequest('/notifications/read-all', { method: 'POST' }),
  getSystemStatus: () => apiRequest('/system/status'),
};
