"use client";

type MeetingJoinBlockProps = {
  status: string;
  meetingUrl?: string | null;
  /** When true, show a retry control for HR. */
  showRetry?: boolean;
  retrying?: boolean;
  onRetry?: () => void;
};

export function MeetingJoinBlock({
  status,
  meetingUrl,
  showRetry = false,
  retrying = false,
  onRetry,
}: MeetingJoinBlockProps) {
  const isScheduled = status === "scheduled";
  const isCompleted = status === "completed";

  if (!isScheduled && !isCompleted) {
    return null;
  }

  if (meetingUrl) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-gray-500">Video meeting</p>
        <a
          href={meetingUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center justify-center bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-semibold hover:bg-brand-700"
        >
          Join interview
        </a>
      </div>
    );
  }

  if (isCompleted) {
    return null;
  }

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 space-y-2">
      <p className="text-sm text-amber-900">Meeting link will appear shortly.</p>
      <p className="text-xs text-amber-800">
        The interview is scheduled. Refresh this page in a moment if the join button is not shown yet.
      </p>
      {showRetry && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="text-sm font-medium text-brand-700 hover:underline disabled:opacity-50"
        >
          {retrying ? "Retrying…" : "Retry meeting link"}
        </button>
      )}
    </div>
  );
}
