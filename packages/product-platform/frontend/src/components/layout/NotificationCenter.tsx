import { Bell } from "lucide-react";

import { Button } from "../ui/button";

export function NotificationCenter() {
  return (
    <details className="relative">
      <summary className="list-none">
        <Button aria-label="Notifications" className="h-9 w-9 p-0" type="button" variant="outline">
          <Bell className="h-4 w-4" />
        </Button>
      </summary>
      <div className="absolute right-0 z-30 mt-2 w-72 rounded-lg border bg-background p-4 text-sm shadow-lg">
        <div className="font-medium">Notifications</div>
        <p className="mt-1 text-muted-foreground">No notifications</p>
      </div>
    </details>
  );
}

