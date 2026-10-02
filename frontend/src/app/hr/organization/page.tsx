"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Network, Search } from "lucide-react";
import { OrgDirectory } from "@/components/OrgDirectory";
import { OrgHierarchyTree } from "@/components/OrgHierarchyTree";
import { api } from "@/lib/api";
import type { DirectoryEntry, HierarchyNode } from "@/types/organization";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

export default function HrOrganizationPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"hierarchy" | "directory">("hierarchy");
  const [nodes, setNodes] = useState<HierarchyNode[]>([]);
  const [directory, setDirectory] = useState<DirectoryEntry[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  const loadHierarchy = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getOrganizationHierarchy();
      setNodes(data.employees);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load hierarchy");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDirectory = useCallback(async (q?: string) => {
    setSearching(true);
    setError("");
    try {
      const data = await api.getOrganizationDirectory(q);
      setDirectory(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load directory");
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    void loadHierarchy();
    void loadDirectory();
  }, [loadHierarchy, loadDirectory]);

  const openEmployee = (employeeId: number) => {
    router.push(`/hr/employees/${employeeId}`);
  };

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1400px] space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">
              Organization
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-brand-900">
              Organization
            </h1>
            <p className="mt-1 text-[13px] text-brand-300">
              Explore reporting lines and browse the company directory.
            </p>
          </div>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <div className={cn(card, "inline-flex gap-1 p-1")}>
          <TabButton
            active={tab === "hierarchy"}
            onClick={() => setTab("hierarchy")}
            label="Hierarchy"
            icon={<Network className="size-3.5" />}
          />
          <TabButton
            active={tab === "directory"}
            onClick={() => setTab("directory")}
            label="Directory"
            icon={<Search className="size-3.5" />}
          />
        </div>

        <div className={cn(card, "min-h-[520px] p-4 sm:p-5")}>
          {loading && tab === "hierarchy" ? (
            <div className="flex justify-center py-16">
              <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
            </div>
          ) : tab === "hierarchy" ? (
            <OrgHierarchyTree nodes={nodes} onSelect={openEmployee} />
          ) : (
            <OrgDirectory
              items={directory}
              searching={searching}
              onSearch={loadDirectory}
              onSelect={openEmployee}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  label,
  icon,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  icon: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-semibold transition",
        active
          ? "bg-[#0f224a] text-white shadow-sm"
          : "text-brand-600 hover:bg-[#f3f6f5]"
      )}
    >
      {icon}
      {label}
    </button>
  );
}
