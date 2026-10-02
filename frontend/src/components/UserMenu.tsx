"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { PROFILE_PICTURE_CHANGED_EVENT } from "@/lib/profileEvents";

type UserMenuProps = {
  editProfileHref?: string;
};

function initialsFromName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function UserMenu({ editProfileHref }: UserMenuProps) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [pictureUrl, setPictureUrl] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const loadAvatar = useCallback(async () => {
    if (!user || !editProfileHref) {
      setPictureUrl(null);
      return;
    }
    try {
      const profile = await api.getMyProfile();
      if (!profile.has_profile_picture) {
        setPictureUrl(null);
        return;
      }
      const result = await api.getMyProfilePictureUrl();
      setPictureUrl(result.url);
    } catch {
      setPictureUrl(null);
    }
  }, [user, editProfileHref]);

  useEffect(() => {
    void loadAvatar();
  }, [loadAvatar, pathname]);

  useEffect(() => {
    const onPictureChanged = () => {
      void loadAvatar();
    };
    window.addEventListener(PROFILE_PICTURE_CHANGED_EVENT, onPictureChanged);
    return () => {
      window.removeEventListener(PROFILE_PICTURE_CHANGED_EVENT, onPictureChanged);
    };
  }, [loadAvatar]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!user) return null;

  const initials = initialsFromName(user.full_name);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => {
          setOpen((value) => !value);
          void loadAvatar();
        }}
        className="h-9 w-9 rounded-full overflow-hidden border border-[#0f224a]/20 bg-[#0f224a]/5 text-xs font-semibold text-[#0f224a] hover:border-[#0f224a]/45 focus:outline-none focus:ring-2 focus:ring-[#0f224a]/25 transition"
        aria-label="Account menu"
        aria-expanded={open}
      >
        {pictureUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={pictureUrl} alt="" className="h-full w-full object-cover" />
        ) : (
          <span className="flex h-full w-full items-center justify-center">{initials}</span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-48 overflow-hidden rounded-xl border border-[#0f224a]/20 bg-white p-1.5 z-50 shadow-[0_18px_40px_-18px_rgba(15,34,74,0.55),0_0_0_1px_rgba(15,34,74,0.06)]">
          {editProfileHref && (
            <Link
              href={editProfileHref}
              onClick={() => setOpen(false)}
              className="block rounded-lg px-3 py-2 text-sm font-medium text-[#0f224a]/90 transition-colors hover:bg-[#0f224a] hover:text-white"
            >
              Edit profile
            </Link>
          )}
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              logout();
            }}
            className="w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-[#0f224a]/90 transition-colors hover:bg-[#0f224a] hover:text-white"
          >
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
