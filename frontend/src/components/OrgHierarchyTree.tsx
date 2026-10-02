"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode, Children } from "react";
import { ChevronDown, Maximize2, Minus, Network, Plus, RotateCcw, Users } from "lucide-react";
import type { HierarchyNode } from "@/types/organization";
import { cn } from "@/lib/utils";

const CARD_W = 188;
const GAP = 28;
const ZOOM_MIN = 0.4;
const ZOOM_MAX = 1.6;
const ZOOM_STEP = 0.1;
const ZOOM_DEFAULT = 1;

const AVATAR_TONES = [
  "bg-[#0f224a]",
  "bg-brand-600",
  "bg-teal-600",
  "bg-sky-600",
  "bg-emerald-700",
  "bg-violet-600",
];

function clampZoom(value: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(value * 100) / 100));
}

export function OrgHierarchyTree({
  nodes,
  onSelect,
  selectedId,
}: {
  nodes: HierarchyNode[];
  onSelect?: (employeeId: number) => void;
  selectedId?: number | null;
}) {
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});
  const [zoom, setZoom] = useState(ZOOM_DEFAULT);
  const viewportRef = useRef<HTMLDivElement>(null);
  const stats = useMemo(() => summarize(nodes), [nodes]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const onWheel = (event: WheelEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      event.preventDefault();
      const direction = event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      setZoom((value) => clampZoom(value + direction));
    };

    viewport.addEventListener("wheel", onWheel, { passive: false });
    return () => viewport.removeEventListener("wheel", onWheel);
  }, []);

  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#0f224a]/5 text-[#0f224a]">
          <Network className="size-5" />
        </div>
        <p className="text-sm font-medium text-brand-900">No hierarchy yet</p>
        <p className="max-w-sm text-[13px] text-brand-300">
          Assign managers on employee profiles to build the reporting tree.
        </p>
      </div>
    );
  }

  const toggle = (id: number) => {
    setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const zoomIn = () => setZoom((value) => clampZoom(value + ZOOM_STEP));
  const zoomOut = () => setZoom((value) => clampZoom(value - ZOOM_STEP));
  const resetZoom = () => setZoom(ZOOM_DEFAULT);

  const fitZoom = () => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const content = viewport.querySelector<HTMLElement>("[data-org-chart-content]");
    if (!content) return;

    const prev = content.style.transform;
    content.style.transform = "scale(1)";
    const contentWidth = Math.max(content.scrollWidth, 1);
    const contentHeight = Math.max(content.scrollHeight, 1);
    content.style.transform = prev;

    const availableWidth = Math.max(viewport.clientWidth - 48, 120);
    const availableHeight = Math.max(viewport.clientHeight - 48, 120);
    const next = Math.min(
      availableWidth / contentWidth,
      availableHeight / contentHeight,
      ZOOM_DEFAULT
    );
    setZoom(clampZoom(next));
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#0f224a]/5 px-2.5 py-1 text-[11px] font-semibold text-[#0f224a]">
            <Users className="size-3.5" />
            {stats.people} people
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-1 text-[11px] font-semibold text-brand-700">
            {stats.roots} root{stats.roots === 1 ? "" : "s"}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-50 px-2.5 py-1 text-[11px] font-semibold text-sky-800">
            Depth {stats.depth}
          </span>
        </div>

        <div className="inline-flex items-center gap-1 rounded-xl border border-brand-200/80 bg-white p-1 shadow-sm">
          <ZoomButton
            label="Zoom out"
            onClick={zoomOut}
            disabled={zoom <= ZOOM_MIN}
          >
            <Minus className="size-3.5" />
          </ZoomButton>
          <span className="min-w-[3.25rem] text-center text-[11px] font-semibold tabular-nums text-[#0f224a]">
            {Math.round(zoom * 100)}%
          </span>
          <ZoomButton
            label="Zoom in"
            onClick={zoomIn}
            disabled={zoom >= ZOOM_MAX}
          >
            <Plus className="size-3.5" />
          </ZoomButton>
          <span className="mx-0.5 h-4 w-px bg-brand-200" />
          <ZoomButton label="Fit to view" onClick={fitZoom}>
            <Maximize2 className="size-3.5" />
          </ZoomButton>
          <ZoomButton
            label="Reset zoom"
            onClick={resetZoom}
            disabled={zoom === ZOOM_DEFAULT}
          >
            <RotateCcw className="size-3.5" />
          </ZoomButton>
        </div>
      </div>

      <div
        ref={viewportRef}
        className="relative h-[min(70vh,720px)] overflow-auto rounded-2xl border border-brand-200/70 bg-[radial-gradient(ellipse_80%_60%_at_50%_0%,rgba(15,34,74,0.05),transparent_55%),linear-gradient(180deg,#f7faf9_0%,#ffffff_45%)] p-6 sm:p-8"
      >
        <p className="pointer-events-none absolute bottom-3 left-4 z-10 hidden text-[10px] font-medium text-brand-300 sm:block">
          Ctrl / ⌘ + scroll to zoom
        </p>
        <div
          data-org-chart-content
          className="inline-flex min-w-full origin-top flex-col items-center transition-transform duration-200 ease-out"
          style={{
            transform: `scale(${zoom})`,
            marginBottom: zoom < 1 ? `${(1 - zoom) * -20}%` : undefined,
          }}
        >
          {nodes.length > 1 ? (
            <>
              <div className="rounded-2xl border border-[#0f224a]/15 bg-[#0f224a] px-5 py-3 text-center shadow-lg shadow-[#0f224a]/20">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/60">
                  Company
                </p>
                <p className="mt-0.5 text-sm font-semibold text-white">
                  Organization chart
                </p>
              </div>
              <ConnectorDown withArrow={false} />
              <ChildrenRow count={nodes.length}>
                {nodes.map((node) => (
                  <TreeBranch
                    key={node.employee_id}
                    node={node}
                    depth={0}
                    collapsed={collapsed}
                    onToggle={toggle}
                    onSelect={onSelect}
                    selectedId={selectedId}
                  />
                ))}
              </ChildrenRow>
            </>
          ) : (
            <TreeBranch
              node={nodes[0]}
              depth={0}
              collapsed={collapsed}
              onToggle={toggle}
              onSelect={onSelect}
              selectedId={selectedId}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function ZoomButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-[#0f224a] transition hover:bg-[#0f224a]/6 disabled:cursor-not-allowed disabled:opacity-35"
    >
      {children}
    </button>
  );
}

function TreeBranch({
  node,
  depth,
  collapsed,
  onToggle,
  onSelect,
  selectedId,
}: {
  node: HierarchyNode;
  depth: number;
  collapsed: Record<number, boolean>;
  onToggle: (id: number) => void;
  onSelect?: (employeeId: number) => void;
  selectedId?: number | null;
}) {
  const hasChildren = node.children.length > 0;
  const isCollapsed = Boolean(collapsed[node.employee_id]);
  const expanded = hasChildren && !isCollapsed;
  const selected = selectedId === node.employee_id;
  const tone = AVATAR_TONES[(node.employee_id + depth) % AVATAR_TONES.length];

  return (
    <div
      className="relative flex flex-col items-center"
      style={{ width: CARD_W }}
    >
      <PersonCard
        node={node}
        tone={tone}
        selected={selected}
        hasChildren={hasChildren}
        expanded={expanded}
        onSelect={onSelect}
        onToggle={() => onToggle(node.employee_id)}
      />

      {expanded ? (
        <>
          <ConnectorDown withArrow={node.children.length === 1} />
          <ChildrenRow count={node.children.length}>
            {node.children.map((child) => (
              <TreeBranch
                key={child.employee_id}
                node={child}
                depth={depth + 1}
                collapsed={collapsed}
                onToggle={onToggle}
                onSelect={onSelect}
                selectedId={selectedId}
              />
            ))}
          </ChildrenRow>
        </>
      ) : null}
    </div>
  );
}

function ChildrenRow({
  count,
  children,
}: {
  count: number;
  children: ReactNode;
}) {
  const barWidth = Math.max(0, (count - 1) * (CARD_W + GAP));
  const items = Children.toArray(children);

  return (
    <div className="relative flex items-start justify-center" style={{ gap: GAP }}>
      {count > 1 ? (
        <div
          className="pointer-events-none absolute top-0 h-px bg-[#0f224a]/40"
          style={{
            left: `calc(50% - ${barWidth / 2}px)`,
            width: barWidth,
          }}
        />
      ) : null}
      {items.map((child) => (
        <div
          key={typeof child === "object" && child && "key" in child ? String(child.key) : undefined}
          className="relative flex flex-col items-center"
        >
          {count > 1 ? <DropArrow /> : null}
          {child}
        </div>
      ))}
    </div>
  );
}

function ConnectorDown({ withArrow = true }: { withArrow?: boolean }) {
  return (
    <div className="relative my-1 flex h-10 w-full items-start justify-center">
      <span
        className={cn(
          "absolute top-0 w-px bg-[#0f224a]/40",
          withArrow ? "h-10" : "h-10"
        )}
      />
      {withArrow ? (
        <ArrowHead className="absolute bottom-0 translate-y-1/2" />
      ) : null}
    </div>
  );
}

function DropArrow() {
  return (
    <div className="relative mb-1 flex h-8 w-full items-start justify-center">
      <span className="absolute top-0 h-8 w-px bg-[#0f224a]/40" />
      <ArrowHead className="absolute bottom-0 translate-y-1/2" />
    </div>
  );
}

function PersonCard({
  node,
  tone,
  selected,
  hasChildren,
  expanded,
  onSelect,
  onToggle,
}: {
  node: HierarchyNode;
  tone: string;
  selected: boolean;
  hasChildren: boolean;
  expanded: boolean;
  onSelect?: (employeeId: number) => void;
  onToggle: () => void;
}) {
  return (
    <div className="relative w-full">
      <button
        type="button"
        onClick={() => onSelect?.(node.employee_id)}
        className={cn(
          "group w-full rounded-2xl border bg-white p-3 text-left shadow-[0_10px_28px_-18px_rgba(15,34,74,0.45)] transition duration-200",
          "hover:-translate-y-0.5 hover:border-[#0f224a]/35 hover:shadow-[0_16px_32px_-16px_rgba(15,34,74,0.4)]",
          selected
            ? "border-[#0f224a] ring-2 ring-[#0f224a]/15"
            : "border-brand-200/80"
        )}
      >
        <div className="flex items-start gap-2.5">
          <span
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white shadow-sm ring-2 ring-white",
              tone
            )}
          >
            {initials(node.name)}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-semibold text-brand-900">
              {node.name}
            </span>
            <span className="mt-0.5 block truncate text-[11px] font-medium text-brand-600">
              {node.position || "No position"}
            </span>
            <span className="mt-0.5 block truncate text-[10px] text-brand-300">
              {node.department || "No department"}
            </span>
          </span>
        </div>

        {node.children.length > 0 ? (
          <span className="mt-2.5 inline-flex items-center gap-1 rounded-full bg-[#f3f6f5] px-2 py-0.5 text-[10px] font-semibold text-brand-700">
            {node.children.length} direct report
            {node.children.length === 1 ? "" : "s"}
          </span>
        ) : null}
      </button>

      {hasChildren ? (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onToggle();
          }}
          className={cn(
            "absolute -bottom-3 left-1/2 z-10 flex h-6 w-6 -translate-x-1/2 items-center justify-center rounded-full border bg-white text-[#0f224a] shadow-md transition hover:bg-[#0f224a] hover:text-white",
            expanded ? "border-[#0f224a]/35" : "border-brand-200"
          )}
          aria-label={expanded ? "Collapse reports" : "Expand reports"}
        >
          <ChevronDown
            className={cn(
              "size-3.5 transition-transform duration-200",
              expanded && "rotate-180"
            )}
          />
        </button>
      ) : null}
    </div>
  );
}

function ArrowHead({ className }: { className?: string }) {
  return (
    <svg
      width="12"
      height="9"
      viewBox="0 0 12 9"
      className={cn("text-[#0f224a]/75", className)}
      aria-hidden
    >
      <path d="M6 9 0 0h12L6 9Z" fill="currentColor" />
    </svg>
  );
}

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function summarize(nodes: HierarchyNode[]) {
  let people = 0;
  let depth = 0;

  const walk = (list: HierarchyNode[], level: number) => {
    depth = Math.max(depth, level);
    for (const node of list) {
      people += 1;
      if (node.children.length) walk(node.children, level + 1);
    }
  };

  walk(nodes, 1);
  return { people, roots: nodes.length, depth };
}
