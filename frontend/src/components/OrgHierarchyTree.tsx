"use client";

import type { HierarchyNode } from "@/types/organization";

export function OrgHierarchyTree({
  nodes,
  onSelect,
}: {
  nodes: HierarchyNode[];
  onSelect?: (employeeId: number) => void;
}) {
  if (nodes.length === 0) {
    return <p className="text-sm text-gray-500 py-6 text-center">No hierarchy yet. Assign managers to build the tree.</p>;
  }

  return (
    <ul className="space-y-1">
      {nodes.map((node) => (
        <HierarchyItem key={node.employee_id} node={node} depth={0} onSelect={onSelect} />
      ))}
    </ul>
  );
}

function HierarchyItem({
  node,
  depth,
  onSelect,
}: {
  node: HierarchyNode;
  depth: number;
  onSelect?: (employeeId: number) => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect?.(node.employee_id)}
        className="w-full text-left px-3 py-2 rounded-md text-sm hover:bg-slate-50 transition"
        style={{ paddingLeft: `${12 + depth * 16}px` }}
      >
        <span className="font-medium text-gray-900">{node.name}</span>
        <span className="text-gray-500">
          {node.position ? ` · ${node.position}` : ""}
          {node.department ? ` · ${node.department}` : ""}
        </span>
      </button>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((child) => (
            <HierarchyItem
              key={child.employee_id}
              node={child}
              depth={depth + 1}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
