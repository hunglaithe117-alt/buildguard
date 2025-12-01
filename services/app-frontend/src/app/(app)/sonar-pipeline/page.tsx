"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { pipelineApi, Project, ProjectStatus, ScanJob, ScanJobStatus } from "@/lib/pipeline-api";

type LoadState<T> = { loading: boolean; error?: string; data: T };

const statusColor: Record<ProjectStatus | ScanJobStatus, string> = {
  PENDING: "bg-yellow-100 text-yellow-800",
  PROCESSING: "bg-blue-100 text-blue-800",
  FINISHED: "bg-green-100 text-green-800",
  RUNNING: "bg-blue-100 text-blue-800",
  SUCCESS: "bg-green-100 text-green-800",
  FAILED_TEMP: "bg-orange-100 text-orange-800",
  FAILED_PERMANENT: "bg-red-100 text-red-800",
};

function StatusPill({ value }: { value: ProjectStatus | ScanJobStatus }) {
  return <Badge className={statusColor[value] ?? ""}>{value}</Badge>;
}

export default function SonarPipelinePage() {
  const [projects, setProjects] = useState<LoadState<Project[]>>({
    loading: true,
    data: [],
  });
  const [jobs, setJobs] = useState<LoadState<ScanJob[]>>({
    loading: true,
    data: [],
  });

  useEffect(() => {
    pipelineApi
      .listProjects()
      .then((data) => setProjects({ loading: false, data }))
      .catch((err) => setProjects({ loading: false, data: [], error: err.message }));

    pipelineApi
      .listScanJobs({ status: "PENDING" })
      .then((data) => setJobs({ loading: false, data }))
      .catch((err) => setJobs({ loading: false, data: [], error: err.message }));
  }, []);

  const recentJobs = useMemo(() => jobs.data.slice(0, 10), [jobs.data]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Sonar Scan Pipeline</h1>
        <p className="text-muted-foreground">
          Quan sát trạng thái dự án, hàng đợi scan, và kết quả Sonar từ pipeline (scan-commit).
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Dự án</CardTitle>
            {projects.error && <p className="text-sm text-red-600">{projects.error}</p>}
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tên</TableHead>
                  <TableHead>Key</TableHead>
                  <TableHead>Tiến độ</TableHead>
                  <TableHead>Trạng thái</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.loading ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-6">
                      Đang tải...
                    </TableCell>
                  </TableRow>
                ) : projects.data.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-6">
                      Chưa có dự án nào
                    </TableCell>
                  </TableRow>
                ) : (
                  projects.data.map((p) => {
                    const progress =
                      p.total_commits > 0
                        ? Math.round((p.processed_commits / p.total_commits) * 100)
                        : 0;
                    return (
                      <TableRow key={p.id}>
                        <TableCell className="font-medium">{p.project_name}</TableCell>
                        <TableCell className="text-muted-foreground">{p.project_key}</TableCell>
                        <TableCell>{progress}%</TableCell>
                        <TableCell>
                          <StatusPill value={p.status} />
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Hàng đợi Scan (mới nhất)</CardTitle>
            {jobs.error && <p className="text-sm text-red-600">{jobs.error}</p>}
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Commit</TableHead>
                  <TableHead>Repo</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead>Cập nhật</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.loading ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-6">
                      Đang tải...
                    </TableCell>
                  </TableRow>
                ) : recentJobs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-6">
                      Không có job nào trong hàng
                    </TableCell>
                  </TableRow>
                ) : (
                  recentJobs.map((j) => (
                    <TableRow key={j.id}>
                      <TableCell className="font-mono text-xs">{j.commit_sha.slice(0, 8)}</TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {j.repo_slug || j.repository_url || "-"}
                      </TableCell>
                      <TableCell>
                        <StatusPill value={j.status} />
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {new Date(j.updated_at).toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
