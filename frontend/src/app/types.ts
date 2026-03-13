export type ResponseProfile = "speed" | "balanced";
export type SessionType = "mentor" | "evaluator" | "expert";
export type Provider = "ollama" | "cerebras" | "groq" | "openai" | "openrouter" | "anthropic" | "gemini";
export type ThemeMode = "light" | "dark" | "dusk" | "neon";
export type OAuthProvider = "google" | "apple";
export type HelpMode = "coach_me" | "challenge_me" | "explain_directly";
export type EvaluatorMode = "idea_review" | "deck_review";

export type FounderType = "student" | "operator" | "founder" | "investor" | "professional" | "other" | "serial" | "unknown";
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
  geography: string;
  websiteUrl: string;
  setupContext: string;
  sessionType: SessionType;
  evaluatorMode: EvaluatorMode;
  mode: Mode;
  helpMode: HelpMode;
  liveWebEnabled: boolean;
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

export type SourceCitation = {
  title: string;
  url: string;
  label: string;
  sourceType: string;
  geographyScope: string;
  confidence: string;
  domain: string;
};

export type ExpertAnalysisSnapshot = {
  strengths: string[];
  risks: string[];
  missingEvidence: string[];
  contradictions: string[];
  nextQuestions: string[];
  recommendedNextActions: string[];
  concepts: string[];
};

export type SessionState = {
  coverage: Record<string, number>;
  sector: string;
  stage: string;
  company_name: string;
  founder_type: string;
  mode: string;
  geography: string;
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
  slideCount?: number;
  hasRenderableSlides?: boolean;
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

export type LensAssessment = {
  key: string;
  label: string;
  status: string;
  score: number;
  why: string;
  evidence: string[];
  improvement: string;
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
  questionsAsked: number;
  maxQuestions: number;
  completed: boolean;
  partial: boolean;
  currentQuestion: EvaluationQuestion | null;
  currentScore: number;
  dimensionScores: DimensionScore[];
  website: Record<string, unknown>;
  lastFeedback: string;
  stopReason: string;
  canGoDeeper: boolean;
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
  verdict: string;
  confidence: number;
  stopReason: string;
  coreLenses: LensAssessment[];
  supportingLenses: LensAssessment[];
  missingEvidence: string[];
  nextExperiments: string[];
};

export type DeckCoverageItem = {
  section: string;
  status: string;
  note: string;
  refs: string[];
  evidence: string[];
  missingItems: string[];
};

export type DeckConstraintCheck = {
  key: string;
  label: string;
  status: string;
  note: string;
  refs: string[];
};

export type DeckFocusedAssessment = {
  key: string;
  label: string;
  status: string;
  assessment: string;
  refs: string[];
};

export type DeckSlideReview = {
  index: number;
  label: string;
  summary: string;
  whatWorks: string[];
  issues: string[];
  suggestions: string[];
  refs: string[];
};

export type DeckEvaluationReport = {
  overallScore: number;
  confidence: number;
  reviewMode: string;
  reviewLimitations: string[];
  verdict: string;
  summary: string;
  whatWorks: string[];
  weakPoints: string[];
  unprovenClaims: string[];
  storyFlow: string;
  templateCoverage: DeckCoverageItem[];
  constraintChecks: DeckConstraintCheck[];
  focusedAssessments: DeckFocusedAssessment[];
  slideReviews: DeckSlideReview[];
  topFixes: string[];
  londonWhaleAssessment: string;
  stopReason: string;
};

export type RuntimeUsageSnapshot = {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  estimated: boolean;
};

export type RuntimeUsageSummary = {
  last: RuntimeUsageSnapshot;
  session: RuntimeUsageSnapshot;
};

export type ProviderOption = {
  key: Provider;
  label: string;
  requiresApiKey: boolean;
  defaultSpeedModel: string;
  defaultBalancedModel: string;
  supportsVisionModels?: boolean;
  recommendedDeckModel?: string;
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
  evaluatorMode?: EvaluatorMode;
  provider: Provider;
  model: string;
  supportsVision?: boolean;
  questionBudget?: number | null;
  websiteUrl: string;
  sources: SourceCitation[];
  confidence: number;
  knowledgeLane: string;
  usedLiveWeb: boolean;
  followUpMode: string;
  helpMode: HelpMode;
  liveWebEnabled: boolean;
  analysisSnapshot: ExpertAnalysisSnapshot;
  runtimeUsage: RuntimeUsageSummary;
  evaluationProgress?: EvaluationProgress | null;
  evaluationReport?: EvaluationReport | null;
  deckEvaluationReport?: DeckEvaluationReport | null;
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
  evaluatorMode?: EvaluatorMode;
  provider: Provider;
  model: string;
  supportsVision?: boolean;
  questionBudget?: number | null;
  websiteUrl: string;
  sources: SourceCitation[];
  confidence: number;
  knowledgeLane: string;
  usedLiveWeb: boolean;
  followUpMode: string;
  helpMode: HelpMode;
  liveWebEnabled: boolean;
  analysisSnapshot: ExpertAnalysisSnapshot;
  runtimeUsage: RuntimeUsageSummary;
  evaluationProgress?: EvaluationProgress | null;
  evaluationReport?: EvaluationReport | null;
  deckEvaluationReport?: DeckEvaluationReport | null;
};

export type SessionListPayload = {
  sessions: SessionSummary[];
};

export type SessionRuntimePayload = {
  sessionId: string;
  provider: string;
  model: string;
  supportsVision?: boolean;
  runtimeUsage: RuntimeUsageSummary;
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
  evaluatorMode: EvaluatorMode;
  evaluationProgress: EvaluationProgress;
  evaluationReport?: EvaluationReport | null;
  deckEvaluationReport?: DeckEvaluationReport | null;
  reciprocal: string;
  question: EvaluationQuestion | null;
  questionLabel: string;
  activeUploads: UploadSummary[];
  warning: string;
  supportsVision: boolean;
  runtimeUsage: RuntimeUsageSummary;
};

export type EvaluatorReportPayload = {
  sessionId: string;
  evaluatorMode: EvaluatorMode;
  evaluationReport?: EvaluationReport | null;
  deckEvaluationReport?: DeckEvaluationReport | null;
  evaluationProgress: EvaluationProgress;
  provider: string;
  model: string;
  supportsVision: boolean;
  websiteUrl: string;
  runtimeUsage: RuntimeUsageSummary;
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
