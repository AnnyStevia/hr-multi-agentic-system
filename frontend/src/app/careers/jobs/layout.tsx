"use client";

import { CandidatePortalShell } from "@/components/CandidatePortalShell";

export default function CandidateJobsLayout({ children }: { children: React.ReactNode }) {
  return <CandidatePortalShell>{children}</CandidatePortalShell>;
}
