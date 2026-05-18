import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { queryString, resolveUrl } from "../api/client";

export interface EventStreamOptions {
  path: string;
  params?: Record<string, unknown>;
  eventName: string;
  queryKeysToInvalidate?: readonly (readonly unknown[])[];
  onMessage?: (event: MessageEvent) => void;
  enabled?: boolean;
}

export function eventStreamUrl(
  path: string,
  params: Record<string, unknown> = {},
  baseUrl = "/api/v1"
) {
  return resolveUrl(baseUrl, `${path}${queryString(params)}`);
}

export function useEventStream({
  path,
  params = {},
  eventName,
  queryKeysToInvalidate = [],
  onMessage,
  enabled = true
}: EventStreamOptions) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || typeof window.EventSource !== "function") {
      return undefined;
    }
    const source = new window.EventSource(eventStreamUrl(path, params));
    const listener = (event: MessageEvent) => {
      onMessage?.(event);
      for (const queryKey of queryKeysToInvalidate) {
        void queryClient.invalidateQueries({ queryKey });
      }
    };
    source.addEventListener(eventName, listener);
    return () => {
      source.removeEventListener(eventName, listener);
      source.close();
    };
  }, [enabled, eventName, onMessage, params, path, queryClient, queryKeysToInvalidate]);
}
