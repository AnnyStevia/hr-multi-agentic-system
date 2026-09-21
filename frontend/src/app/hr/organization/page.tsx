"use client";

import { useCallback, useEffect, useState } from "react";
import { EmployeeOrganizationCard } from "@/components/EmployeeOrganizationCard";
import { OrgDirectory } from "@/components/OrgDirectory";
import { OrgHierarchyTree } from "@/components/OrgHierarchyTree";
import { api } from "@/lib/api";
import type {
  DirectoryEntry,
  EmployeeOrganization,
  HierarchyNode,
} from "@/types/organization";

export default function HrOrganizationPage() {
  const [tab, setTab] = useState<"hierarchy" | "directory">("hierarchy");
  const [nodes, setNodes] = useState<HierarchyNode[]>([]);
  const [directory, setDirectory] = useState<DirectoryEntry[]>([]);
  const [selected, setSelected] = useState<EmployeeOrganization | null>(null);
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
    loadHierarchy();
    loadDirectory();
  }, [loadHierarchy, loadDirectory]);

  const openEmployee = async (employeeId: number) => {
    setError("");
    try {
      setSelected(await api.getEmployeeOrganization(employeeId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load employee");
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Organization</h1>
        <p className="mt-1 text-sm text-gray-600">
          Company hierarchy and directory based on reporting relationships.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="flex gap-2 border-b border-gray-200">
        <TabButton active={tab === "hierarchy"} onClick={() => setTab("hierarchy")} label="Hierarchy" />
        <TabButton active={tab === "directory"} onClick={() => setTab("directory")} label="Directory" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm p-4 min-h-[320px]">
          {loading && tab === "hierarchy" ? (
            <div className="py-16 flex justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
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
        <div>
          {selected ? (
            <EmployeeOrganizationCard organization={selected} title="Selected employee" />
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 p-5 text-sm text-gray-500">
              Select an employee to view organizational details.
            </div>
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
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition ${
        active
          ? "border-brand-600 text-brand-700"
          : "border-transparent text-gray-500 hover:text-gray-800"
      }`}
    >
      {label}
    </button>
  );
}
