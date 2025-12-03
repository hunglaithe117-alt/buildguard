import type {
  Build,
  BuildDetail,
  BuildListResponse,
  DashboardSummaryResponse,
  GithubAuthorizeResponse,
  GithubInstallation,
  GithubInstallationListResponse,
  RepoDetail,
  RepoImportPayload,
  RepoListResponse,
  RepoSuggestionResponse,
  RepoSearchResponse,
  LazySyncPreviewResponse,
  RepoUpdatePayload,
  RepositoryRecord,
  UserAccount,
  AuthVerifyResponse,
  RefreshTokenResponse,
  ScanJob,
  ScanResult,
  FailedScan,
} from "@/types";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

// Token refresh flag to prevent multiple refresh attempts
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: any) => void;
  reject: (reason?: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Response interceptor to handle token expiration
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      const authError = error.response?.headers?.["x-auth-error"];

      // Handle GitHub token errors - redirect to re-authenticate
      if (
        authError === "github_token_expired" ||
        authError === "github_token_revoked" ||
        authError === "github_not_connected"
      ) {
        // Don't retry, let the component handle re-authentication
        return Promise.reject(error);
      }

      // Handle JWT token expiration - try to refresh
      if (isRefreshing) {
        // If already refreshing, queue this request
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => {
            return api(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Attempt to refresh the token
        await api.post<RefreshTokenResponse>("/auth/refresh");
        processQueue(null);
        isRefreshing = false;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        isRefreshing = false;
        // Redirect to login page
        if (typeof window !== "undefined" && window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export const buildApi = {
  getByRepo: async (
    repoId: string,
    params?: {
      skip?: number;
      limit?: number;
      q?: string;
    }
  ) => {
    const response = await api.get<BuildListResponse>(`/repos/${repoId}/builds`, {
      params,
    });
    return response.data;
  },

  getById: async (repoId: string, buildId: string) => {
    const response = await api.get<BuildDetail>(
      `/repos/${repoId}/builds/${buildId}`
    );
    return response.data;
  },
};

export const reposApi = {
  list: async (params?: { skip?: number; limit?: number; q?: string }) => {
    const response = await api.get<RepoListResponse>("/repos/", { params });
    return response.data;
  },
  get: async (repoId: string) => {
    const response = await api.get<RepoDetail>(`/repos/${repoId}`);
    return response.data;
  },
  update: async (repoId: string, payload: RepoUpdatePayload) => {
    const response = await api.patch<RepoDetail>(`/repos/${repoId}`, payload);
    return response.data;
  },
  importBulk: async (payloads: RepoImportPayload[]) => {
    const response = await api.post<RepositoryRecord[]>("/repos/import/bulk", payloads);
    return response.data;
  },
  discover: async (query?: string, limit: number = 50) => {
    const response = await api.get<RepoSuggestionResponse>("/repos/available", {
      params: {
        q: query,
        limit,
      },
    });
    return response.data;
  },
  search: async (query?: string) => {
    const response = await api.get<RepoSearchResponse>("/repos/search", {
      params: { q: query },
    });
    return response.data;
  },

  triggerLazySync: async (repoId: string) => {
    const response = await api.post<{ status: string }>(
      `/repos/${repoId}/sync-run`
    );
    return response.data;
  },
  sync: async () => {
    const response = await api.post<RepoSuggestionResponse>("/repos/sync");
    return response.data;
  },
  triggerScan: async (repoId: string, buildId: string) => {
    const response = await api.post<{ status: string; job_id: string }>(
      `/repos/${repoId}/builds/${buildId}/scan`
    );
    return response.data;
  },
  getBuild: async (repoId: string, buildId: string) => {
    const response = await api.get<BuildDetail>(`/repos/${repoId}/builds/${buildId}`);
    return response.data;
  },
  triggerRescan: async (repoId: string, buildId: string) => {
    const response = await api.post<{ status: string }>(
      `/repos/${repoId}/builds/${buildId}/rescan`
    );
    return response.data;
  },
  submitFeedback: async (
    repoId: string,
    buildId: string,
    payload: { is_false_positive: boolean; reason: string }
  ) => {
    const res = await api.post(
      `/repos/${repoId}/builds/${buildId}/feedback`,
      payload
    );
    return res.data;
  },

  compareBuilds: async (
    repoId: string,
    baseBuildId: string,
    headBuildId: string
  ) => {
    const res = await api.get(`/repos/${repoId}/compare`, {
      params: { base_build_id: baseBuildId, head_build_id: headBuildId },
    });
    return res.data;
  },
  getMetrics: async (repoId: string) => {
    const response = await api.get<string[]>(`/repos/${repoId}/metrics`);
    return response.data;
  },
  updateMetrics: async (repoId: string, metrics: string[]) => {
    const response = await api.put<{ metrics: string[] }>(
      `/repos/${repoId}/metrics`,
      { metrics }
    );
    return response.data;
  },
};

export const sonarApi = {
  getConfig: async (repoId: string) => {
    const response = await api.get<{ content: string }>(`/repos/${repoId}/sonar/config`);
    return response.data;
  },
  updateConfig: async (repoId: string, content: string) => {
    const response = await api.post<{ status: string }>(
      `/repos/${repoId}/sonar/config`,
      { content }
    );
    return response.data;
  },
  listJobs: async (repoId: string, params?: { skip?: number; limit?: number }) => {
    const response = await api.get<{ items: ScanJob[]; total: number }>(
      `/repos/${repoId}/sonar/jobs`,
      { params }
    );
    return response.data;
  },
  retryJob: async (jobId: string) => {
    const response = await api.post<{ status: string; job_id: string }>(
      `/repos/sonar/jobs/${jobId}/retry`
    );
    return response.data;
  },
  listResults: async (repoId: string, params?: { skip?: number; limit?: number }) => {
    const response = await api.get<{ items: ScanResult[]; total: number }>(
      `/repos/${repoId}/sonar/results`,
      { params }
    );
    return response.data;
  },
  listFailedScans: async (repoId: string, params?: { skip?: number; limit?: number }) => {
    const response = await api.get<{ items: FailedScan[]; total: number }>(
      `/repos/${repoId}/sonar/failed`,
      { params }
    );
    return response.data;
  },
  updateFailedScanConfig: async (failedScanId: string, content: string) => {
    const response = await api.put<{ status: string; failed_scan_id: string }>(
      `/repos/sonar/failed/${failedScanId}/config`,
      { content }
    );
    return response.data;
  },
  retryFailedScan: async (failedScanId: string) => {
    const response = await api.post<{ status: string; job_id: string }>(
      `/repos/sonar/failed/${failedScanId}/retry`
    );
    return response.data;
  },
  getAvailableMetrics: async () => {
    const response = await api.get<string[]>("/sonar/metrics");
    return response.data;
  },
};

export const dashboardApi = {
  getSummary: async () => {
    const response = await api.get<DashboardSummaryResponse>(
      "/dashboard/summary"
    );
    return response.data;
  },
  getRecentBuilds: async (limit: number = 10) => {
    const response = await api.get<Build[]>("/dashboard/recent-builds", {
      params: { limit },
    });
    return response.data;
  },
};

export const integrationApi = {
  verifyAuth: async () => {
    const response = await api.get<AuthVerifyResponse>("/auth/verify");
    return response.data;
  },
  startGithubOAuth: async (redirectPath?: string) => {
    const response = await api.post<GithubAuthorizeResponse>(
      "/auth/github/login",
      {
        redirect_path: redirectPath,
      }
    );
    return response.data;
  },
  revokeGithubToken: async () => {
    await api.post("/auth/github/revoke");
  },
  logout: async () => {
    await api.post("/auth/logout");
  },
  refreshToken: async () => {
    const response = await api.post<RefreshTokenResponse>("/auth/refresh");
    return response.data;
  },
  getCurrentUser: async () => {
    const response = await api.get<UserAccount>("/auth/me");
    return response.data;
  },

  listGithubInstallations: async () => {
    const response = await api.get<GithubInstallationListResponse>(
      "/integrations/github/installations"
    );
    return response.data;
  },
  getGithubInstallation: async (installationId: string) => {
    const response = await api.get<GithubInstallation>(
      `/integrations/github/installations/${installationId}`
    );
    return response.data;
  },
  syncInstallations: async () => {
    const response = await api.post<GithubInstallationListResponse>(
      "/integrations/github/sync"
    );
    return response.data;
  },
};

export const usersApi = {
  getCurrentUser: async () => {
    const response = await api.get<UserAccount>("/users/me");
    return response.data;
  },
};

export const datasetFeaturesApi = {
  getFeatures: async (jobId: string) => {
    const response = await api.get<any[]>(`/datasets/${jobId}/features`);
    return response.data;
  },
  startExtraction: async (
    jobId: string,
    selectedFeatures: string[],
    extractorConfig: any = {}
  ) => {
    const response = await api.post<{ status: string; message: string }>(
      `/datasets/${jobId}/start-extraction`,
      { selected_features: selectedFeatures, extractor_config: extractorConfig }
    );
    return response.data;
  },
};
