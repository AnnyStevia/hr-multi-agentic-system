import {
  LEAVE_APPROVAL_STATUS_LABELS,
  type LeaveApprovalStatus,
  type LeaveRequest,
} from "@/types/leave";

function stageClass(status: LeaveApprovalStatus): string {
  if (status === "approved") return "text-brand-600";
  if (status === "rejected") return "text-red-600";
  return "text-brand-300";
}

export function LeaveApprovalStages({ request }: { request: LeaveRequest }) {
  return (
    <p className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
      <span className={stageClass(request.manager_approval)}>
        Manager: {LEAVE_APPROVAL_STATUS_LABELS[request.manager_approval]}
      </span>
      <span className={stageClass(request.hr_approval)}>
        HR: {LEAVE_APPROVAL_STATUS_LABELS[request.hr_approval]}
      </span>
      {request.admin_override !== "pending" && (
        <span className={stageClass(request.admin_override)}>
          Admin: {LEAVE_APPROVAL_STATUS_LABELS[request.admin_override]}
        </span>
      )}
    </p>
  );
}
