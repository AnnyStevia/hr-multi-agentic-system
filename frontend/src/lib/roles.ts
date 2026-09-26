import type { User } from "@/types/auth";

export function hasRole(user: User | null, roleName: string): boolean {
  return !!user?.roles.some((role) => role.name === roleName);
}

export function isAdmin(user: User | null): boolean {
  return hasRole(user, "admin");
}

export function isHR(user: User | null): boolean {
  return hasRole(user, "hr");
}

export function needsOnboarding(user: User | null): boolean {
  return user?.onboarding_status === "in_progress";
}

/** Employee portal: employee role, or hired user with an onboarding record (dual-role / lag-safe). */
export function canAccessEmployeePortal(user: User | null): boolean {
  if (!user) return false;
  if (hasRole(user, "employee")) return true;
  return user.onboarding_status === "in_progress" || user.onboarding_status === "completed";
}

/**
 * Interview assignment workspace (propose slots / complete feedback).
 * HR and managers are often panel members without the employee role.
 */
export function canAccessInterviewAssignments(user: User | null): boolean {
  if (!user) return false;
  if (canAccessEmployeePortal(user)) return true;
  return hasRole(user, "hr") || hasRole(user, "manager") || hasRole(user, "admin");
}

/** Staff who may only use /employee/interviews (not the full employee portal). */
export function isInterviewAssignmentsOnly(user: User | null): boolean {
  return Boolean(user && !canAccessEmployeePortal(user) && canAccessInterviewAssignments(user));
}

const ROLE_HOME_PATHS: Array<{ role: string; path: string }> = [
  { role: "admin", path: "/admin/dashboard" },
  { role: "hr", path: "/hr/dashboard" },
  { role: "manager", path: "/manager/dashboard" },
  { role: "employee", path: "/employee/dashboard" },
  { role: "candidate", path: "/careers/jobs" },
];

export function getHomePath(user: User | null): string {
  if (!user) {
    return "/login";
  }
  if (needsOnboarding(user)) {
    return "/employee/onboarding";
  }
  for (const mapping of ROLE_HOME_PATHS) {
    if (hasRole(user, mapping.role)) {
      return mapping.path;
    }
  }
  return "/dashboard";
}

export function isCandidate(user: User | null): boolean {
  return hasRole(user, "candidate");
}

export function canAccessHrPortal(user: User | null): boolean {
  return isAdmin(user) || isHR(user);
}

export function isSafeCareersNext(next: string | null | undefined): boolean {
  if (!next) {
    return false;
  }
  if (!next.startsWith("/careers")) {
    return false;
  }
  if (next.startsWith("//") || next.includes("://") || next.includes("..") || next.includes("\\")) {
    return false;
  }
  return true;
}

export function resolvePostAuthPath(user: User | null, next?: string | null): string {
  if (needsOnboarding(user)) {
    return "/employee/onboarding";
  }
  const home = getHomePath(user);
  if (isCandidate(user) && !hasRole(user, "employee") && isSafeCareersNext(next)) {
    return next as string;
  }
  return home;
}
