export interface CustomerListItem {
  customer_id: string;
  first_name: string;
  last_name: string;
  email: string;
  country?: string | null;
  segment_id?: string | null;
  lifetime_value: number;
  churn_score: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Transaction {
  transaction_id: string;
  product_id?: string | null;
  transaction_date?: string | null;
  channel?: string | null;
  status?: string | null;
  amount: number;
}

export interface CustomerProfile {
  customer_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string | null;
  country?: string | null;
  city?: string | null;
  gender?: string | null;
  age?: number | null;
  signup_date?: string | null;
  last_purchase_date?: string | null;
  segment_id?: string | null;
  lifetime_value: number;
  churn_score: number;
  updated_at?: string | null;
}

export interface CustomerDetail {
  profile: CustomerProfile;
  transactions: Transaction[];
}

export interface CategorySpend {
  category: string;
  total: number;
}

export interface CustomerMetrics {
  lifetime_spend: number;
  top_categories: CategorySpend[];
  last_30d: number;
  last_90d: number;
  open_tickets: number;
  avg_csat?: number | null;
}

export interface Note {
  id: number;
  customer_id: string;
  note: string;
  author_email: string;
  created_at: string;
  processed: boolean;
}

export interface SegmentOverride {
  customer_id: string;
  segment_id: string;
  author_email: string;
  updated_at: string;
  processed: boolean;
}

export interface Segment {
  segment_id: string;
  segment_name: string;
  description?: string | null;
}

export interface AppConfig {
  databricks_host: string;
  dashboard_id: string;
  genie_space_id: string;
  workspace_id?: string | null;
  user_email?: string | null;
}

export interface GenieConversation {
  conversation_id: string;
  message_id: string;
}

export interface GenieMessageResult {
  status: string;
  content?: string | null;
  query?: string | null;
  columns?: string[] | null;
  rows?: unknown[][] | null;
  error?: string | null;
}

export interface RunSummary {
  run_id: number;
  state?: string | null;
  result?: string | null;
  start_time?: number | null;
  run_page_url?: string | null;
}

export interface RunStatus extends RunSummary {
  life_cycle_state?: string | null;
  result_state?: string | null;
  end_time?: number | null;
}
