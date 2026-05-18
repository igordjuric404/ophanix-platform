import type { ReactNode } from "react";
import { useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "../ui/dialog";
import { Button, type ButtonVariant } from "../ui/button";

export function ConfirmDialog({
  trigger,
  title,
  description,
  onConfirm,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  confirmVariant = "destructive",
  isPending = false
}: {
  trigger: ReactNode;
  title: string;
  description: string;
  onConfirm: () => void | Promise<void>;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: ButtonVariant;
  isPending?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const pending = isPending || isConfirming;

  async function handleConfirm() {
    setIsConfirming(true);
    try {
      await onConfirm();
      setOpen(false);
    } finally {
      setIsConfirming(false);
    }
  }

  return (
    <Dialog
      onOpenChange={(nextOpen) => {
        if (!pending) {
          setOpen(nextOpen);
        }
      }}
      open={open}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="mt-5 flex justify-end gap-2">
          <Button disabled={pending} onClick={() => setOpen(false)} variant="outline">
            {cancelLabel}
          </Button>
          <Button disabled={pending} onClick={() => void handleConfirm()} variant={confirmVariant}>
            {pending ? "Working" : confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
