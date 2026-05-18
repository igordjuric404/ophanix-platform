import { createContext, useContext, type ReactNode } from "react";

import type { UserPrincipal } from "../api/types";

const CurrentUserContext = createContext<UserPrincipal | null>(null);

export function CurrentUserProvider({
  children,
  user
}: {
  children: ReactNode;
  user: UserPrincipal;
}) {
  return <CurrentUserContext.Provider value={user}>{children}</CurrentUserContext.Provider>;
}

export function useCurrentUserPrincipal() {
  return useContext(CurrentUserContext);
}
