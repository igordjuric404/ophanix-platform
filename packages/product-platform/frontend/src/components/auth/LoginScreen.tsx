import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useDevLogin } from "../../api/auth";
import { ApiClientError } from "../../api/client";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";

const loginSchema = z.object({
  email: z.string().email(),
  role: z.string().min(1)
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginScreen() {
  const navigate = useNavigate();
  const login = useDevLogin();
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "admin@example.com",
      role: "Platform Admin"
    }
  });

  async function onSubmit(values: LoginFormValues) {
    await login.mutateAsync({
      email: values.email,
      roles: [values.role]
    });
    await navigate({ to: "/overview" });
  }

  const errorMessage =
    login.error instanceof ApiClientError
      ? login.error.message
      : login.error instanceof Error
        ? login.error.message
        : null;

  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
      <div className="fixed inset-x-0 top-0 h-0.5 bg-gradient-to-r from-brand-warm via-brand-cream to-brand-teal" />
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <CardTitle className="text-xl">Ophanix Product Platform</CardTitle>
          <CardDescription>Sign in to the local governance control plane.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" {...form.register("email")} />
              {form.formState.errors.email ? (
                <p className="text-sm text-destructive">{form.formState.errors.email.message}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-background/90 px-3 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-4 focus-visible:ring-ring/15"
                id="role"
                {...form.register("role")}
              >
                <option>Platform Admin</option>
                <option>Policy Admin</option>
                <option>Security Admin</option>
                <option>Compliance Admin</option>
                <option>Operator</option>
                <option>Viewer</option>
              </select>
            </div>
            {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}
            <Button className="w-full" disabled={login.isPending} type="submit">
              {login.isPending ? "Signing in" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
