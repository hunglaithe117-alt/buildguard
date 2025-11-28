import { useState, useEffect, useCallback } from "react";
import { Loader2, RefreshCw, AlertCircle, CheckCircle2, XCircle, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { sonarApi } from "@/lib/api";
import { ScanJob, ScanJobStatus } from "@/types";
import { formatTimestamp } from "@/lib/utils";
import { useToast } from "@/components/ui/use-toast";

interface ScanJobsTableProps {
    repoId: string;
}

function StatusBadge({ status }: { status: ScanJobStatus }) {
    switch (status) {
        case ScanJobStatus.SUCCESS:
            return (
                <Badge variant="outline" className="border-green-500 text-green-600 gap-1">
                    <CheckCircle2 className="h-3 w-3" /> Success
                </Badge>
            );
        case ScanJobStatus.FAILED:
            return (
                <Badge variant="destructive" className="gap-1">
                    <XCircle className="h-3 w-3" /> Failed
                </Badge>
            );
        case ScanJobStatus.RUNNING:
            return (
                <Badge variant="default" className="bg-blue-500 gap-1">
                    <Loader2 className="h-3 w-3 animate-spin" /> Running
                </Badge>
            );
        default:
            return (
                <Badge variant="secondary" className="gap-1">
                    <Clock className="h-3 w-3" /> Pending
                </Badge>
            );
    }
}

export function ScanJobsTable({ repoId }: ScanJobsTableProps) {
    const [jobs, setJobs] = useState<ScanJob[]>([]);
    const [loading, setLoading] = useState(true);
    const [retryingId, setRetryingId] = useState<string | null>(null);
    const { toast } = useToast();

    const loadJobs = useCallback(async () => {
        try {
            const data = await sonarApi.listJobs(repoId);
            setJobs(data.items);
        } catch (error) {
            console.error("Failed to load jobs", error);
        } finally {
            setLoading(false);
        }
    }, [repoId]);

    useEffect(() => {
        loadJobs();
        const interval = setInterval(loadJobs, 5000); // Poll every 5s
        return () => clearInterval(interval);
    }, [loadJobs]);

    const handleRetry = async (jobId: string) => {
        setRetryingId(jobId);
        try {
            await sonarApi.retryJob(jobId);
            toast({
                title: "Retry Queued",
                description: "The scan job has been queued for retry.",
            });
            loadJobs();
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to retry job.",
                variant: "destructive",
            });
        } finally {
            setRetryingId(null);
        }
    };

    if (loading && jobs.length === 0) {
        return (
            <div className="flex justify-center p-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium">Scan History</h3>
                <Button variant="outline" size="sm" onClick={() => loadJobs()}>
                    <RefreshCw className="mr-2 h-4 w-4" /> Refresh
                </Button>
            </div>

            <div className="rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Status</TableHead>
                            <TableHead>Commit</TableHead>
                            <TableHead>Created At</TableHead>
                            <TableHead>Duration</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {jobs.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                                    No scan jobs found.
                                </TableCell>
                            </TableRow>
                        ) : (
                            jobs.map((job) => (
                                <TableRow key={job.id}>
                                    <TableCell>
                                        <StatusBadge status={job.status} />
                                        {job.error_message && (
                                            <div className="text-xs text-red-500 mt-1 max-w-[300px] truncate" title={job.error_message}>
                                                {job.error_message}
                                            </div>
                                        )}
                                    </TableCell>
                                    <TableCell className="font-mono text-xs">
                                        {job.commit_sha.substring(0, 7)}
                                    </TableCell>
                                    <TableCell className="text-muted-foreground text-sm">
                                        {formatTimestamp(job.created_at)}
                                    </TableCell>
                                    <TableCell className="text-muted-foreground text-sm">
                                        {job.started_at && job.finished_at
                                            ? `${Math.round((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000)}s`
                                            : "-"}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        {job.status === ScanJobStatus.FAILED && (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => handleRetry(job.id)}
                                                disabled={retryingId === job.id}
                                            >
                                                {retryingId === job.id ? <Loader2 className="h-3 w-3 animate-spin" /> : "Retry"}
                                            </Button>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}
