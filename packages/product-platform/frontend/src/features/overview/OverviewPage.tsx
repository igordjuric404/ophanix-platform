import { Activity, Database, LoaderCircle, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { useCurrentUser } from "../../api/auth";
import { useSystemDependencies, useVersionInfo } from "../../api/system";
import { DataTable } from "../../components/shared/DataTable";
import { ErrorState } from "../../components/shared/ErrorState";
import { MetricCard } from "../../components/shared/MetricCard";
import { LoadingState } from "../../components/shared/LoadingState";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";

export function OverviewPage() {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const currentUser = useCurrentUser();
  const dependencies = useSystemDependencies();
  const version = useVersionInfo();

  if (dependencies.isLoading || version.isLoading) {
    return <LoadingState label="Loading platform overview" />;
  }

  if (dependencies.isError || version.isError) {
    const error = dependencies.error ?? version.error;
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : "Unable to load platform overview."}
          onRetry={() => {
            void dependencies.refetch();
            void version.refetch();
          }}
        />
      </div>
    );
  }

  const dependencyItems = dependencies.data ?? [];
  const healthyCount = dependencyItems.filter(
    (item) => item.status.toLowerCase() === "healthy"
  ).length;
  const user = currentUser.data;
  const refreshOverview = async () => {
    setIsRefreshing(true);
    try {
      await Promise.allSettled([
        currentUser.refetch(),
        dependencies.refetch(),
        version.refetch()
      ]);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <>
      <PageHeader
        action={
          <Button disabled={isRefreshing} onClick={refreshOverview} type="button" variant="outline">
            {isRefreshing ? "Refreshing" : "Refresh"}
          </Button>
        }
        description="Governed estate summary, runtime health, and product platform readiness."
        title="Overview"
      />
      <section className="relative space-y-5 p-6">
        {isRefreshing ? (
          <div
            className="absolute inset-0 z-20 flex items-center justify-center bg-background/70 backdrop-blur-sm"
            role="status"
          >
            <div className="flex items-center gap-2 rounded-md border border-border/80 bg-card px-4 py-3 text-sm shadow-[var(--shadow-panel)]">
              <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
              Refreshing overview
            </div>
          </div>
        ) : null}
        <div className="grid gap-4 md:grid-cols-3">
          <MetricCard
            detail="Current authenticated principal"
            label="Session"
            value={user?.display_name ?? "Unknown"}
          />
          <MetricCard
            detail="FastAPI dependency checks"
            label="Healthy dependencies"
            value={`${healthyCount}/${dependencyItems.length}`}
          />
          <MetricCard
            detail={version.data?.environment ?? "local"}
            label="Build"
            value={version.data?.build_sha ?? "local"}
          />
        </div>
        <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
          <Card>
            <CardHeader>
              <CardTitle>System dependencies</CardTitle>
              <CardDescription>Readiness checks exposed by the existing product API.</CardDescription>
            </CardHeader>
            <CardContent>
              <DataTable
                columns={[
                  { header: "Dependency", cell: (item) => item.name },
                  { header: "Status", cell: (item) => <StatusBadge status={item.status} /> },
                  { header: "Details", cell: (item) => item.message ?? item.details ?? "No details" }
                ]}
                getKey={(item) => item.name}
                items={dependencyItems}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Foundation</CardTitle>
              <CardDescription>Shared framework services now active for every route.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-brand-teal" />
                Session cookie auth with `/api/v1/auth/dev-login`
              </div>
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                TanStack Query server state
              </div>
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-brand-warm" />
                Vite static build and Docker-ready assets
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </>
  );
}
