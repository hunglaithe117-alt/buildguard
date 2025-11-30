"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { Trash2, Plus, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

const fetcher = (url: string) =>
    fetch(process.env.NEXT_PUBLIC_API_URL + url).then((res) => res.json());

interface Token {
    id: string;
    token: string;
    type: string;
    remaining: number;
    reset_time: number;
    disabled: boolean;
    added_at: number;
    last_used: number;
}

export default function TokensPage() {
    const { data: tokens, error, isLoading } = useSWR<Token[]>("/api/tokens", fetcher, {
        refreshInterval: 5000, // Auto-refresh every 5s to see rate limit updates
    });

    const [newToken, setNewToken] = useState("");
    const [isAdding, setIsAdding] = useState(false);

    const handleAddToken = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newToken.trim()) return;

        setIsAdding(true);
        try {
            const res = await fetch(process.env.NEXT_PUBLIC_API_URL + "/api/tokens/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: newToken, type: "pat" }),
            });
            if (res.ok) {
                setNewToken("");
                mutate("/api/tokens");
            } else {
                alert("Failed to add token");
            }
        } catch (err) {
            console.error(err);
            alert("Error adding token");
        } finally {
            setIsAdding(false);
        }
    };

    const handleRemoveToken = async (id: string) => {
        if (!confirm("Are you sure you want to remove this token?")) return;
        try {
            const res = await fetch(process.env.NEXT_PUBLIC_API_URL + `/api/tokens/${id}`, {
                method: "DELETE",
            });
            if (res.ok) {
                mutate("/api/tokens");
            } else {
                alert("Failed to remove token");
            }
        } catch (err) {
            console.error(err);
            alert("Error removing token");
        }
    };

    const formatTime = (timestamp: number) => {
        if (!timestamp) return "-";
        return new Date(timestamp * 1000).toLocaleString();
    };

    const getResetTime = (timestamp: number) => {
        if (!timestamp) return "-";
        const diff = Math.ceil(timestamp - Date.now() / 1000);
        if (diff <= 0) return "Ready";
        return `${diff}s`;
    };

    return (
        <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight">GitHub Tokens</h1>
                <Button variant="outline" size="icon" onClick={() => mutate("/api/tokens")}>
                    <RefreshCw className="h-4 w-4" />
                </Button>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Add New Token</CardTitle>
                    <CardDescription>
                        Add a GitHub Personal Access Token (PAT) to the pool.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleAddToken} className="flex gap-4 items-end">
                        <div className="grid w-full max-w-sm items-center gap-1.5">
                            <Label htmlFor="token">Token</Label>
                            <Input
                                type="password"
                                id="token"
                                placeholder="ghp_..."
                                value={newToken}
                                onChange={(e) => setNewToken(e.target.value)}
                            />
                        </div>
                        <Button type="submit" disabled={isAdding}>
                            {isAdding ? "Adding..." : <><Plus className="mr-2 h-4 w-4" /> Add Token</>}
                        </Button>
                    </form>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Token Pool Status</CardTitle>
                    <CardDescription>
                        Real-time status of all configured tokens.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {isLoading ? (
                        <div>Loading...</div>
                    ) : error ? (
                        <div className="text-red-500">Error loading tokens</div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Token</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Remaining</TableHead>
                                    <TableHead>Reset In</TableHead>
                                    <TableHead>Last Used</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {tokens?.map((token) => (
                                    <TableRow key={token.id}>
                                        <TableCell className="font-mono">{token.token}</TableCell>
                                        <TableCell>
                                            {token.disabled ? (
                                                <Badge variant="destructive">Disabled</Badge>
                                            ) : (
                                                <Badge variant="default" className="bg-green-600 hover:bg-green-700">Active</Badge>
                                            )}
                                        </TableCell>
                                        <TableCell className="w-[200px]">
                                            <div className="flex flex-col gap-1">
                                                <span className="text-xs text-muted-foreground">
                                                    {token.remaining} / 5000
                                                </span>
                                                <Progress value={(token.remaining / 5000) * 100} className="h-2" />
                                            </div>
                                        </TableCell>
                                        <TableCell>{getResetTime(token.reset_time)}</TableCell>
                                        <TableCell>{formatTime(token.last_used)}</TableCell>
                                        <TableCell className="text-right">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="text-destructive hover:text-destructive/90"
                                                onClick={() => handleRemoveToken(token.id)}
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                                {tokens?.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={6} className="text-center text-muted-foreground">
                                            No tokens configured. Add one above.
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
