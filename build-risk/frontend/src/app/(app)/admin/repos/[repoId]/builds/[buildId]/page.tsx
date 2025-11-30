"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useParams, useRouter } from "next/navigation";
import { Loader2, ArrowLeft, RefreshCw, AlertTriangle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { reposApi } from "@/lib/api";
import { BuildDetail } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const Portal = ({ children }: { children: React.ReactNode }) => {
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);
    if (!mounted) return null;
    return createPortal(children, document.body);
};

export default function BuildDetailPage() {
    const params = useParams();
    const router = useRouter();
    const repoId = params.repoId as string;
    const buildId = params.buildId as string;

    const [build, setBuild] = useState<BuildDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [rescanLoading, setRescanLoading] = useState(false);
    const [feedbackOpen, setFeedbackOpen] = useState(false);
    const [feedbackLoading, setFeedbackLoading] = useState(false);
    const [feedbackReason, setFeedbackReason] = useState("");
    const [isFalsePositive, setIsFalsePositive] = useState(false);

    useEffect(() => {
        loadBuild();
    }, [repoId, buildId]);

    const loadBuild = async () => {
        try {
            const data = await reposApi.getBuild(repoId, buildId);
            setBuild(data);
        } catch (err) {
            setError("Failed to load build details");
        } finally {
            setLoading(false);
        }
    };

    const handleRescan = async () => {
        setRescanLoading(true);
        try {
            await reposApi.triggerRescan(repoId, buildId);
            alert("Rescan queued successfully");
        } catch (err) {
            alert("Failed to trigger rescan");
        } finally {
            setRescanLoading(false);
        }
    };

    const handleFeedbackSubmit = async () => {
        setFeedbackLoading(true);
        try {
            await reposApi.submitFeedback(repoId, buildId, {
                is_false_positive: isFalsePositive,
                reason: feedbackReason
            });
            setFeedbackOpen(false);
            alert("Feedback submitted");
            loadBuild();
        } catch (err) {
            alert("Failed to submit feedback");
        } finally {
            setFeedbackLoading(false);
        }
    };

    if (loading) return <div className="flex justify-center p-8"><Loader2 className="animate-spin" /></div>;
    if (error || !build) return <div className="p-8 text-red-500">{error || "Build not found"}</div>;

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" onClick={() => router.back()}>
                    <ArrowLeft className="h-4 w-4" />
                </Button>
                <div>
                    <h1 className="text-2xl font-bold">Build #{build.build_number}</h1>
                    <p className="text-muted-foreground">Commit: {build.commit_sha?.substring(0, 7)}</p>
                </div>
                <div className="ml-auto flex gap-2">
                    <Button
                        variant="outline"
                        onClick={() =>
                            router.push(
                                `/admin/repos/${repoId}/compare?head_build_id=${buildId}`
                            )
                        }
                    >
                        Compare
                    </Button>
                    <Button variant="outline" onClick={handleRescan}>
                        {rescanLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                        Trigger Rescan
                    </Button>
                    <Button variant="outline" onClick={() => setFeedbackOpen(true)}>
                        <AlertTriangle className="mr-2 h-4 w-4" />
                        Report Issue
                    </Button>
                </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
                <Card>
                    <CardHeader>
                        <CardTitle>Build Info</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        <div className="flex justify-between">
                            <span className="text-muted-foreground">Status:</span>
                            <Badge>{build.status}</Badge>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-muted-foreground">Duration:</span>
                            <span>{build.duration}s</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-muted-foreground">Tests:</span>
                            <span>{build.num_tests}</span>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>Risk Factors</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {build.risk_factors && build.risk_factors.length > 0 && (
                            <div className="mb-4 flex flex-wrap gap-2">
                                {build.risk_factors.map((factor) => (
                                    <Badge key={factor} variant="destructive">
                                        {factor}
                                    </Badge>
                                ))}
                            </div>
                        )}
                        <div className="flex justify-between">
                            <span className="text-muted-foreground">Churn:</span>
                            <span>{build.git_diff_src_churn} lines</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-muted-foreground">Team Size:</span>
                            <span>{build.gh_team_size}</span>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {feedbackOpen && (
                <Portal>
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                        <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-slate-950">
                            <div className="mb-4 flex items-center justify-between">
                                <h3 className="text-lg font-semibold">Report Issue</h3>
                                <button onClick={() => setFeedbackOpen(false)}><X className="h-4 w-4" /></button>
                            </div>

                            <div className="space-y-4">
                                <div className="flex items-center space-x-2">
                                    <input
                                        type="checkbox"
                                        id="fp"
                                        checked={isFalsePositive}
                                        onChange={(e) => setIsFalsePositive(e.target.checked)}
                                        className="h-4 w-4 rounded border-gray-300"
                                    />
                                    <Label htmlFor="fp">This is a False Positive</Label>
                                </div>

                                <div className="space-y-2">
                                    <Label>Reason</Label>
                                    <Textarea
                                        value={feedbackReason}
                                        onChange={(e) => setFeedbackReason(e.target.value)}
                                        placeholder="Why is this incorrect?"
                                    />
                                </div>

                                <div className="flex justify-end gap-2 pt-2">
                                    <Button variant="outline" onClick={() => setFeedbackOpen(false)}>Cancel</Button>
                                    <Button onClick={handleFeedbackSubmit} disabled={feedbackLoading}>
                                        {feedbackLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "Submit"}
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </div>
                </Portal>
            )}
        </div>
    );
}
