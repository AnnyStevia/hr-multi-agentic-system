export function EmployeeStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: "bg-green-100 text-green-800",
    inactive: "bg-gray-100 text-gray-700",
    on_leave: "bg-amber-100 text-amber-800",
  };
  const labels: Record<string, string> = {
    active: "Active",
    inactive: "Inactive",
    on_leave: "On leave",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status] || "bg-gray-100 text-gray-700"}`}>
      {labels[status] || status}
    </span>
  );
}
