export interface Issue {
  severity: "critical" | "warning" | "note";
  title: string;
  explanation: string;
  reference?: string;
}

export interface EvaluatorReport {
  readinessScore: number;
  issues: Issue[];
  sessionId: string;
  sourceName?: string;
}

export interface ChatMessage {
  role: "user" | "sift";
  content: string;
  structured?: boolean;
}

export interface OutlineSlide {
  slideNumber: number;
  title: string;
  notes: string;
}

export interface SiftSession {
  sessionId: string;
  provider: string;
  model: string;
  apiKey?: string;
  sourceName?: string;
  report?: EvaluatorReport;
}
