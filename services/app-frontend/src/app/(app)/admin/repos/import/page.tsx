"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Loader2, Github, FileSpreadsheet, CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
    Form,
    FormControl,
    FormDescription,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { api } from "@/lib/api";

const formSchema = z.object({
    source_type: z.enum(["github", "csv"]),
    repo_url: z.string().optional(),
    dataset_template_id: z.string().optional(),
    max_builds: z.coerce.number().min(1).max(1000).optional(),
});

export default function ImportPage() {
    const router = useRouter();
    const { toast } = useToast();
    const [templates, setTemplates] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [csvFile, setCsvFile] = useState<File | null>(null);

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            source_type: "github",
            max_builds: 100,
        },
    });

    const sourceType = form.watch("source_type");

    useEffect(() => {
        api.get("/datasets/templates").then((res) => {
            setTemplates(res.data);
        });
    }, []);

    async function onSubmit(values: z.infer<typeof formSchema>) {
        setIsLoading(true);
        try {
            if (values.source_type === "github" && !values.repo_url) {
                form.setError("repo_url", { message: "Repository URL is required" });
                return;
            }
            if (values.source_type === "csv" && !csvFile) {
                toast({
                    title: "Validation Error",
                    description: "CSV File is required",
                    variant: "destructive",
                });
                return;
            }

            const formData = new FormData();
            formData.append("source_type", values.source_type);
            formData.append("max_builds", values.max_builds?.toString() || "100");

            if (values.dataset_template_id) {
                formData.append("dataset_template_id", values.dataset_template_id);
            }

            if (values.source_type === "github") {
                formData.append("repo_url", values.repo_url || "");
            } else if (values.source_type === "csv" && csvFile) {
                formData.append("csv_file", csvFile);
            }

            await api.post("/dataset-builder/jobs", formData, {
                headers: {
                    "Content-Type": "multipart/form-data",
                },
            });

            toast({
                title: "Import Job Created",
                description: "Your dataset import job has been queued successfully.",
            });

            router.push("/admin/repos");
        } catch (error: any) {
            toast({
                title: "Error",
                description: error.response?.data?.detail || "Something went wrong",
                variant: "destructive",
            });
        } finally {
            setIsLoading(false);
        }
    }

    return (
        <div className="container mx-auto py-10">
            <Card className="max-w-2xl mx-auto">
                <CardHeader>
                    <CardTitle>Import Repository</CardTitle>
                    <CardDescription>
                        Import data from GitHub or CSV for analysis.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Form form={form}>
                        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
                            <FormField
                                control={form.control}
                                name="source_type"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Source Type</FormLabel>
                                        <Select
                                            onValueChange={field.onChange}
                                            defaultValue={field.value}
                                        >
                                            <FormControl>
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select a source" />
                                                </SelectTrigger>
                                            </FormControl>
                                            <SelectContent>
                                                <SelectItem value="github">
                                                    <div className="flex items-center">
                                                        <Github className="mr-2 h-4 w-4" />
                                                        GitHub Repository
                                                    </div>
                                                </SelectItem>
                                                <SelectItem value="csv">
                                                    <div className="flex items-center">
                                                        <FileSpreadsheet className="mr-2 h-4 w-4" />
                                                        CSV Dataset
                                                    </div>
                                                </SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />

                            {sourceType === "github" && (
                                <>
                                    <FormField
                                        control={form.control}
                                        name="repo_url"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel>Repository URL</FormLabel>
                                                <FormControl>
                                                    <Input placeholder="https://github.com/owner/repo" {...field} />
                                                </FormControl>
                                                <FormDescription>
                                                    Public or private repository URL.
                                                </FormDescription>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                    <FormField
                                        control={form.control}
                                        name="max_builds"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel>Max Builds to Import</FormLabel>
                                                <FormControl>
                                                    <Input type="number" {...field} />
                                                </FormControl>
                                                <FormDescription>
                                                    Limit the number of historical builds to fetch (1-1000).
                                                </FormDescription>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                </>
                            )}

                            {sourceType === "csv" && (
                                <FormItem>
                                    <FormLabel>CSV File</FormLabel>
                                    <FormControl>
                                        <Input
                                            type="file"
                                            accept=".csv"
                                            onChange={(e) => {
                                                const file = e.target.files?.[0] || null;
                                                setCsvFile(file);
                                            }}
                                        />
                                    </FormControl>
                                    <FormDescription>
                                        Upload a CSV file with headers: tr_build_id, gh_project_name, git_trigger_commit
                                    </FormDescription>
                                </FormItem>
                            )}

                            <FormField
                                control={form.control}
                                name="dataset_template_id"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Dataset Template (Optional)</FormLabel>
                                        <Select
                                            onValueChange={field.onChange}
                                            defaultValue={field.value}
                                        >
                                            <FormControl>
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select a template" />
                                                </SelectTrigger>
                                            </FormControl>
                                            <SelectContent>
                                                <SelectItem value="">None</SelectItem>
                                                {templates.map((t) => (
                                                    <SelectItem key={t.id} value={t.id}>
                                                        {t.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                        <FormDescription>
                                            Apply a template to guide feature extraction.
                                        </FormDescription>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />

                            <Button type="submit" disabled={isLoading}>
                                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                Start Import
                            </Button>
                        </form>
                    </Form>
                </CardContent>
            </Card>
        </div>
    );
}
