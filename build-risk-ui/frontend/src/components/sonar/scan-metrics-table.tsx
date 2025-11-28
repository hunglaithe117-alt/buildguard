import { useState, useEffect, useCallback } from "react";
import { Loader2, BarChart3, RefreshCw } from "lucide-react";
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
import { formatTimestamp } from "@/lib/utils";

interface ScanResult {
    id: string;
    repo_id: string;
    job_id: string;
    sonar_project_key: string;
    metrics: Record<string, string | number>;
    created_at: string;
}

interface ScanMetricsTableProps {
    repoId: string;
}

const IMPORTANT_METRICS = [
    "ncloc",
    "complexity",
    "bugs",
    "vulnerabilities",
    "code_smells",
    "coverage",
    "duplicated_lines_density",
];

export function ScanMetricsTable({ repoId }: ScanMetricsTableProps) {
    const [results, setResults] = useState<ScanResult[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const loadResults = useCallback(async () => {
        try {
            const data = await sonarApi.listResults(repoId);
            setResults(data.items);
        } catch (error) {
            console.error("Failed to load scan results", error);
        } finally {
            setLoading(false);
        }
    }, [repoId]);

    useEffect(() => {
        loadResults();
    }, [loadResults]);

    const formatMetricValue = (key: string, value: string | number) => {
        if (typeof value === "number") {
            if (key.includes("density") || key.includes("coverage")) {
                return `${value.toFixed(2)}%`;
            }
            return value.toLocaleString();
        }
        return value;
    };

    const getMetricBadge = (key: string, value: string | number) => {
        const numValue = typeof value === "number" ? value : parseFloat(value as string);

        if (key === "bugs" || key === "vulnerabilities") {
            if (numValue === 0) return <Badge variant="outline" className="border-green-500 text-green-600">Good</Badge>;
            if (numValue < 5) return <Badge variant="outline" className="border-yellow-500 text-yellow-600">Fair</Badge>;
            return <Badge variant="destructive">Poor</Badge>;
        }

        if (key === "code_smells") {
            if (numValue < 10) return <Badge variant="outline" className="border-green-500 text-green-600">Good</Badge>;
            if (numValue < 50) return <Badge variant="outline" className="border-yellow-500 text-yellow-600">Fair</Badge>;
            return <Badge variant="destructive">Poor</Badge>;
        }

        return null;
    };

    if (loading && results.length === 0) {
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
                    <h3 className="text-lg font-medium">Scan Results & Metrics</h3>
                    <p className="text-sm text-muted-foreground">
                        Historical scan metrics from SonarQube
                    </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => loadResults()}>
                    <RefreshCw className="mr-2 h-4 w-4" /> Refresh
                </Button>
            </div>

            {results.length === 0 ? (
                <div className="rounded-md border p-8 text-center">
                    <BarChart3 className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                    <p className="text-muted-foreground">No scan results yet</p>
                </div>
            ) : (
                <div className="rounded-md border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Component Key</TableHead>
                                <TableHead>Lines of Code</TableHead>
                                <TableHead>Bugs</TableHead>
                                <TableHead>Vulnerabilities</TableHead>
                                <TableHead>Code Smells</TableHead>
                                <TableHead>Created At</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {results.map((result) => (
                                <>
                                    <TableRow key={result.id}>
                                        <TableCell className="font-mono text-xs">
                                            {result.sonar_project_key.split('_').pop()?.substring(0, 7) || 'N/A'}
                                        </TableCell>
                                        <TableCell>
                                            {formatMetricValue("ncloc", result.metrics.ncloc || 0)}
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                {formatMetricValue("bugs", result.metrics.bugs || 0)}
                                                {getMetricBadge("bugs", result.metrics.bugs || 0)}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                {formatMetricValue("vulnerabilities", result.metrics.vulnerabilities || 0)}
                                                {getMetricBadge("vulnerabilities", result.metrics.vulnerabilities || 0)}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                {formatMetricValue("code_smells", result.metrics.code_smells || 0)}
                                                {getMetricBadge("code_smells", result.metrics.code_smells || 0)}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {formatTimestamp(result.created_at)}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => setExpandedId(expandedId === result.id ? null : result.id)}
                                            >
                                                {expandedId === result.id ? "Hide" : "Details"}
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                    {expandedId === result.id && (
                                        <TableRow>
                                            <TableCell colSpan={7} className="bg-muted/50">
                                                <div className="p-4">
                                                    <h4 className="font-medium mb-3">All Metrics</h4>
                                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                                        {Object.entries(result.metrics).map(([key, value]) => (
                                                            <div key={key} className="border rounded p-2 bg-background">
                                                                <div className="text-xs text-muted-foreground mb-1">
                                                                    {key.replace(/_/g, ' ').toUpperCase()}
                                                                </div>
                                                                <div className="font-medium">
                                                                    {formatMetricValue(key, value)}
                                                                </div>
                                                            </div>
                                                        ))}
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
