export interface Lead {
  query: string;
  name: string;
  phone: string;
  address: string;
  email: string;
  owner_name: string;
  website: string;
  maps_url: string;
  category: string;
  social_links: string[];
  scraped_at: string;
  confidence_score: number;
}

export interface QueryResult {
  query: string;
  status: "completed" | "failed" | "cancelled";
  leads_count: number;
  elapsed_seconds: number;
  csv_path: string;
  export_expires_at: string | null;
  error: string | null;
}

export interface JobProgress {
  query: string | null;
  phase: string;
  leads_collected: number;
  leads_target: number;
  visible_cards: number;
  scrolls_used: number;
  max_scrolls: number;
  stale_scrolls: number;
  message: string | null;
  end_reason: string | null;
  elapsed_seconds: number | null;
  csv_path: string | null;
  export_expires_at: string | null;
  updated_at: string | null;
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  created_at: string;
  completed_at: string | null;
  queries: string[];
  queries_total: number;
  queries_done: number;
  results: QueryResult[];
  leads: Lead[];
  summary: {
    total_leads: number;
    emails_found: number;
    websites_found: number;
    queries_succeeded: number;
    queries_failed: number;
    queries_cancelled: number;
  };
  progress: JobProgress | null;
  recent_events: string[];
  export_retention_minutes: number;
  exports_are_temporary: boolean;
  master_csv_enabled: boolean;
  combined_csv_filename: string | null;
  combined_csv_path: string | null;
  combined_csv_expires_at: string | null;
}

export interface ScrapeRequest {
  queries: string[];
  max_results_per_query: number;
  max_scrolls_per_query: number;
  max_runtime_seconds: number;
  headless: boolean;
  enrich_websites: boolean;
  resume: boolean;
}

export interface ExportFile {
  filename: string;
  size_bytes: number;
  modified_at: string;
  expires_at: string | null;
}

export interface AppConfig {
  queries: string[];
  max_results_per_query: number;
  max_scrolls_per_query: number;
  max_runtime_seconds: number;
  output_dir: string;
  logs_dir: string;
  checkpoint_dir: string;
  export_retention_minutes: number;
  headless: boolean;
  enrich_websites: boolean;
  enable_master_csv: boolean;
}

export interface HealthStatus {
  status: string;
  version: string;
  uptime_seconds: number;
}

export interface DedupeStatus {
  alias_count: number;
}

export interface AgentRunRequest {
  goal: string;
  max_queries: number;
  max_results_per_query: number;
  max_scrolls_per_query: number;
  max_runtime_seconds: number;
  headless: boolean;
  enrich_websites: boolean;
  resume: boolean;
}

export interface AgentProgress {
  phase: string;
  message: string | null;
  updated_at: string | null;
}

export interface AgentLeadInsight {
  name: string;
  query: string;
  score: number;
  email: string;
  website: string;
  reasons: string[];
}

export interface AgentAnalysis {
  total_leads: number;
  emails_found: number;
  websites_found: number;
  top_leads: AgentLeadInsight[];
  summary: string;
}

export interface AgentRunStatus {
  run_id: string;
  status:
    | "pending"
    | "running"
    | "cancel_requested"
    | "completed"
    | "failed"
    | "cancelled";
  created_at: string;
  completed_at: string | null;
  goal: string;
  proposed_queries: string[];
  scrape_request: Partial<ScrapeRequest> | null;
  scrape_job_id: string | null;
  scrape_job_status: JobStatus["status"] | null;
  linked_export_filename: string | null;
  linked_export_expires_at: string | null;
  progress: AgentProgress | null;
  analysis: AgentAnalysis | null;
  recent_events: string[];
  error: string | null;
}
