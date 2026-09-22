import { addCalendarDays, formatDisplayDate } from "@/components/calendar/dateUtils";
import type { CurrentLeaveSummary } from "@/types/leave";

export function OnLeaveBanner({ currentLeave }: { currentLeave: CurrentLeaveSummary }) {
  const returnsOn = addCalendarDays(currentLeave.end_date, 1);
  return (
    <div className="rounded-xl border border-brand-200 bg-brand-100/60 px-4 py-3">
      <p className="text-sm font-semibold text-brand-900">Currently on leave</p>
      <p className="mt-1 text-sm text-brand-600 font-medium">{currentLeave.leave_type}</p>
      <p className="mt-1 text-sm text-brand-300">
        {formatDisplayDate(currentLeave.start_date)} → {formatDisplayDate(currentLeave.end_date)}
      </p>
      <p className="mt-1 text-sm text-brand-900">
        Returns {formatDisplayDate(returnsOn)}
      </p>
    </div>
  );
}
