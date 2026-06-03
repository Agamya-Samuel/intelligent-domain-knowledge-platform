"use client";

import { useSession, signOut } from "next-auth/react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

/* ── Settings Page Component ───────────────────────────────────────── */

export default function SettingsPage() {
  const { data: session, status } = useSession();
  const [saved, setSaved] = useState(false);

  if (status === "loading") {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center">Sign in required</CardTitle>
          </CardHeader>
          <CardContent className="text-center text-sm text-muted-foreground">
            Please sign in to access settings.
          </CardContent>
        </Card>
      </div>
    );
  }

  const userEmail = session.user?.email ?? "";
  const userName = session.user?.name ?? "";

  return (
    <div className="mx-auto max-w-2xl p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your account and application preferences.
        </p>
      </div>

      {/* Profile Section */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Profile</CardTitle>
          <CardDescription>Your account information.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Display Name</Label>
            <Input
              id="name"
              defaultValue={userName}
              placeholder="Your name"
              disabled
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              defaultValue={userEmail}
              type="email"
              disabled
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Profile information is managed through your authentication provider.
          </p>
        </CardContent>
      </Card>

      {/* Model Preferences */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Model Preferences</CardTitle>
          <CardDescription>
            Default settings for model selection and inference.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Default Model Variant</p>
              <p className="text-xs text-muted-foreground">
                Choose between base and fine-tuned model for new sessions.
              </p>
            </div>
            <select
              className="h-9 rounded-lg border border-input bg-background px-3 text-sm"
              defaultValue="base"
            >
              <option value="base">Base Model</option>
              <option value="finetuned">Fine-tuned Model</option>
            </select>
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Advanced RAG</p>
              <p className="text-xs text-muted-foreground">
                Enable hybrid retrieval, reranking, and query expansion.
              </p>
            </div>
            <label className="relative inline-flex cursor-pointer items-center">
              <input type="checkbox" defaultChecked className="peer sr-only" />
              <div className="h-5 w-9 rounded-full bg-muted peer-checked:bg-primary after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-4" />
            </label>
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Streaming Responses</p>
              <p className="text-xs text-muted-foreground">
                Stream tokens as they are generated (vs. waiting for full response).
              </p>
            </div>
            <label className="relative inline-flex cursor-pointer items-center">
              <input type="checkbox" defaultChecked className="peer sr-only" />
              <div className="h-5 w-9 rounded-full bg-muted peer-checked:bg-primary after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-4" />
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Budget & Usage */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Budget & Usage</CardTitle>
          <CardDescription>
            Monthly budget limit and cost tracking.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm">Monthly Budget Limit</span>
            <span className="text-sm font-semibold">$30.00</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              Hard block enforced at limit. No overspend allowed.
            </span>
          </div>
          <Separator />
          <p className="text-xs text-muted-foreground">
            Budget resets at the start of each month. View detailed
            usage in the Analytics dashboard.
          </p>
        </CardContent>
      </Card>

      {/* Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Account Actions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setSaved(true);
                setTimeout(() => setSaved(false), 2000);
              }}
            >
              {saved ? "Saved!" : "Save Preferences"}
            </Button>
            <Button
              variant="destructive"
              onClick={() => signOut({ callbackUrl: "/login" })}
            >
              Sign Out
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
