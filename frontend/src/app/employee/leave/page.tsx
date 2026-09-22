"use client";

import { MyLeaveWorkspace } from "@/components/MyLeaveWorkspace";

export default function EmployeeLeavePage() {
  return (
    <MyLeaveWorkspace
      backHref="/employee/dashboard"
      backLabel="Dashboard"
      title="Leave"
      showTeamRequests
    />
  );
}
