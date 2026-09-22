"use client";

import { MyLeaveWorkspace } from "@/components/MyLeaveWorkspace";

export default function HrMyLeavePage() {
  return (
    <MyLeaveWorkspace
      backHref="/hr/leave"
      backLabel="Leave"
      title="My leave"
      showTeamRequests={false}
    />
  );
}
