"use client";

import { useState, type ReactNode } from "react";

export function ApplicationSection({
  title,
  children,
  collapsible = false,
  defaultOpen = true,
}: {
  title: string;
  children: ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  if (!collapsible) {
    return (
      <section className="bg-white rounded-xl border shadow-sm p-6 space-y-3">
        <h2 className="text-sm font-medium text-gray-500">{title}</h2>
        {children}
      </section>
    );
  }

  return (
    <section className="bg-white rounded-xl border shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="w-full px-6 py-4 flex items-center justify-between gap-3 text-left hover:bg-gray-50 transition"
        aria-expanded={open}
      >
        <h2 className="text-sm font-medium text-gray-500">{title}</h2>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`h-4 w-4 text-gray-500 transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 10.94l3.71-3.71a.75.75 0 1 1 1.06 1.06l-4.24 4.24a.75.75 0 0 1-1.06 0L5.21 8.29a.75.75 0 0 1 .02-1.08z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      {open && <div className="px-6 pb-6 space-y-3 border-t border-gray-100 pt-4">{children}</div>}
    </section>
  );
}
