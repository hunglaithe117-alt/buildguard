"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { datasetFeaturesApi, datasetBuilderApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

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
    const [job, setJob] = useState<any>(null);
    const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
    const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});

    const loadData = useCallback(async () => {
        if (!jobIdParam) {
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const [featuresData, jobData] = await Promise.all([
                datasetFeaturesApi.getFeatures(jobIdParam),
                datasetBuilderApi.getJob(jobIdParam)
            ]);

            setFeatures(featuresData);
            setJob(jobData);

            // Default select all
            setSelectedFeatures(new Set(featuresData.map((f: any) => f.key || f.name)));

            if (jobData.source_type === 'csv' && jobData.dataset_template_id) {
                // Analyze mapping for CSV
                try {
                    const analysis = await datasetBuilderApi.analyzeMapping(jobIdParam, jobData.dataset_template_id);
                    setCsvHeaders(analysis.csv_headers || []);

                    // Pre-fill mapping from suggestions
                    const initialMapping: Record<string, string> = {};
                    analysis.feature_mappings?.forEach((m: any) => {
                        if (m.mapping_suggestion?.csv_column) {
                            initialMapping[m.feature.key] = m.mapping_suggestion.csv_column;
                        }
                    });
                    setColumnMapping(initialMapping);
                } catch (e) {
                    console.error("Failed to analyze mapping", e);
                }
            }

        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to load job data",
                variant: "destructive",
            });
        } finally {
            setLoading(false);
        }
    }, [jobIdParam, toast]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const toggleFeature = (key: string) => {
        const newSelected = new Set(selectedFeatures);
        if (newSelected.has(key)) {
            newSelected.delete(key);
        } else {
            newSelected.add(key);
        }
        setSelectedFeatures(newSelected);
    };

    const handleMappingChange = (featureKey: string, column: string) => {
        setColumnMapping(prev => ({
            ...prev,
            [featureKey]: column
        }));
    };

    const handleStart = async () => {
        if (!jobIdParam) return;

        // Validation for CSV
        if (job?.source_type === 'csv') {
            const mandatory = ["tr_build_id", "gh_project_name", "git_trigger_commit"];
            const missing = mandatory.filter(field => !columnMapping[field]);

            if (missing.length > 0) {
                toast({
                    title: "Validation Error",
                    description: `Missing mandatory mapping for: ${missing.join(", ")}`,
                    variant: "destructive",
                });
                return;
            }
        }

        setSubmitting(true);
        try {
            await datasetFeaturesApi.startExtraction(
                jobIdParam,
                Array.from(selectedFeatures),
                {},
                columnMapping
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
                                        <div key={feature.key} className="flex flex-col space-y-2 p-2 border rounded">
                                            <div className="flex items-center space-x-2">
                                                <Switch
                                                    id={feature.key}
                                                    checked={selectedFeatures.has(feature.key)}
                                                    onCheckedChange={() => toggleFeature(feature.key)}
                                                    disabled={["tr_build_id", "gh_project_name", "git_trigger_commit"].includes(feature.key)}
                                                />
                                                <Label htmlFor={feature.key} className="flex flex-col">
                                                    <span className="font-medium">{feature.name}</span>
                                                    <span className="text-xs text-muted-foreground">
                                                        {feature.description || feature.key}
                                                    </span>
                                                </Label>
                                            </div>

                                            {job?.source_type === 'csv' && selectedFeatures.has(feature.key) && (
                                                <div className="mt-2">
                                                    <Select
                                                        value={columnMapping[feature.key] || ""}
                                                        onValueChange={(val) => handleMappingChange(feature.key, val)}
                                                    >
                                                        <SelectTrigger className="w-full h-8 text-xs">
                                                            <SelectValue placeholder="Map to column..." />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {csvHeaders.map(header => (
                                                                <SelectItem key={header} value={header}>
                                                                    {header}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                    {["tr_build_id", "gh_project_name", "git_trigger_commit"].includes(feature.key) && (
                                                        <span className="text-[10px] text-red-500 font-semibold">* Required</span>
                                                    )}
                                                </div>
                                            )}
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
