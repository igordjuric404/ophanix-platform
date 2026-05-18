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
