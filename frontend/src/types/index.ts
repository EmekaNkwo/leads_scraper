export interface Lead {
  query: string;
  name: string;
  phone: string;
  address: string;
  email: string;
  owner_name: string;
  website: string;
  category: string;
  social_links: string[];
  scraped_at: string;
  confidence_score: number;
}

export interface QueryResult {
  query: string;
  leads_count: number;
  elapsed_seconds: number;
  csv_path: string;
  error: string | null;
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  completed_at: string | null;
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
  };
}

export interface ScrapeRequest {
  queries: string[];
  max_results_per_query: number;
  max_scrolls_per_query: number;
  max_runtime_seconds: number;
  headless: boolean;
  enrich_websites: boolean;
  export_json: boolean;
  resume: boolean;
}

export interface ExportFile {
  filename: string;
  size_bytes: number;
  modified_at: string;
}

export interface AppConfig {
  queries: string[];
  max_results_per_query: number;
  max_scrolls_per_query: number;
  max_runtime_seconds: number;
  output_dir: string;
  logs_dir: string;
  checkpoint_dir: string;
  archive_after_days: number;
  headless: boolean;
  enrich_websites: boolean;
  export_json: boolean;
}

export interface HealthStatus {
  status: string;
  version: string;
  uptime_seconds: number;
}
