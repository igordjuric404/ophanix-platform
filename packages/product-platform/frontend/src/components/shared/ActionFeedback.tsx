import { useCallback, useState } from "react";

export interface ActionFeedbackMessage {
  type: "success" | "error";
  message: string;
}

export interface RunActionFeedbackOptions<TValue> {
  errorMessage?: string;
  successMessage?: string | ((value: TValue) => string | null | undefined) | null;
}

export function ActionFeedback({ feedback }: { feedback: ActionFeedbackMessage | null }) {
  if (!feedback) {
    return null;
  }

  const isError = feedback.type === "error";

  return (
    <div
      aria-live={isError ? "assertive" : "polite"}
      className={isError ? "feedback-danger" : "feedback-success"}
      role={isError ? "alert" : "status"}
    >
      {feedback.message}
    </div>
  );
}

export function actionErrorMessage(error: unknown, fallback = "Action failed") {
  return error instanceof Error ? error.message : fallback;
}

export function useActionFeedback() {
  const [feedback, setFeedback] = useState<ActionFeedbackMessage | null>(null);

  const clearFeedback = useCallback(() => setFeedback(null), []);

  const setSuccess = useCallback((message: string) => {
    setFeedback({ type: "success", message });
  }, []);

  const setError = useCallback((message: string) => {
    setFeedback({ type: "error", message });
  }, []);

  const runWithFeedback = useCallback(
    async <TValue,>(
      task: () => Promise<TValue>,
      options: RunActionFeedbackOptions<TValue> = {}
    ): Promise<TValue | null> => {
      try {
        const result = await task();
        const successMessage =
          typeof options.successMessage === "function"
            ? options.successMessage(result)
            : options.successMessage;
        if (successMessage) {
          setSuccess(successMessage);
        }
        return result;
      } catch (error) {
        setError(actionErrorMessage(error, options.errorMessage));
        return null;
      }
    },
    [setError, setSuccess]
  );

  return {
    clearFeedback,
    feedback,
    runWithFeedback,
    setError,
    setFeedback,
    setSuccess
  };
}
