import { Button } from "../ui/button";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      className="feedback-danger"
      role="alert"
    >
      <div className="font-medium">Unable to load data</div>
      <p className="mt-1">{message}</p>
      {onRetry ? (
        <Button className="mt-3" onClick={onRetry} type="button" variant="outline">
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export interface QueryErrorSummaryItem {
  error: unknown;
  isError: boolean;
  label: string;
  onRetry?: () => void;
}

export function QueryErrorSummary({ items }: { items: QueryErrorSummaryItem[] }) {
  const failures = items.filter((item) => item.isError);

  if (failures.length === 0) {
    return null;
  }

  return (
    <div className="feedback-danger" role="alert">
      <div className="font-medium">
        {failures.length === 1 ? "A section failed to load" : "Some sections failed to load"}
      </div>
      <ul className="mt-2 space-y-1">
        {failures.map((item) => (
          <li className="flex flex-wrap items-center justify-between gap-3" key={item.label}>
            <span>
              <strong>{item.label}:</strong> {queryErrorMessage(item.error)}
            </span>
            {item.onRetry ? (
              <Button onClick={item.onRetry} type="button" variant="outline">
                Retry
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function queryErrorMessage(error: unknown, fallback = "Unable to load data.") {
  return error instanceof Error ? error.message : fallback;
}
