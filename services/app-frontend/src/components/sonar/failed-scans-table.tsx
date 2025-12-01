import { useState, useEffect, useCallback } from "react";
import { Loader2, AlertCircle, Edit, RotateCcw } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import { sonarApi } from "@/lib/api";
import { formatTimestamp } from "@/lib/utils";
import { useToast } from "@/components/ui/use-toast";

interface FailedScan {
    id: string;
    repo_id: string;
    build_id: string;
    job_id: string;
    commit_sha: string;
    reason: string;
    error_type: string;
    status: string;
    config_override?: string;
    retry_count: number;
    created_at: string;
}

interface FailedScansTableProps {
    repoId: string;
}

export function FailedScansTable({ repoId }: FailedScansTableProps) {
    const [failed, setFailed] = useState<FailedScan[]>([]);
    const [loading, setLoading] = useState(true);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editConfig, setEditConfig] = useState("");
    const [saving, setSaving] = useState(false);
    const [retrying, setRetrying] = useState<string | null>(null);
    const { toast } = useToast();

    const loadFailedScans = useCallback(async () => {
        try {
            const data = await sonarApi.listFailedScans(repoId);
            setFailed(data.items);
        } catch (error) {
            console.error("Failed to load failed scans", error);
        } finally {
            setLoading(false);
        }
    }, [repoId]);

    useEffect(() => {
        loadFailedScans();
        const interval = setInterval(loadFailedScans, 10000); // Poll every 10s
        return () => clearInterval(interval);
    }, [loadFailedScans]);

    const handleEdit = (scan: FailedScan) => {
        setEditingId(scan.id);
        setEditConfig(scan.config_override || "");
    };

    const handleSaveConfig = async (scanId: string) => {
        setSaving(true);
        try {
            await sonarApi.updateFailedScanConfig(scanId, editConfig);
            toast({
                title: "Config Saved",
                description: "Configuration override has been saved.",
            });
            setEditingId(null);
            loadFailedScans();
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to save configuration.",
                variant: "destructive",
            });
        } finally {
            setSaving(false);
        }
    };

    const handleRetry = async (scanId: string) => {
        setRetrying(scanId);
        try {
            await sonarApi.retryFailedScan(scanId);
            toast({
                title: "Retry Queued",
                description: "The scan has been queued for retry.",
            });
            loadFailedScans();
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to retry scan.",
                variant: "destructive",
            });
        } finally {
            setRetrying(null);
        }
    };

    if (loading && failed.length === 0) {
        return (
            <div className="flex justify-center p-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-medium">Failed Scans</h3>
                    <p className="text-sm text-muted-foreground">
                        Scans that failed and need configuration fixes
                    </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => loadFailedScans()}>
                    <RotateCcw className="mr-2 h-4 w-4" /> Refresh
                </Button>
            </div>

            {failed.length === 0 ? (
                <div className="rounded-md border p-8 text-center">
                    <AlertCircle className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                    <p className="text-muted-foreground">No failed scans</p>
                </div>
            ) : (
                <div className="rounded-md border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Commit</TableHead>
                                <TableHead>Error</TableHead>
                                <TableHead>Retries</TableHead>
                                <TableHead>Created At</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {failed.map((scan) => (
                                <>
                                    <TableRow key={scan.id}>
                                        <TableCell className="font-mono text-xs">
                                            {scan.commit_sha.substring(0, 7)}
                                        </TableCell>
                                        <TableCell>
                                            <div className="max-w-[300px]">
                                                <Badge variant="destructive" className="mb-1">
                                                    {scan.error_type}
                                                </Badge>
                                                <p className="text-xs text-muted-foreground truncate" title={scan.reason}>
                                                    {scan.reason}
                                                </p>
                                            </div>
                                        </TableCell>
                                        <TableCell>{scan.retry_count}</TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {formatTimestamp(scan.created_at)}
                                        </TableCell>
                                        <TableCell className="text-right space-x-2">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => handleEdit(scan)}
                                            >
                                                <Edit className="h-3 w-3 mr-1" /> Edit Config
                                            </Button>
                                            <Button
                                                variant="default"
                                                size="sm"
                                                onClick={() => handleRetry(scan.id)}
                                                disabled={retrying === scan.id}
                                            >
                                                {retrying === scan.id ? (
                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                ) : (
                                                    <>
                                                        <RotateCcw className="h-3 w-3 mr-1" /> Retry
                                                    </>
                                                )}
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                    {editingId === scan.id && (
                                        <TableRow>
                                            <TableCell colSpan={5} className="bg-muted/50">
                                                <div className="space-y-2 p-2">
                                                    <label className="text-sm font-medium">
                                                        Configuration Override (sonar-project.properties)
                                                    </label>
                                                    <Textarea
                                                        value={editConfig}
                                                        onChange={(e) => setEditConfig(e.target.value)}
                                                        className="font-mono text-xs min-h-[150px]"
                                                        placeholder="sonar.projectKey=my-project&#10;sonar.sources=.&#10;..."
                                                    />
                                                    <div className="flex justify-end gap-2">
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => setEditingId(null)}
                                                        >
                                                            Cancel
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            onClick={() => handleSaveConfig(scan.id)}
                                                            disabled={saving}
                                                        >
                                                            {saving && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                            Save Config
                                                        </Button>
                                                    </div>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}
        </div>
    );
}
