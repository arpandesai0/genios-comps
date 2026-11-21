import * as React from "react";
import { cn } from "@/lib/utils";
export function Badge({
  className,
  variant = "secondary",
  ...props
}: React.ComponentProps<"span"> & {
  variant?: "default" | "secondary" | "outline" | "destructive";
}) {
  return (
    <span className={cn("badge", `badge-${variant}`, className)} {...props} />
  );
}
