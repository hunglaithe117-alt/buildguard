"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { buildApi, reposApi } from "@/lib/api";
import { BuildDetail, BuildListResponse, CompareResponse } from "@/types";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { ArrowLeft, ArrowRight, Minus, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function ComparePage() {
    const params = useParams();
    const searchParams = useSearchParams();
    const router = useRouter();
    const repoId = params.repoId as string;

    const [builds, setBuilds] = useState<BuildDetail[]>([]);
    const [baseBuildId, setBaseBuildId] = useState<string>(
        searchParams.get("base_build_id") || ""
    );
    const [headBuildId, setHeadBuildId] = useState<string>(
        searchParams.get("head_build_id") || ""
    );
    const [comparison, setComparison] = useState<CompareResponse | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadBuilds();
    }, [repoId]);

    useEffect(() => {
        if (baseBuildId && headBuildId) {
            compare();
        }
    }, [baseBuildId, headBuildId]);

    const loadBuilds = async () => {
        try {
            const res = await buildApi.getByRepo(repoId, { limit: 100 }); // Fetch last 100 builds
            setBuilds(res.items);
        } catch (error) {
            console.error("Failed to load builds", error);
        }
    };

    const compare = async () => {
        setLoading(true);
        try {
            const res = await reposApi.compareBuilds(repoId, baseBuildId, headBuildId);
            setComparison(res);
        } catch (error) {
            console.error("Failed to compare builds", error);
        } finally {
            setLoading(false);
        }
    };

    const formatMetric = (val: number) => {
        if (val > 0) return `+${val}`;
        return val;
    };

    const getMetricColor = (val: number, inverse = false) => {
        if (val === 0) return "text-gray-500";
        if (inverse) {
            return val > 0 ? "text-green-600" : "text-red-600";
        }
        return val > 0 ? "text-red-600" : "text-green-600";
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => router.back()}
                >
                    <ArrowLeft className="h-4 w-4" />
                </Button>
                <h1 className="text-3xl font-bold tracking-tight">Compare Builds</h1>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Select Builds</CardTitle>
                </CardHeader>
                <CardContent className="flex items-center gap-4">
                    <div className="flex-1">
                        <label className="text-sm font-medium mb-1 block">Base Build</label>
                        <Select value={baseBuildId} onValueChange={setBaseBuildId}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select base build" />
                            </SelectTrigger>
                            <SelectContent>
                                {builds.map((b) => (
                                    <SelectItem key={b.id} value={b.id}>
                                        #{b.tr_build_number} ({b.status}) -{" "}
                                        {new Date(b.gh_build_started_at!).toLocaleDateString()}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <ArrowRight className="h-6 w-6 text-muted-foreground mt-6" />
                    <div className="flex-1">
                        <label className="text-sm font-medium mb-1 block">Head Build</label>
                        <Select value={headBuildId} onValueChange={setHeadBuildId}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select head build" />
                            </SelectTrigger>
                            <SelectContent>
                                {builds.map((b) => (
                                    <SelectItem key={b.id} value={b.id}>
                                        #{b.tr_build_number} ({b.status}) -{" "}
                                        {new Date(b.gh_build_started_at!).toLocaleDateString()}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </CardContent>
            </Card>

            {comparison && (
                <div className="grid gap-6 md:grid-cols-2">
                    <Card className="md:col-span-2">
                        <CardHeader>
                            <CardTitle>Metrics Comparison</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                {Object.entries(comparison.metrics_diff).map(([key, delta]) => (
                                    <div key={key} className="p-4 border rounded-lg">
                                        <div className="text-sm text-muted-foreground capitalize">
                                            {key.replace(/_/g, " ")}
                                        </div>
                                        <div className={`text-2xl font-bold ${getMetricColor(delta)}`}>
                                            {formatMetric(delta)}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Files Changed</CardTitle>
                            <CardDescription>
                                Files modified between base and head.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-2 max-h-[400px] overflow-y-auto">
                                {comparison.files_changed.map((file, i) => (
                                    <div key={i} className="flex items-center gap-2 text-sm">
                                        <Badge variant="outline" className="w-8 justify-center">
                                            {file.status}
                                        </Badge>
                                        <span className="truncate" title={file.path}>
                                            {file.path}
                                        </span>
                                    </div>
                                ))}
                                {comparison.files_changed.length === 0 && (
                                    <div className="text-muted-foreground text-sm">
                                        No files changed.
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Commits</CardTitle>
                            <CardDescription>
                                Commits included in this range.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4 max-h-[400px] overflow-y-auto">
                                {comparison.commits.map((commit) => (
                                    <div key={commit.sha} className="border-b pb-2 last:border-0">
                                        <div className="font-medium text-sm truncate">
                                            {commit.message}
                                        </div>
                                        <div className="flex justify-between text-xs text-muted-foreground mt-1">
                                            <span>{commit.author}</span>
                                            <span className="font-mono">{commit.sha.substring(0, 7)}</span>
                                        </div>
                                    </div>
                                ))}
                                {comparison.commits.length === 0 && (
                                    <div className="text-muted-foreground text-sm">
                                        No commits found.
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}
