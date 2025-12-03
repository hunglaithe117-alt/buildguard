"use client";

import { FormEvent, useEffect, useMemo, useState, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import {
    AlertCircle,
    CheckCircle2,
    Loader2,
    RefreshCw,
    Search,
    X,
    Globe,
    Lock,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { integrationApi, reposApi } from "@/lib/api";
import {
    RepoSuggestion,
    RepoImportPayload,
    TestFramework,
    SourceLanguage,
    CIProvider,
} from "@/types";
import { useAuth } from "@/contexts/auth-context";
import { useDebounce } from "@/hooks/use-debounce";

const Portal = ({ children }: { children: React.ReactNode }) => {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    if (!mounted) return null;
    return createPortal(children, document.body);
};

interface ImportRepoModalProps {
    isOpen: boolean;
    onClose: () => void;
    onImport: () => void;
}

export function ImportRepoModal({ isOpen, onClose, onImport }: ImportRepoModalProps) {
    const [step, setStep] = useState<1 | 2>(1);
    const [searchTerm, setSearchTerm] = useState("");
    const [isSearching, setIsSearching] = useState(false);
    const debouncedSearchTerm = useDebounce(searchTerm, 500);
    const lastSearchedTerm = useRef<string | null>(null);

    // Search results
    const [privateMatches, setPrivateMatches] = useState<RepoSuggestion[]>([]);
    const [publicMatches, setPublicMatches] = useState<RepoSuggestion[]>([]);
    const [searchError, setSearchError] = useState<string | null>(null);

    // Selection & Config
    const [selectedRepos, setSelectedRepos] = useState<Record<string, RepoSuggestion>>({});
    const [repoConfigs, setRepoConfigs] = useState<
        Record<string, {
            test_frameworks: string[];
            source_languages: string[];
            ci_provider: string;
            auto_sonar_scan: boolean;
        }>
    >({});

    const [importing, setImporting] = useState(false);
    const [importError, setImportError] = useState<string | null>(null);

    const performSearch = useCallback(async (query: string, force = false) => {
        if (!force && query === lastSearchedTerm.current) return;
        lastSearchedTerm.current = query;

        setIsSearching(true);
        setSearchError(null);
        try {
            const data = await reposApi.search(query.trim() || undefined);
            setPrivateMatches(data.private_matches);
            setPublicMatches(data.public_matches);
        } catch (err) {
            console.error(err);
            setSearchError("Failed to search repositories.");
        } finally {
            setIsSearching(false);
        }
    }, []);

    // Debounce search
    useEffect(() => {
        if (isOpen && debouncedSearchTerm === searchTerm) {
            performSearch(debouncedSearchTerm);
        }
    }, [debouncedSearchTerm, isOpen, searchTerm, performSearch]);

    // Reset state on open
    useEffect(() => {
        if (isOpen) {
            setStep(1);
            setSearchTerm("");
            setSelectedRepos({});
            setRepoConfigs({});
            setPrivateMatches([]);
            setPublicMatches([]);
            setSearchError(null);
            setImportError(null);
            // Initial load (empty search)
            performSearch("", true);
        }
    }, [isOpen, performSearch]);

    const handleSync = async () => {
        setIsSearching(true);
        try {
            await reposApi.sync();
            // Re-run search to update list
            await performSearch(searchTerm, true);
        } catch (err) {
            console.error(err);
            setSearchError("Failed to sync repositories from GitHub.");
            setIsSearching(false);
        }
    };

    const toggleSelection = (repo: RepoSuggestion) => {
        setSelectedRepos((prev) => {
            const next = { ...prev };
            if (next[repo.full_name]) {
                delete next[repo.full_name];
                // Remove config
                setRepoConfigs((current) => {
                    const updated = { ...current };
                    delete updated[repo.full_name];
                    return updated;
                });
            } else {
                next[repo.full_name] = repo;
                // Initialize config
                setRepoConfigs((current) => ({
                    ...current,
                    [repo.full_name]: {
                        test_frameworks: [],
                        source_languages: [],
                        ci_provider: CIProvider.GITHUB_ACTIONS,
                        auto_sonar_scan: false,
                    },
                }));
            }
            return next;
        });
    };

    const selectedList = useMemo(() => Object.values(selectedRepos), [selectedRepos]);

    const handleImport = async () => {
        if (!selectedList.length) return;
        setImporting(true);
        setImportError(null);

        try {
            const payloads: RepoImportPayload[] = selectedList.map((repo) => {
                const config = repoConfigs[repo.full_name];
                return {
                    full_name: repo.full_name,
                    provider: "github",
                    installation_id: repo.installation_id, // Can be undefined for public repos
                    test_frameworks: config.test_frameworks,
                    source_languages: config.source_languages,
                    ci_provider: config.ci_provider,
                    auto_sonar_scan: config.auto_sonar_scan,
                };
            });

            await reposApi.importBulk(payloads);
            onImport(); // Trigger refresh in parent
            onClose();
        } catch (err) {
            console.error(err);
            setImportError("Failed to import repositories. Please try again.");
        } finally {
            setImporting(false);
        }
    };

    const { status, refresh } = useAuth();
    const [isAppInstalled, setIsAppInstalled] = useState(false);
    const [isPolling, setIsPolling] = useState(false);

    // Check installation status on mount and when status changes
    useEffect(() => {
        if (status?.app_installed) {
            setIsAppInstalled(true);
        } else {
            checkInstallation();
        }
    }, [status]);

    const checkInstallation = async () => {
        try {
            const response = await integrationApi.syncInstallations();

            if (response.installations.length > 0) {
                setIsAppInstalled(true);
            }
        } catch (error) {
            console.error("Failed to check installation status", error);
        }
    };

    const handleInstallApp = () => {
        window.open("https://github.com/apps/builddefection", "_blank");
        setIsPolling(true);
    };

    // Polling logic
    useEffect(() => {
        let intervalId: NodeJS.Timeout;
        let attempts = 0;
        const maxAttempts = 24; // 2 minutes (5s interval)

        if (isPolling && !isAppInstalled) {
            intervalId = setInterval(async () => {
                attempts++;
                await checkInstallation();

                // If installed (checked via effect on status) or max attempts reached
                if (attempts >= maxAttempts) {
                    setIsPolling(false);
                }
            }, 5000);
        }

        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    }, [isPolling, isAppInstalled]);

    // Stop polling if installed
    useEffect(() => {
        if (isAppInstalled) {
            setIsPolling(false);
        }
    }, [isAppInstalled]);

    if (!isOpen) return null;

    return (
        <Portal>
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
                <div className="w-full max-w-3xl rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-950 border dark:border-slate-800">
                    <div className="mb-6 flex items-center justify-between">
                        <div>
                            <h2 className="text-xl font-semibold">Import Repositories</h2>
                            <p className="text-sm text-muted-foreground">
                                Step {step} of 2: {step === 1 ? "Select repositories" : "Configure settings"}
                            </p>
                        </div>
                        <button
                            type="button"
                            className="rounded-full p-2 text-muted-foreground hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            onClick={onClose}
                        >
                            <X className="h-5 w-5" />
                        </button>
                    </div>

                    {!isAppInstalled ? (
                        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/50 dark:bg-amber-900/20">
                            <div className="flex items-start gap-3">
                                <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5" />
                                <div className="flex-1">
                                    <h3 className="text-sm font-medium text-amber-900 dark:text-amber-200">
                                        GitHub App Required
                                    </h3>
                                    <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
                                        To import private repositories and enable automatic build tracking, you must install the BuildGuard GitHub App.
                                    </p>
                                    <div className="mt-3 flex items-center gap-3">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="border-amber-200 bg-white text-amber-900 hover:bg-amber-50 hover:text-amber-900 dark:border-amber-800 dark:bg-slate-950 dark:text-amber-200 dark:hover:bg-amber-900/20"
                                            onClick={handleInstallApp}
                                            disabled={isPolling}
                                        >
                                            {isPolling ? (
                                                <>
                                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                    Checking installation...
                                                </>
                                            ) : (
                                                "Install GitHub App"
                                            )}
                                        </Button>
                                        {isPolling && (
                                            <span className="text-xs text-amber-700 dark:text-amber-300 animate-pulse">
                                                Listening for installation...
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="mb-6 rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-900/50 dark:bg-green-900/20">
                            <div className="flex items-center gap-3">
                                <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
                                <div>
                                    <h3 className="text-sm font-medium text-green-900 dark:text-green-200">
                                        GitHub App Connected
                                    </h3>
                                    <p className="text-sm text-green-700 dark:text-green-300">
                                        Your private repositories are ready to be imported.
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {step === 1 ? (
                        <div className="space-y-6">
                            <div className="flex gap-2">
                                <div className="relative flex-1">
                                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                    <input
                                        type="text"
                                        className="w-full rounded-lg border bg-transparent pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                                        placeholder="Search repositories (e.g. owner/repo)..."
                                        value={searchTerm}
                                        onChange={(e) => setSearchTerm(e.target.value)}
                                    />
                                </div>
                                <Button
                                    variant="outline"
                                    onClick={handleSync}
                                    title="Sync private repositories from GitHub App"
                                    disabled={isSearching}
                                >
                                    <RefreshCw className={`h-4 w-4 ${isSearching ? "animate-spin" : ""}`} />
                                </Button>
                            </div>

                            <div className="h-[400px] overflow-y-auto pr-2 space-y-6">
                                {searchError && (
                                    <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
                                        {searchError}
                                    </div>
                                )}

                                {/* Private Repos Section */}
                                <div>
                                    <h3 className="mb-3 text-sm font-medium text-muted-foreground flex items-center gap-2">
                                        <Lock className="h-3 w-3" /> Your Repositories (App Installed)
                                    </h3>
                                    <div className="space-y-2">
                                        {privateMatches.length === 0 && !isSearching ? (
                                            <div className="text-sm text-muted-foreground italic px-2">
                                                No matching private repositories found.
                                            </div>
                                        ) : (
                                            privateMatches.map((repo) => (
                                                <RepoItem
                                                    key={repo.full_name}
                                                    repo={repo}
                                                    isSelected={!!selectedRepos[repo.full_name]}
                                                    onToggle={() => toggleSelection(repo)}
                                                />
                                            ))
                                        )}
                                    </div>
                                </div>

                                {/* Public Repos Section */}
                                <div>
                                    <h3 className="mb-3 text-sm font-medium text-muted-foreground flex items-center gap-2">
                                        <Globe className="h-3 w-3" /> Public GitHub Repositories
                                    </h3>
                                    <div className="space-y-2">
                                        {publicMatches.length === 0 && !isSearching ? (
                                            <div className="text-sm text-muted-foreground italic px-2">
                                                {searchTerm.length >= 3
                                                    ? "No matching public repositories found."
                                                    : "Type at least 3 characters to search public repositories."}
                                            </div>
                                        ) : (
                                            publicMatches.map((repo) => (
                                                <RepoItem
                                                    key={repo.full_name}
                                                    repo={repo}
                                                    isSelected={!!selectedRepos[repo.full_name]}
                                                    onToggle={() => toggleSelection(repo)}
                                                />
                                            ))
                                        )}
                                    </div>
                                </div>

                                {isSearching && (
                                    <div className="flex justify-center py-4">
                                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <div className="h-[400px] overflow-y-auto pr-2 space-y-4">
                                {selectedList.map((repo) => (
                                    <RepoConfigItem
                                        key={repo.full_name}
                                        repo={repo}
                                        config={repoConfigs[repo.full_name]}
                                        onChange={(newConfig) =>
                                            setRepoConfigs((prev) => ({
                                                ...prev,
                                                [repo.full_name]: newConfig,
                                            }))
                                        }
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="mt-6 flex items-center justify-between border-t pt-4">
                        <Button variant="ghost" onClick={onClose}>
                            Cancel
                        </Button>
                        <div className="flex gap-2">
                            {step === 2 && (
                                <Button variant="outline" onClick={() => setStep(1)}>
                                    Back
                                </Button>
                            )}
                            {step === 1 ? (
                                <Button
                                    onClick={() => setStep(2)}
                                    disabled={selectedList.length === 0}
                                >
                                    Next ({selectedList.length})
                                </Button>
                            ) : (
                                <Button onClick={handleImport} disabled={importing}>
                                    {importing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                    Import {selectedList.length} Repositories
                                </Button>
                            )}
                        </div>
                    </div>

                    {importError && (
                        <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
                            {importError}
                        </div>
                    )}
                </div>
            </div>
        </Portal>
    );
}

function RepoItem({
    repo,
    isSelected,
    onToggle,
}: {
    repo: RepoSuggestion;
    isSelected: boolean;
    onToggle: () => void;
}) {
    return (
        <label className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${isSelected ? 'bg-slate-50 border-primary/50 dark:bg-slate-900' : 'hover:bg-slate-50 dark:hover:bg-slate-900/50'}`}>
            <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                checked={isSelected}
                onChange={onToggle}
            />
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{repo.full_name}</span>
                    {repo.private && (
                        <Badge variant="secondary" className="text-[10px] h-5 px-1.5">Private</Badge>
                    )}
                </div>
                <p className="text-sm text-muted-foreground line-clamp-1">
                    {repo.description || "No description provided"}
                </p>
            </div>
        </label>
    );
}

function RepoConfigItem({
    repo,
    config,
    onChange,
}: {
    repo: RepoSuggestion;
    config: {
        test_frameworks: string[];
        source_languages: string[];
        ci_provider: string;
        auto_sonar_scan: boolean;
    };
    onChange: (config: any) => void;
}) {
    const toggleFramework = (framework: string) => {
        const current = config.test_frameworks;
        const next = current.includes(framework)
            ? current.filter((f) => f !== framework)
            : [...current, framework];
        onChange({ ...config, test_frameworks: next });
    };

    const toggleLanguage = (language: string) => {
        const current = config.source_languages;
        const next = current.includes(language)
            ? current.filter((l) => l !== language)
            : [...current, language];
        onChange({ ...config, source_languages: next });
    };

    return (
        <div className="rounded-xl border p-4 space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="font-semibold">{repo.full_name}</h3>
                <Badge variant="outline">{repo.private ? "Private" : "Public"}</Badge>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
                <div>
                    <label className="text-xs font-semibold text-muted-foreground uppercase mb-2 block">
                        Test Frameworks
                    </label>
                    <div className="space-y-3">
                        {/* Python Frameworks */}
                        <div>
                            <span className="text-[10px] font-medium text-muted-foreground uppercase mb-1 block">Python</span>
                            <div className="grid grid-cols-2 gap-2">
                                {[TestFramework.PYTEST, TestFramework.UNITTEST].map((fw) => (
                                    <label key={fw} className="flex items-center gap-2 text-sm cursor-pointer">
                                        <input
                                            type="checkbox"
                                            className="rounded border-gray-300"
                                            checked={config.test_frameworks.includes(fw)}
                                            onChange={() => toggleFramework(fw)}
                                        />
                                        {fw}
                                    </label>
                                ))}
                            </div>
                        </div>

                        {/* Ruby Frameworks */}
                        <div>
                            <span className="text-[10px] font-medium text-muted-foreground uppercase mb-1 block">Ruby</span>
                            <div className="grid grid-cols-2 gap-2">
                                {[TestFramework.RSPEC, TestFramework.MINITEST, TestFramework.TESTUNIT, TestFramework.CUCUMBER].map((fw) => (
                                    <label key={fw} className="flex items-center gap-2 text-sm cursor-pointer">
                                        <input
                                            type="checkbox"
                                            className="rounded border-gray-300"
                                            checked={config.test_frameworks.includes(fw)}
                                            onChange={() => toggleFramework(fw)}
                                        />
                                        {fw}
                                    </label>
                                ))}
                            </div>
                        </div>

                        {/* Java Frameworks */}
                        <div>
                            <span className="text-[10px] font-medium text-muted-foreground uppercase mb-1 block">Java</span>
                            <div className="grid grid-cols-2 gap-2">
                                {[TestFramework.JUNIT, TestFramework.TESTNG].map((fw) => (
                                    <label key={fw} className="flex items-center gap-2 text-sm cursor-pointer">
                                        <input
                                            type="checkbox"
                                            className="rounded border-gray-300"
                                            checked={config.test_frameworks.includes(fw)}
                                            onChange={() => toggleFramework(fw)}
                                        />
                                        {fw}
                                    </label>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="space-y-4">
                    <div>
                        <label className="text-xs font-semibold text-muted-foreground uppercase mb-2 block">
                            Source Languages
                        </label>
                        <div className="grid grid-cols-2 gap-2">
                            {[SourceLanguage.PYTHON, SourceLanguage.RUBY, SourceLanguage.JAVA].map((lang) => (
                                <label key={lang} className="flex items-center gap-2 text-sm cursor-pointer">
                                    <input
                                        type="checkbox"
                                        className="rounded border-gray-300"
                                        checked={config.source_languages.includes(lang)}
                                        onChange={() => toggleLanguage(lang)}
                                    />
                                    {lang}
                                </label>
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="text-xs font-semibold text-muted-foreground uppercase mb-2 block">
                            CI Provider
                        </label>
                        <select
                            className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm"
                            value={config.ci_provider}
                            onChange={(e) => onChange({ ...config, ci_provider: e.target.value })}
                        >
                            <option value={CIProvider.GITHUB_ACTIONS}>GitHub Actions</option>
                        </select>
                    </div>

                    <div>
                        <label className="text-xs font-semibold text-muted-foreground uppercase mb-2 block">
                            SonarQube Scanning
                        </label>
                        <label className="flex items-center gap-2 text-sm cursor-pointer">
                            <input
                                type="checkbox"
                                className="rounded border-gray-300"
                                checked={config.auto_sonar_scan}
                                onChange={(e) => onChange({ ...config, auto_sonar_scan: e.target.checked })}
                            />
                            Auto-scan new commits
                        </label>
                        <p className="text-[10px] text-muted-foreground mt-1">
                            If disabled, you can manually trigger scans for individual commits later.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
