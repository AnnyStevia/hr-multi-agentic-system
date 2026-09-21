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
        className="h-9 w-9 rounded-full overflow-hidden border border-gray-200 bg-slate-100 text-xs font-medium text-slate-600 hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition"
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
        <div className="absolute right-0 mt-2 w-44 rounded-lg border border-gray-200 bg-white py-1 shadow-sm z-50">
          {editProfileHref && (
            <Link
              href={editProfileHref}
              onClick={() => setOpen(false)}
              className="block px-3 py-2 text-sm text-gray-700 hover:bg-slate-50"
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
            className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-slate-50"
          >
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
