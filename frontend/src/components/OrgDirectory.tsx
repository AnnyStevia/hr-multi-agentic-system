"use client";

import { useState } from "react";
import type { DirectoryEntry } from "@/types/organization";

export function OrgDirectory({
  items,
  onSearch,
  onSelect,
  searching = false,
}: {
  items: DirectoryEntry[];
  onSearch: (query: string) => void;
  onSelect?: (employeeId: number) => void;
  searching?: boolean;
}) {
  const [query, setQuery] = useState("");

  return (
    <div className="space-y-4">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSearch(query.trim());
        }}
        className="flex gap-2"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or position"
          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-brand-500 text-sm"
        />
        <button
          type="submit"
          disabled={searching}
          className="px-4 py-2.5 rounded-lg text-sm font-medium bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
        >
          Search
        </button>
      </form>

      {items.length === 0 ? (
        <p className="text-sm text-gray-500 py-6 text-center">No employees found.</p>
      ) : (
        <ul className="divide-y divide-gray-100 border border-gray-200 rounded-xl bg-white overflow-hidden">
          {items.map((item) => (
            <li key={item.employee_id}>
              <button
                type="button"
                onClick={() => onSelect?.(item.employee_id)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition"
              >
                <span className="h-9 w-9 rounded-full overflow-hidden border border-gray-200 bg-slate-100 shrink-0 flex items-center justify-center text-xs font-medium text-slate-600">
                  {item.profile_picture_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={item.profile_picture_url}
                      alt=""
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    initials(item.full_name)
                  )}
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-gray-900 truncate">
                    {item.full_name}
                  </span>
                  <span className="block text-xs text-gray-500 truncate">
                    {[item.position, item.department].filter(Boolean).join(" · ") || "—"}
                    {item.manager ? ` · Reports to ${item.manager}` : ""}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}
