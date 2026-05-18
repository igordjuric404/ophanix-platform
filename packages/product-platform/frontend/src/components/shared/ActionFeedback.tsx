export interface ActionFeedbackMessage {
  type: "success" | "error";
  message: string;
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
