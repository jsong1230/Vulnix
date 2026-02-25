/**
 * API 타입 정의
 * - IDE 분석 API 요청/응답 타입
 */

export interface Finding {
  rule_id: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'informational';
  message: string;
  file_path: string;
  start_line: number;
  end_line: number;
  start_col: number;
  end_col: number;
  code_snippet: string;
  cwe_id?: string;
  owasp_category?: string;
  vulnerability_type: string;
  is_false_positive_filtered: boolean;
}

export interface AnalyzeRequest {
  file_path: string;
  language: string;
  content: string;
  context?: { workspace_name?: string; git_branch?: string };
}

export interface AnalyzeResponse {
  success: boolean;
  data?: { findings: Finding[]; analysis_duration_ms: number; semgrep_version: string };
  error?: { code: string; message: string } | null;
}

export interface FalsePositivePattern {
  id: string;
  semgrep_rule_id: string;
  file_pattern?: string;
  reason?: string;
  is_active: boolean;
  updated_at: string;
}

export interface FalsePositivePatternsResponse {
  success: boolean;
  data?: { patterns: FalsePositivePattern[]; last_updated: string; etag: string };
  error?: { code: string; message: string } | null;
}

export interface PatchSuggestionRequest {
  file_path: string;
  language: string;
  content: string;
  finding: {
    rule_id: string;
    start_line: number;
    end_line: number;
    code_snippet: string;
    message: string;
  };
}

export interface PatchSuggestionResponse {
  success: boolean;
  data?: { patch_diff: string; patch_description: string; vulnerability_detail: Record<string, unknown> };
  error?: { code: string; message: string } | null;
}
