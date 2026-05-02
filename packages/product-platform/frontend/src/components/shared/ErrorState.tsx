import { Button } from "../ui/button";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      className="rounded-lg border border-rose-200 bg-rose-50 p-5 text-sm text-rose-800"
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

