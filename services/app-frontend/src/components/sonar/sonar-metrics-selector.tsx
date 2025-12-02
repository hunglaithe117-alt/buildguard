"use client";

import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { reposApi, sonarApi } from "@/lib/api";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

interface SonarMetricsSelectorProps {
    repoId: string;
}

export function SonarMetricsSelector({ repoId }: SonarMetricsSelectorProps) {
    const [availableMetrics, setAvailableMetrics] = useState<string[]>([]);
    const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const { toast } = useToast();

    useEffect(() => {
        const loadData = async () => {
            try {
                const [available, current] = await Promise.all([
                    sonarApi.getAvailableMetrics(),
                    reposApi.getMetrics(repoId),
                ]);
                setAvailableMetrics(available);
                // If current is empty/null, it might mean "use default" or "none selected".
                // For now, if it's null/empty, we might want to pre-select all or none.
                // But the backend returns [] if null.
                // Ideally, if it's the first time, maybe we should show what's currently active (default).
                // But the API returns the *custom* config.
                // If custom config is empty, it uses default.
                // To make it clear, maybe we should have a "Use Default" toggle?
                // For now, let's just assume explicit selection.
                // If current is empty, we start with empty.
                // Wait, if the user wants to use default, they should clear the list?
                // Or maybe we pre-fill with available if it's empty?
                // Let's stick to: what you see is what you get.
                // If the backend returns [], it means no *custom* metrics.
                // But the backend logic says: if custom_metrics is None, use default.
                // If custom_metrics is [], use [].
                // The API `get_repository_metrics` returns `repo.sonar_metrics or []`.
                // So we can't distinguish between "not set" and "empty set".
                // However, `sonar_metrics` in DB is Optional.
                // If I want to support "Use Default", I might need to handle `null`.
                // But the API returns `[]` for null.
                // Let's assume for this UI, we just manage the list.
                // If the user saves an empty list, they get no metrics?
                // Or should we initialize with `available` if it's empty?
                // Let's initialize with `available` if `current` is empty, assuming they want everything by default.
                // actually, if `current` is empty, it means they haven't customized it yet (likely).
                // So showing all checked is a good default visual.
                if (!current || current.length === 0) {
                    setSelectedMetrics(available);
                } else {
                    setSelectedMetrics(current);
                }
            } catch (error) {
                console.error("Failed to load metrics", error);
                toast({
                    title: "Error",
                    description: "Failed to load metrics configuration.",
                    variant: "destructive",
                });
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, [repoId, toast]);

    const handleToggle = (metric: string) => {
        setSelectedMetrics((prev) =>
            prev.includes(metric)
                ? prev.filter((m) => m !== metric)
                : [...prev, metric]
        );
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            await reposApi.updateMetrics(repoId, selectedMetrics);
            toast({
                title: "Success",
                description: "Metrics configuration updated.",
            });
        } catch (error) {
            console.error("Failed to save metrics", error);
            toast({
                title: "Error",
                description: "Failed to save metrics configuration.",
                variant: "destructive",
            });
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return <Loader2 className="h-6 w-6 animate-spin" />;
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div className="text-sm text-muted-foreground">
                    Select the metrics to be collected during SonarQube scans.
                </div>
                <div className="text-sm font-medium">
                    {selectedMetrics.length} selected
                </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[400px] overflow-y-auto p-1">
                {availableMetrics.map((metric) => (
                    <div key={metric} className="flex items-center space-x-2 border p-3 rounded-md hover:bg-accent/50 transition-colors">
                        <Switch
                            id={`metric-${metric}`}
                            checked={selectedMetrics.includes(metric)}
                            onCheckedChange={() => handleToggle(metric)}
                        />
                        <Label htmlFor={`metric-${metric}`} className="cursor-pointer font-mono text-xs flex-1 break-all">
                            {metric}
                        </Label>
                    </div>
                ))}
            </div>
            <div className="flex justify-end pt-4 border-t">
                <Button onClick={handleSave} disabled={saving}>
                    {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    <Save className="mr-2 h-4 w-4" />
                    Save Changes
                </Button>
            </div>
        </div>
    );
}
