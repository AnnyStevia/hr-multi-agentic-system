export function EmployeeStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: "bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-600/15",
    inactive: "bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-500/10",
    on_leave: "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-600/15",
  };
  const labels: Record<string, string> = {
    active: "Active",
    inactive: "Inactive",
    on_leave: "On leave",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${
        styles[status] || "bg-slate-100 text-slate-700"
      }`}
    >
      {labels[status] || status}
    </span>
  );
}
