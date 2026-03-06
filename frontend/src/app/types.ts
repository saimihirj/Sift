export type ResponseProfile = "speed" | "balanced";

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

export type SessionPayload = {
  sessionId: string;
  history: ChatTurn[];
  state: SessionState;
  chips: string[];
  responseProfile: ResponseProfile;
  coverage: CoverageItem[];
  nextGap: string;
  activeUploads: UploadSummary[];
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
};

export type SessionListPayload = {
  sessions: SessionSummary[];
};

export type OutlinePayload = {
  sessionId: string;
  markdown: string;
  responseProfile: ResponseProfile;
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
