"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { datasetsApi } from "@/lib/api";
import { Loader2, Upload, FileSpreadsheet, Github } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

enum DatasetSource {
    CSV_UPLOAD = "csv_upload",
    GITHUB_IMPORT = "github_import",
}

export default function NewDatasetPage() {
    const router = useRouter();
    const { toast } = useToast();
    const [step, setStep] = useState(1);
    const [loading, setLoading] = useState(false);

    // Form State
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [sourceType, setSourceType] = useState<DatasetSource>(
        DatasetSource.CSV_UPLOAD
    );
    const [templates, setTemplates] = useState<any[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<string>("");

    // CSV State
    const [csvFile, setCsvFile] = useState<File | null>(null);
    const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
    const [csvPreview, setCsvPreview] = useState<any[]>([]);
    const [mandatoryMapping, setMandatoryMapping] = useState({
        tr_build_id: "",
        gh_project_name: "",
        git_trigger_commit: "",
    });

    // GitHub State
    const [repoUrl, setRepoUrl] = useState("");

    useEffect(() => {
        loadTemplates();
    }, []);

    const loadTemplates = async () => {
        try {
            const data = await datasetsApi.listTemplates();
            setTemplates(data);
            if (data.length > 0) {
                setSelectedTemplate(data[0]._id);
            }
        } catch (error) {
            console.error("Failed to load templates", error);
        }
    };

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            setCsvFile(file);
            setLoading(true);
            try {
                const data = await datasetsApi.uploadCsvPreview(file);
                setCsvHeaders(data.headers);
                setCsvPreview(data.sample_rows);

                // Auto-guess mapping
                const guessMapping = { ...mandatoryMapping };
                data.headers.forEach(header => {
                    const h = header.toLowerCase();
                    if (h.includes("build") && h.includes("id")) guessMapping.tr_build_id = header;
                    if (h.includes("project") || h.includes("slug")) guessMapping.gh_project_name = header;
                    if (h.includes("commit") || h.includes("sha")) guessMapping.git_trigger_commit = header;
                });
                setMandatoryMapping(guessMapping);

            } catch (error) {
                toast({
                    title: "Error parsing CSV",
                    description: "Could not read the CSV file. Please check the format.",
                    variant: "destructive",
                });
                setCsvFile(null);
            } finally {
                setLoading(false);
            }
        }
    };

    const handleSubmit = async () => {
        setLoading(true);
        try {
            const payload = {
                name,
                description,
                source_type: sourceType,
                template_id: selectedTemplate,
                config: {
                    // GitHub Config
                    ...(sourceType === DatasetSource.GITHUB_IMPORT && {
                        repo_url: repoUrl,
                        build_limit: 100,
                    }),
                    // CSV Config
                    ...(sourceType === DatasetSource.CSV_UPLOAD && {
                        file_path: csvFile?.name, // In real app, this should be the uploaded path/ID
                        mandatory_mapping: mandatoryMapping,
                    }),
                },
            };

            const res = await datasetsApi.createDataset(payload);
            toast({
                title: "Dataset Created",
                description: "Your dataset has been initialized.",
            });
            router.push(`/datasets/${res.id}/configure`);
        } catch (error: any) {
            toast({
                title: "Creation Failed",
                description: error.response?.data?.detail || "Something went wrong.",
                variant: "destructive",
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="container max-w-4xl py-8">
            <h1 className="text-3xl font-bold mb-6">Create New Dataset</h1>

            <div className="grid gap-6">
                {/* Step 1: Basic Info & Source */}
                <Card>
                    <CardHeader>
                        <CardTitle>1. Dataset Details</CardTitle>
                        <CardDescription>
                            Choose how you want to construct your dataset.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid gap-2">
                            <Label>Dataset Name</Label>
                            <Input
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="e.g. My Custom Analysis"
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label>Description (Optional)</Label>
                            <Input
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="Brief description of this dataset"
                            />
                        </div>

                        <div className="grid gap-2">
                            <Label>Source Type</Label>
                            <Tabs
                                value={sourceType}
                                onValueChange={(v) => setSourceType(v as DatasetSource)}
                                className="w-full"
                            >
                                <TabsList className="grid w-full grid-cols-2">
                                    <TabsTrigger value={DatasetSource.CSV_UPLOAD}>
                                        <FileSpreadsheet className="mr-2 h-4 w-4" />
                                        CSV Upload
                                    </TabsTrigger>
                                    <TabsTrigger value={DatasetSource.GITHUB_IMPORT}>
                                        <Github className="mr-2 h-4 w-4" />
                                        GitHub Import
                                    </TabsTrigger>
                                </TabsList>
                                <TabsContent value={DatasetSource.CSV_UPLOAD} className="pt-4">
                                    <div className="rounded-md border border-dashed p-8 text-center">
                                        <div className="mx-auto flex max-w-[420px] flex-col items-center justify-center text-center">
                                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                                                <Upload className="h-5 w-5" />
                                            </div>
                                            <h3 className="mt-4 text-lg font-semibold">
                                                Upload your CSV
                                            </h3>
                                            <p className="mb-4 mt-2 text-sm text-muted-foreground">
                                                Drag and drop or click to upload. Must contain build ID,
                                                project name, and commit SHA.
                                            </p>
                                            <Input
                                                type="file"
                                                accept=".csv"
                                                onChange={handleFileChange}
                                                className="max-w-xs"
                                            />
                                        </div>
                                    </div>
                                </TabsContent>
                                <TabsContent
                                    value={DatasetSource.GITHUB_IMPORT}
                                    className="pt-4"
                                >
                                    <div className="grid gap-2">
                                        <Label>Repository URL</Label>
                                        <Input
                                            value={repoUrl}
                                            onChange={(e) => setRepoUrl(e.target.value)}
                                            placeholder="https://github.com/owner/repo"
                                        />
                                        <p className="text-sm text-muted-foreground">
                                            We will scan this repository to extract build history.
                                        </p>
                                    </div>
                                </TabsContent>
                            </Tabs>
                        </div>

                        <div className="grid gap-2">
                            <Label>Template</Label>
                            <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select a template" />
                                </SelectTrigger>
                                <SelectContent>
                                    {templates.map(t => (
                                        <SelectItem key={t._id} value={t._id}>{t.name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </CardContent>
                </Card>

                {/* Step 2: CSV Mapping (Only if CSV) */}
                {sourceType === DatasetSource.CSV_UPLOAD && csvFile && (
                    <Card>
                        <CardHeader>
                            <CardTitle>2. Map Mandatory Columns</CardTitle>
                            <CardDescription>
                                We need to know which columns in your CSV correspond to these
                                required fields.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div className="space-y-2">
                                    <Label>Build ID</Label>
                                    <Select
                                        value={mandatoryMapping.tr_build_id}
                                        onValueChange={(v) =>
                                            setMandatoryMapping({ ...mandatoryMapping, tr_build_id: v })
                                        }
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Select column" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {csvHeaders.map((h) => (
                                                <SelectItem key={h} value={h}>
                                                    {h}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label>Project Name</Label>
                                    <Select
                                        value={mandatoryMapping.gh_project_name}
                                        onValueChange={(v) =>
                                            setMandatoryMapping({
                                                ...mandatoryMapping,
                                                gh_project_name: v,
                                            })
                                        }
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Select column" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {csvHeaders.map((h) => (
                                                <SelectItem key={h} value={h}>
                                                    {h}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label>Trigger Commit</Label>
                                    <Select
                                        value={mandatoryMapping.git_trigger_commit}
                                        onValueChange={(v) =>
                                            setMandatoryMapping({
                                                ...mandatoryMapping,
                                                git_trigger_commit: v,
                                            })
                                        }
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Select column" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {csvHeaders.map((h) => (
                                                <SelectItem key={h} value={h}>
                                                    {h}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            {/* Preview Table */}
                            <div className="mt-4 rounded-md border">
                                <div className="p-4 bg-muted/50 border-b">
                                    <h4 className="font-medium">File Preview (First 5 rows)</h4>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="border-b">
                                                {csvHeaders.map((h) => (
                                                    <th key={h} className="h-10 px-4 text-left font-medium">
                                                        {h}
                                                    </th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {csvPreview.map((row, i) => (
                                                <tr key={i} className="border-b last:border-0">
                                                    {csvHeaders.map((h) => (
                                                        <td key={h} className="h-10 px-4">
                                                            {row[h]}
                                                        </td>
                                                    ))}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}

                <div className="flex justify-end">
                    <Button
                        size="lg"
                        onClick={handleSubmit}
                        disabled={
                            loading ||
                            !name ||
                            (sourceType === DatasetSource.CSV_UPLOAD &&
                                (!csvFile ||
                                    !mandatoryMapping.tr_build_id ||
                                    !mandatoryMapping.gh_project_name ||
                                    !mandatoryMapping.git_trigger_commit)) ||
                            (sourceType === DatasetSource.GITHUB_IMPORT && !repoUrl)
                        }
                    >
                        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Create & Configure Features
                    </Button>
                </div>
            </div>
        </div>
    );
}
