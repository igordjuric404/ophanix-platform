import { Navigate } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { useCurrentUser } from "../../api/auth";
import { ApiClientError } from "../../api/client";
import type { UserPrincipal } from "../../api/types";
import { ErrorState } from "../shared/ErrorState";
import { LoadingState } from "../shared/LoadingState";

export function RequireAuth({
  children,
  unauthenticatedFallback
}: {
  children: (user: UserPrincipal) => ReactNode;
  unauthenticatedFallback?: ReactNode;
}) {
  const currentUser = useCurrentUser();

  if (currentUser.isLoading) {
    return <LoadingState label="Checking session" />;
  }

  if (currentUser.isError) {
    const error = currentUser.error;
    if (error instanceof ApiClientError && error.status === 401) {
      return unauthenticatedFallback ?? <Navigate to="/login" />;
    }
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Authentication check failed."}
        onRetry={() => void currentUser.refetch()}
      />
    );
  }

  if (!currentUser.data) {
    return <ErrorState message="Authenticated session did not include a user." />;
  }

  return <>{children(currentUser.data)}</>;
}
