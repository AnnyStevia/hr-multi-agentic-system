/** Client-side link preview helpers — no server fetch of target URLs. */

export type LinkPreviewKind = "youtube" | "vimeo" | "generic";

export type LinkPreviewMeta = {
  kind: LinkPreviewKind;
  href: string;
  hostname: string;
  label: string;
  /** Public image URL we can load in <img> without scraping the target page. */
  thumbnailUrl: string | null;
  faviconUrl: string;
};

function safeParseUrl(raw: string): URL | null {
  try {
    const url = new URL(raw.trim());
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    if (!url.hostname) return null;
    return url;
  } catch {
    return null;
  }
}

export function extractYoutubeVideoId(url: URL): string | null {
  const host = url.hostname.replace(/^www\./, "").toLowerCase();
  if (host === "youtu.be") {
    const id = url.pathname.split("/").filter(Boolean)[0];
    return id || null;
  }
  if (host === "youtube.com" || host === "m.youtube.com" || host === "music.youtube.com") {
    const v = url.searchParams.get("v");
    if (v) return v;
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] === "embed" || parts[0] === "shorts" || parts[0] === "live") {
      return parts[1] || null;
    }
  }
  return null;
}

export function extractVimeoId(url: URL): string | null {
  const host = url.hostname.replace(/^www\./, "").toLowerCase();
  if (host !== "vimeo.com" && host !== "player.vimeo.com") return null;
  const parts = url.pathname.split("/").filter(Boolean);
  if (host === "player.vimeo.com" && parts[0] === "video") {
    return parts[1] || null;
  }
  const id = parts.find((part) => /^\d+$/.test(part));
  return id || null;
}

export function getLinkPreviewMeta(rawUrl: string | null | undefined): LinkPreviewMeta | null {
  if (!rawUrl?.trim()) return null;
  const url = safeParseUrl(rawUrl);
  if (!url) return null;

  const hostname = url.hostname.replace(/^www\./, "");
  const faviconUrl = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(hostname)}&sz=64`;

  const youtubeId = extractYoutubeVideoId(url);
  if (youtubeId) {
    return {
      kind: "youtube",
      href: url.toString(),
      hostname,
      label: "YouTube video",
      thumbnailUrl: `https://i.ytimg.com/vi/${youtubeId}/hqdefault.jpg`,
      faviconUrl,
    };
  }

  const vimeoId = extractVimeoId(url);
  if (vimeoId) {
    return {
      kind: "vimeo",
      href: url.toString(),
      hostname,
      label: "Vimeo video",
      // Vimeo does not expose a stable public thumbnail without an API call.
      thumbnailUrl: null,
      faviconUrl,
    };
  }

  const pathLabel = `${url.pathname}${url.search}`.replace(/\/$/, "") || "/";
  return {
    kind: "generic",
    href: url.toString(),
    hostname,
    label: pathLabel.length > 48 ? `${pathLabel.slice(0, 45)}…` : pathLabel,
    thumbnailUrl: null,
    faviconUrl,
  };
}
