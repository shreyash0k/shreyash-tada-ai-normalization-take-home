"use client";

import { Dialog } from "@base-ui/react/dialog";
import type { CSSProperties, ReactNode } from "react";
import type { IssueGroup } from "@/lib/issues";
import { IssueList } from "./issue-list";

export function IssueDialog({
  title,
  subtitle,
  groups,
  emptyText,
  triggerClassName,
  triggerStyle,
  children,
}: {
  title: string;
  subtitle: string;
  groups: IssueGroup[];
  emptyText?: string;
  triggerClassName: string;
  triggerStyle?: CSSProperties;
  children: ReactNode;
}) {
  const empty = groups.every((group) => group.issues.length === 0);
  return (
    <Dialog.Root>
      <Dialog.Trigger className={triggerClassName} style={triggerStyle}>
        {children}
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-40 bg-neutral-900/35" />
        <Dialog.Popup className="fixed left-1/2 top-20 z-50 max-h-[calc(100vh-10rem)] w-[calc(100%-3rem)] max-w-3xl -translate-x-1/2 overflow-y-auto rounded-2xl bg-white p-7 text-sm shadow-2xl outline-none">
          <Dialog.Close
            aria-label="Close"
            className="absolute right-5 top-4 cursor-pointer text-xl text-neutral-400 hover:text-neutral-700"
          >
            ×
          </Dialog.Close>
          <Dialog.Title className="pr-8 text-xl font-semibold tracking-tight">{title}</Dialog.Title>
          <Dialog.Description className="mt-0.5 mb-5 font-mono text-xs text-neutral-400">{subtitle}</Dialog.Description>
          {empty ? (
            <p className="py-6 text-center text-neutral-500">{emptyText ?? "Nothing was flagged."}</p>
          ) : (
            groups
              .filter((group) => group.issues.length > 0)
              .map((group, index) => (
                <section key={group.heading ?? index} className="mt-4 first:mt-0">
                  {group.heading && (
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">{group.heading}</h3>
                  )}
                  <IssueList issues={group.issues} />
                </section>
              ))
          )}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
