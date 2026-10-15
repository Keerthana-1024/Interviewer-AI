import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

// ─── Types ────────────────────────────────────────────────────────────────────
export interface ResumeResponse {
  id: string; filename: string; extraction_status: string;
  parsed_profile: Record<string, unknown> | null; created_at: string;
}

export interface JDResponse {
  id: string; extraction_status: string;
  parsed_requirements: Record<string, unknown> | null; created_at: string;
}

export interface MatchReportResponse {
  id: string; resume_id: string; jd_id: string;
  overall_score: number | null; required_skill_coverage: number | null;
  preferred_skill_coverage: number | null;
  skill_analysis: {
    required: SkillResult[]; preferred: SkillResult[];
  } | null;
  strengths: string[] | null; gaps: string[] | null;
  suggested_topics: string[] | null; interview_plan: unknown | null;
  created_at: string;
}

export interface SkillResult {
  jd_skill: string; status: string; matched_to: string | null;
  evidence: string | null; confidence: number; fuzzy_score: number | null; notes: string | null;
}

export interface SessionState {
  id: string; status: string; config: Record<string, unknown> | null;
  current_question_index: number; total_questions: number;
  started_at: string | null; completed_at: string | null;
  candidate_name: string | null; created_at: string;
}

export interface QuestionResponse {
  id: string; question_text: string; competency: string;
  question_type: string; difficulty: string; order_index: number;
  requires_whiteboard: boolean; time_allocation_minutes: number;
  is_follow_up: boolean;
  session_progress: { current: number; total: number; percent: number; status: string };
}

export interface AnswerResponse {
  answer_id: string; question_id: string;
  evaluation: { overall_score: number; feedback: string; concepts_demonstrated: string[]; missing_concepts: string[] } | null;
  next_action: string; message: string;
}

export interface FinalReport {
  id: string; session_id: string; overall_score: number | null;
  overall_summary: string | null; competency_scores: Record<string, { average_score: number; num_questions: number }> | null;
  technical_strengths: string[] | null; knowledge_gaps: string[] | null;
  verified_claims: string[] | null; unverified_claims: string[] | null;
  recommended_study_areas: { topic: string; reason: string; resources_hint: string }[] | null;
  full_report: Record<string, unknown> | null; created_at: string;
}

export interface CreateInterviewRequest {
  resume_id: string; jd_id: string; match_report_id?: string;
  candidate_name?: string; mode: string; difficulty: string;
  duration_minutes: number; max_questions: number;
}

// ─── API functions ────────────────────────────────────────────────────────────

export const uploadResume = (file: File) => {
  const fd = new FormData(); fd.append('file', file)
  return api.post<ResumeResponse>('/resumes', fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 180000 })
}

export const analyzeJD = (jd_text: string) =>
  api.post<JDResponse>('/job-descriptions/analyze', { jd_text })

export const createMatch = (resume_id: string, jd_id: string) =>
  api.post<MatchReportResponse>('/matches', { resume_id, jd_id })

export const getMatch = (matchId: string) =>
  api.get<MatchReportResponse>(`/matches/${matchId}`)

export const createInterview = (req: CreateInterviewRequest) =>
  api.post<SessionState>('/interviews', req)

export const getSession = (sessionId: string) =>
  api.get<SessionState>(`/interviews/${sessionId}`)

export const getCurrentQuestion = (sessionId: string) =>
  api.get<QuestionResponse>(`/interviews/${sessionId}/question`)

export const getQuestionAudioUrl = (sessionId: string) =>
  `/api/interviews/${sessionId}/question/audio`

export const submitAnswer = (sessionId: string, answer_text: string | null, skipped = false) =>
  api.post<AnswerResponse>(`/interviews/${sessionId}/answers`, { answer_text, skipped })

export const pauseInterview = (sessionId: string) =>
  api.post(`/interviews/${sessionId}/pause`)

export const resumeInterview = (sessionId: string) =>
  api.post(`/interviews/${sessionId}/resume`)

export const endInterview = (sessionId: string) =>
  api.post(`/interviews/${sessionId}/end`)

export const getReport = (sessionId: string) =>
  api.get<FinalReport>(`/interviews/${sessionId}/report`)

export const deleteSession = (sessionId: string) =>
  api.delete(`/interviews/${sessionId}`)

export const listSessions = () =>
  api.get<SessionState[]>('/interviews')

export default api
