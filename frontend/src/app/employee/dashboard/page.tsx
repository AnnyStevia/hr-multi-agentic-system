"use client";

import { useEffect, useState } from "react";
import { OnLeaveBanner } from "@/components/OnLeaveBanner";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import type { EmployeeProfile } from "@/types/profile";

export default function EmployeeDashboardPage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);

  useEffect(() => {
    void api
      .getMyProfile()
      .then(setProfile)
      .catch(() => setProfile(null));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-brand-900">Welcome, {user?.first_name}</h1>
        <p className="mt-2 text-brand-300">Your employee workspace.</p>
      </div>
      {profile?.current_work_status === "ON_LEAVE" && profile.current_leave && (
        <OnLeaveBanner currentLeave={profile.current_leave} />
      )}
    </div>
  );
}
