import { type RefObject, useEffect } from "react";

const HEADER_POPOVER_OPEN_EVENT = "ophanix:header-popover-open";

export function announceHeaderPopoverOpen(id: string) {
  window.dispatchEvent(new CustomEvent(HEADER_POPOVER_OPEN_EVENT, { detail: { id } }));
}

export function useHeaderPopoverDismiss({
  id,
  onOpenChange,
  open,
  rootRef,
  triggerRef
}: {
  id: string;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  rootRef: RefObject<HTMLElement | null>;
  triggerRef?: RefObject<HTMLElement | null>;
}) {
  useEffect(() => {
    if (!open) {
      return undefined;
    }

    function closePopover({ restoreFocus }: { restoreFocus: boolean }) {
      onOpenChange(false);
      if (restoreFocus) {
        triggerRef?.current?.focus();
      }
    }

    function handlePointerDown(event: PointerEvent) {
      const target = event.target;
      if (target instanceof Node && rootRef.current?.contains(target)) {
        return;
      }
      closePopover({ restoreFocus: false });
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closePopover({ restoreFocus: true });
      }
    }

    function handlePeerOpen(event: Event) {
      const peerId = event instanceof CustomEvent ? event.detail?.id : null;
      if (peerId !== id) {
        closePopover({ restoreFocus: false });
      }
    }

    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener(HEADER_POPOVER_OPEN_EVENT, handlePeerOpen);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener(HEADER_POPOVER_OPEN_EVENT, handlePeerOpen);
    };
  }, [id, onOpenChange, open, rootRef, triggerRef]);
}
