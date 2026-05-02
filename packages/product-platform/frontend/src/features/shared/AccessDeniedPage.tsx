import { PageHeader } from "../../components/layout/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";

export function AccessDeniedPage({ path }: { path: string }) {
  return (
    <>
      <PageHeader
        title="Access Denied"
        description={`Your current role does not include the permission required for ${path}.`}
      />
      <section className="p-6">
        <Card>
          <CardHeader>
            <CardTitle>Permission required</CardTitle>
            <CardDescription>
              Frontend permissions only shape navigation. Backend authorization remains authoritative.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Contact a platform administrator if this workspace should be available to your role.
          </CardContent>
        </Card>
      </section>
    </>
  );
}

