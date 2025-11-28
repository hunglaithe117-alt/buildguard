import { useState, useEffect } from "react";
import { Loader2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { sonarApi } from "@/lib/api";

interface SonarConfigEditorProps {
    repoId: string;
}

export function SonarConfigEditor({ repoId }: SonarConfigEditorProps) {
    const [content, setContent] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const { toast } = useToast();

    useEffect(() => {
        loadConfig();
    }, [repoId]);

    const loadConfig = async () => {
        try {
            const data = await sonarApi.getConfig(repoId);
            setContent(data.content || "");
        } catch (error) {
            console.error("Failed to load config", error);
            toast({
                title: "Error",
                description: "Failed to load SonarQube configuration.",
                variant: "destructive",
            });
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            await sonarApi.updateConfig(repoId, content);
            toast({
                title: "Success",
                description: "Configuration saved successfully.",
            });
        } catch (error) {
            console.error("Failed to save config", error);
            toast({
                title: "Error",
                description: "Failed to save configuration.",
                variant: "destructive",
            });
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
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
                    <h3 className="text-lg font-medium">SonarQube Configuration</h3>
                    <p className="text-sm text-muted-foreground">
                        Define properties for sonar-project.properties.
                    </p>
                </div>
                <Button onClick={handleSave} disabled={saving}>
                    {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                    Save Config
                </Button>
            </div>
            <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="font-mono text-sm min-h-[300px]"
                placeholder="# sonar-project.properties content..."
            />
        </div>
    );
}
