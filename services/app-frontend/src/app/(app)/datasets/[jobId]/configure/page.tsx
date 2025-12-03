"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { datasetFeaturesApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";

type DatasetFeature = {
    key: string;
    name: string;
    description?: string | null;
    default_source?: string | null;
};

const SOURCE_LABELS: Record<string, string> = {
    build_log_extract: "Build Logs",
    git_history_extract: "Git History",
    repo_snapshot_extract: "Repo Snapshot",
    github_api_extract: "GitHub API",
    csv_mapped: "Manual Upload",
    derived: "Derived",
    metadata: "Metadata",
};

export default function ConfigureExtractionPage() {
    const { jobId } = useParams();
    const jobIdParam = Array.isArray(jobId) ? jobId[0] : jobId;
    const router = useRouter();
    const { toast } = useToast();
    const [features, setFeatures] = useState<DatasetFeature[]>([]);
    const [selectedFeatures, setSelectedFeatures] = useState<Set<string>>(new Set());
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    const loadFeatures = useCallback(async () => {
        if (!jobIdParam) {
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const data = await datasetFeaturesApi.getFeatures(jobIdParam);
            setFeatures(data);
            // Default select all
            setSelectedFeatures(new Set(data.map((f) => f.key || f.name)));
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to load features",
                variant: "destructive",
            });
        } finally {
            setLoading(false);
        }
    }, [jobIdParam, toast]);

    useEffect(() => {
        loadFeatures();
    }, [loadFeatures]);

    const toggleFeature = (key: string) => {
        const newSelected = new Set(selectedFeatures);
        if (newSelected.has(key)) {
            newSelected.delete(key);
        } else {
            newSelected.add(key);
        }
        setSelectedFeatures(newSelected);
    };

    const handleStart = async () => {
        if (!jobIdParam) return;
        setSubmitting(true);
        try {
            await datasetFeaturesApi.startExtraction(
                jobIdParam,
                Array.from(selectedFeatures)
            );
            toast({
                title: "Success",
                description: "Extraction started",
            });
            router.push(`/datasets`);
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to start extraction",
                variant: "destructive",
            });
        } finally {
            setSubmitting(false);
        }
    };

    // Group features by default_source
    const groupedFeatures = features.reduce<Record<string, DatasetFeature[]>>((acc, feature) => {
        const rawType = feature.default_source || "other";
        const label = SOURCE_LABELS[rawType.toLowerCase()] || "Other";
        if (!acc[label]) acc[label] = [];
        acc[label].push(feature);
        return acc;
    }, {});

    if (loading) return <div className="p-10">Loading...</div>;

    return (
        <div className="container mx-auto py-10">
            <h1 className="text-3xl font-bold mb-6">Configure Extraction</h1>

            {features.length === 0 ? (
                <div className="p-6 rounded-lg border text-sm text-muted-foreground">
                    No features available for this job/template.
                </div>
            ) : (
                <div className="grid gap-6">
                    {Object.entries(groupedFeatures).map(([type, list]) => (
                        <Card key={type}>
                            <CardHeader>
                                <CardTitle>{type}</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {list.map((feature) => (
                                        <div key={feature.key} className="flex items-center space-x-2">
                                            <Switch
                                                id={feature.key}
                                                checked={selectedFeatures.has(feature.key)}
                                                onCheckedChange={() => toggleFeature(feature.key)}
                                            />
                                            <Label htmlFor={feature.key} className="flex flex-col">
                                                <span className="font-medium">{feature.name}</span>
                                                <span className="text-xs text-muted-foreground">
                                                    {feature.description || feature.key}
                                                </span>
                                            </Label>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            <div className="mt-8 flex justify-end">
                <Button onClick={handleStart} disabled={submitting}>
                    {submitting ? "Starting..." : "Start Extraction"}
                </Button>
            </div>
        </div>
    );
}
