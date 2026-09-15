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
  const home = getHomePath(user);
  if (isCandidate(user) && isSafeCareersNext(next)) {
    return next as string;
  }
  return home;
}
