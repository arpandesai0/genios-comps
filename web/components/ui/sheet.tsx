"use client";
import * as React from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
export const Sheet = Dialog.Root;
export const SheetTrigger = Dialog.Trigger;
export const SheetClose = Dialog.Close;
export function SheetContent({
  className,
  children,
  ...props
}: React.ComponentProps<typeof Dialog.Content>) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="sheet-overlay" />
      <Dialog.Content className={cn("sheet-content", className)} {...props}>
        {children}
        <Dialog.Close
          className="sheet-close button button-ghost button-icon"
          aria-label="Close panel"
        >
          <X size={20} />
        </Dialog.Close>
      </Dialog.Content>
    </Dialog.Portal>
  );
}
export function SheetHeader(props: React.ComponentProps<"div">) {
  return <div className="sheet-header" {...props} />;
}
export function SheetTitle(props: React.ComponentProps<typeof Dialog.Title>) {
  return <Dialog.Title className="sheet-title" {...props} />;
}
export function SheetDescription(
  props: React.ComponentProps<typeof Dialog.Description>,
) {
  return <Dialog.Description className="muted" {...props} />;
}
