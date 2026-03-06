export type ResponseProfile = "speed" | "balanced";
export type SessionType = "mentor" | "evaluator";
export type Provider = "ollama" | "cerebras" | "groq" | "openai" | "openrouter" | "anthropic" | "gemini";
export type ThemeMode = "light" | "dark" | "neon";
export type OAuthProvider = "google" | "apple";

export type FounderType = "student" | "professional" | "founder" | "serial" | "unknown";
export type Sector =
  | "saas"
  | "d2c"
  | "fintech"
  | "marketplace"
  | "edtech"
  | "healthtech"
  | "deeptech"
  | "unknown";
export type Stage = "idea" | "pre-revenue" | "early-revenue" | "growth" | "unknown";
export type Mode = "think_it_through" | "quick_stress_test";
export type RuntimeKind = "local" | "external";

export type SetupDraft = {
  runtimeKind: RuntimeKind;
  provider: Provider;
  model: string;
  apiKey: string;
  founderType: FounderType;
  sector: Sector;
  stage: Stage;
  websiteUrl: string;
  setupContext: string;
  sessionType: SessionType;
  mode: Mode;
  questionBudget: 10 | 15 | 20;
};

export type ChatTurn = {
  role: "user" | "assistant";
  content: string;
  timestamp?: string | null;
  metadata?: Record<string, unknown>;
};

export type CoverageItem = {
  section: string;
  score: number;
  label: string;
};

export type SessionState = {
  coverage: Record<string, number>;
  sector: string;
  stage: string;
  company_name: string;
  founder_type: string;
  mode: string;
  urgency: boolean;
  number_claims: Array<{
    claim: string;
    source_provided: boolean;
    challenged: boolean;
    stress_tested: boolean;
  }>;
  phase: string;
  turns: number;
  facts: Record<string, string>;
};

export type UploadSummary = {
  name: string;
  docType: string;
  chunkCount: number;
  chars: number;
  uploadedAt: string;
};

export type EvaluationQuestion = {
  id: string;
  text: string;
  baseText: string;
  contextHint: string;
  contextMode: string;
  category: string;
  weightTier: string;
};

export type DimensionScore = {
  key: string;
  label: string;
  score: number;
};

export type QuestionScore = {
  questionId: string;
  question: string;
  category: string;
  score: number;
  why: string;
  suggestions: string[];
};

export type EvaluationProgress = {
  questionBudget: number;
  answeredQuestions: number;
  completed: boolean;
  partial: boolean;
  currentQuestion: EvaluationQuestion | null;
  currentScore: number;
  dimensionScores: DimensionScore[];
  website: Record<string, unknown>;
  lastFeedback: string;
};

export type EvaluationReport = {
  overallScore: number;
  partial: boolean;
  answeredQuestions: number;
  questionBudget: number;
  dimensionScores: DimensionScore[];
  why: string[];
  suggestions: string[];
  questions: QuestionScore[];
  summary: string;
};

export type ProviderOption = {
  key: Provider;
  label: string;
  requiresApiKey: boolean;
  defaultSpeedModel: string;
  defaultBalancedModel: string;
};

export type AuthProviderOption = {
  key: OAuthProvider;
  label: string;
  configured: boolean;
};

export type AuthUser = {
  provider: OAuthProvider;
  userId: string;
  email: string;
  displayName: string;
  avatarUrl: string;
  clientId: string;
};

export type AuthSessionPayload = {
  user: AuthUser | null;
  providers: AuthProviderOption[];
  error: string;
  adminMode: boolean;
};

export type SessionPayload = {
  sessionId: string;
  history: ChatTurn[];
  state: SessionState;
  chips: string[];
  responseProfile: ResponseProfile;
  coverage: CoverageItem[];
  nextGap: string;
  activeUploads: UploadSummary[];
  sessionType: SessionType;
  provider: Provider;
  model: string;
  questionBudget?: number | null;
  websiteUrl: string;
  evaluationProgress?: EvaluationProgress | null;
  evaluationReport?: EvaluationReport | null;
};

export type SessionSummary = {
  sessionId: string;
  title: string;
  subtitle: string;
  lastActive?: string | null;
  turnCount: number;
  companyName: string;
  displayName: string;
  sector: string;
  stage: string;
  sessionType: SessionType;
  provider: string;
  model: string;
  questionBudget?: number | null;
};

export type StartSessionPayload = {
  sessionId: string;
  openingMessage: string;
  state: SessionState;
  chips: string[];
  responseProfile: ResponseProfile;
  coverage: CoverageItem[];
  nextGap: string;
  activeUploads: UploadSummary[];
  sessionType: SessionType;
  provider: Provider;
  model: string;
  questionBudget?: number | null;
  websiteUrl: string;
  evaluationProgress?: EvaluationProgress | null;
  evaluationReport?: EvaluationReport | null;
};

export type SessionListPayload = {
  sessions: SessionSummary[];
};

export type SessionRuntimePayload = {
  sessionId: string;
  provider: string;
  model: string;
};

export type OutlinePayload = {
  sessionId: string;
  markdown: string;
  responseProfile: ResponseProfile;
};

export type ProviderCatalogPayload = {
  providers: ProviderOption[];
};

export type EvaluatorAnswerPayload = {
  sessionId: string;
  evaluationProgress: EvaluationProgress;
  evaluationReport: EvaluationReport;
  reciprocal: string;
  question: EvaluationQuestion | null;
  questionLabel: string;
  activeUploads: UploadSummary[];
  warning: string;
};

export type EvaluatorReportPayload = {
  sessionId: string;
  evaluationReport: EvaluationReport;
  evaluationProgress: EvaluationProgress;
  provider: string;
  model: string;
  websiteUrl: string;
};

export type AdminOverview = {
  totalSessions: number;
  totalTurns: number;
  totalEvents: number;
  uniqueVisitors: number;
  sessionsLast7Days: number;
  eventsLast24Hours: number;
  outlineOpens: number;
  uploads: number;
  chatCompletions: number;
  averageFirstTokenSeconds: number;
  averageTotalSeconds: number;
  evaluatorSessions: number;
  evaluatorCompletions: number;
  evaluatorCompletionRate: number;
  averageSuccessScore: number;
  averageEvaluatorScore: number;
  websiteFetchFailures: number;
  dropOffQuestion: string;
  providerBreakdown: Record<string, number>;
  eventBreakdown: Record<string, number>;
};

export type AdminEvent = {
  client_id: string;
  session_id: string;
  display_name: string;
  event_type: string;
  pathname: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type AdminEventsPayload = {
  events: AdminEvent[];
  sessions: SessionSummary[];
};
