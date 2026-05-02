import { PageHeader } from "../../components/layout/PageHeader";
import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";

export function FeaturePlaceholderPage({
  title,
  description,
  status
}: {
  title: string;
  description: string;
  status: string;
}) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <section className="grid gap-4 p-6 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle>Migration status</CardTitle>
              <Badge tone="warning">{status}</Badge>
            </div>
            <CardDescription>
              The React workspace route is registered and protected. Feature-specific controls will
              be migrated from the existing implementation in the matching worktree phase.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border bg-muted/40 p-4 text-sm text-muted-foreground">
              Backend API contracts are preserved while this page waits for its feature refactor.
            </div>
          </CardContent>
        </Card>
      </section>
    </>
  );
}

