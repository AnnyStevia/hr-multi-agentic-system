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

export default function EmployeeOrganizationPage() {
  const [tab, setTab] = useState<"mine" | "hierarchy" | "directory">("mine");
  const [mine, setMine] = useState<EmployeeOrganization | null>(null);
  const [nodes, setNodes] = useState<HierarchyNode[]>([]);
  const [directory, setDirectory] = useState<DirectoryEntry[]>([]);
  const [selected, setSelected] = useState<EmployeeOrganization | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  const loadMine = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setMine(await api.getMyOrganization());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load your organization");
    } finally {
      setLoading(false);
    }
  }, []);

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
    loadMine();
    loadHierarchy();
    loadDirectory();
  }, [loadMine, loadHierarchy, loadDirectory]);

  const openFromDirectory = async (employeeId: number) => {
    // Employees can only call me/organization and directory/hierarchy — detail of others
    // via directory row + hierarchy is limited. Use directory data for a lightweight card.
    const entry = directory.find((item) => item.employee_id === employeeId);
    if (!entry) return;
    setSelected({
      employee: {
        employee_id: entry.employee_id,
        full_name: entry.full_name,
        position: entry.position,
        department: entry.department,
        has_profile_picture: entry.has_profile_picture,
      },
      position: entry.position
        ? {
            id: 0,
            title: entry.position,
            description: null,
            department_id: null,
            department: entry.department,
            created_at: "",
            updated_at: "",
          }
        : null,
      department: entry.department
        ? {
            id: 0,
            name: entry.department,
            status: "active",
            created_at: "",
            updated_at: "",
          }
        : null,
      manager: entry.manager
        ? {
            employee_id: 0,
            full_name: entry.manager,
            position: null,
            department: null,
            has_profile_picture: false,
          }
        : null,
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Organization</h1>
        <p className="mt-1 text-sm text-gray-600">
          Your place in the company, the directory, and the reporting hierarchy.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="flex gap-2 border-b border-gray-200">
        <TabButton active={tab === "mine"} onClick={() => setTab("mine")} label="My place" />
        <TabButton active={tab === "hierarchy"} onClick={() => setTab("hierarchy")} label="Hierarchy" />
        <TabButton active={tab === "directory"} onClick={() => setTab("directory")} label="Directory" />
      </div>

      {tab === "mine" && (
        loading && !mine ? (
          <div className="py-16 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
          </div>
        ) : mine ? (
          <EmployeeOrganizationCard organization={mine} title="My organization" />
        ) : (
          <p className="text-sm text-gray-500">Organization details are not available.</p>
        )
      )}

      {tab === "hierarchy" && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
          {loading ? (
            <div className="py-16 flex justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
            </div>
          ) : (
            <OrgHierarchyTree nodes={nodes} />
          )}
        </div>
      )}

      {tab === "directory" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <OrgDirectory
              items={directory}
              searching={searching}
              onSearch={loadDirectory}
              onSelect={openFromDirectory}
            />
          </div>
          <div>
            {selected ? (
              <EmployeeOrganizationCard organization={selected} title="Colleague" />
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 p-5 text-sm text-gray-500">
                Select a colleague to view basic organizational information.
              </div>
            )}
          </div>
        </div>
      )}
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
