"use client";

import { CandidatePortalShell } from "@/components/CandidatePortalShell";

export default function CandidateInterviewLayout({ children }: { children: React.ReactNode }) {
  return <CandidatePortalShell>{children}</CandidatePortalShell>;
}
