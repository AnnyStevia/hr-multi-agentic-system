export const PROFILE_PICTURE_CHANGED_EVENT = "my-profile-picture-changed";

export function notifyProfilePictureChanged(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(PROFILE_PICTURE_CHANGED_EVENT));
}
