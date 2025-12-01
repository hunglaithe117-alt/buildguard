export type SonarConfig = {
  filename: string;
  file_path: string;
  updated_at?: string;
};

export enum ProjectStatus {
  PENDING = "PENDING",
  PROCESSING = "PROCESSING",
  FINISHED = "FINISHED",
}

export enum ScanJobStatus {
  PENDING = "PENDING",
  RUNNING = "RUNNING",
  SUCCESS = "SUCCESS",
  FAILED_TEMP = "FAILED_TEMP",
  FAILED_PERMANENT = "FAILED_PERMANENT",
}

export type Project = {
  id: string;
  project_name: string;
  project_key: string;
  total_builds: number;
  total_commits: number;
  processed_commits: number;
  failed_commits: number;
  status: ProjectStatus;
  source_filename?: string | null;
  source_path?: string | null;
  created_at: string;
  updated_at: string;
  sonar_config?: SonarConfig | null;
};

export type ScanJob = {
  id: string;
  project_id: string;
  commit_sha: string;
  status: ScanJobStatus;
  retry_count: number;
  max_retries: number;
  last_error?: string | null;
  component_key?: string | null;
  repository_url?: string | null;
  repo_slug?: string | null;
  created_at: string;
  updated_at: string;
};

const API_BASE =
  process.env.NEXT_PUBLIC_PIPELINE_API_URL ?? "http://localhost:8001/api";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    cache: "no-store",
    ...options,
  });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || `Request to ${path} failed (${resp.status})`);
  }
  if (resp.status === 204) {
    return {} as T;
  }
  return (await resp.json()) as T;
}

export const pipelineApi = {
  listProjects: () => apiFetch<Project[]>("/projects"),
  listScanJobs: (params?: { status?: string; project_id?: string }) =>
    apiFetch<ScanJob[]>(
      `/scan-jobs${params ? `?${new URLSearchParams(params as any).toString()}` : ""}`
    ),
};
