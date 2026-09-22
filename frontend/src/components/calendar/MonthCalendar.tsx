"use client";

import { toIsoDate } from "@/components/calendar/dateUtils";

export type DayVisualState = "available" | "approved" | "pending" | "unavailable" | "today";

export type MonthCalendarProps = {
  year: number;
  month: number; // 1-12
  onMonthChange: (year: number, month: number) => void;
  selectedStart?: string | null;
  selectedEnd?: string | null;
  onSelectDate?: (isoDate: string) => void;
  dayStates?: Record<string, DayVisualState>;
  disabledDates?: Set<string> | string[];
  className?: string;
};

export { addCalendarDays, formatDisplayDate } from "@/components/calendar/dateUtils";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

/** Monday-based weekday index 0..6 */
function mondayIndex(date: Date): number {
  return (date.getDay() + 6) % 7;
}

function isDisabled(iso: string, disabledDates?: Set<string> | string[]): boolean {
  if (!disabledDates) return false;
  if (disabledDates instanceof Set) return disabledDates.has(iso);
  return disabledDates.includes(iso);
}

function inSelectedRange(iso: string, start?: string | null, end?: string | null): boolean {
  if (!start) return false;
  if (!end) return iso === start;
  return iso >= start && iso <= end;
}

export function MonthCalendar({
  year,
  month,
  onMonthChange,
  selectedStart = null,
  selectedEnd = null,
  onSelectDate,
  dayStates = {},
  disabledDates,
  className = "",
}: MonthCalendarProps) {
  const todayIso = toIsoDate(new Date());
  const totalDays = daysInMonth(year, month);
  const first = new Date(year, month - 1, 1);
  const leading = mondayIndex(first);

  const cells: Array<{ iso: string | null; day: number | null }> = [];
  for (let i = 0; i < leading; i++) cells.push({ iso: null, day: null });
  for (let day = 1; day <= totalDays; day++) {
    const iso = toIsoDate(new Date(year, month - 1, day));
    cells.push({ iso, day });
  }
  while (cells.length % 7 !== 0) cells.push({ iso: null, day: null });

  const monthLabel = first.toLocaleString(undefined, { month: "long", year: "numeric" });

  const goPrev = () => {
    if (month === 1) onMonthChange(year - 1, 12);
    else onMonthChange(year, month - 1);
  };

  const goNext = () => {
    if (month === 12) onMonthChange(year + 1, 1);
    else onMonthChange(year, month + 1);
  };

  const goToday = () => {
    const now = new Date();
    onMonthChange(now.getFullYear(), now.getMonth() + 1);
  };

  return (
    <div className={`rounded-xl border border-brand-200 bg-white p-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h3 className="text-sm font-semibold text-brand-900">{monthLabel}</h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={goPrev}
            className="px-2.5 py-1.5 text-sm rounded-lg border border-brand-200 text-brand-900 hover:bg-brand-100"
            aria-label="Previous month"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={goToday}
            className="px-3 py-1.5 text-sm rounded-lg border border-brand-200 text-brand-600 font-medium hover:bg-brand-100"
          >
            Today
          </button>
          <button
            type="button"
            onClick={goNext}
            className="px-2.5 py-1.5 text-sm rounded-lg border border-brand-200 text-brand-900 hover:bg-brand-100"
            aria-label="Next month"
          >
            ›
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1 mb-1">
        {WEEKDAYS.map((label) => (
          <div key={label} className="text-center text-[11px] font-medium text-brand-300 py-1">
            {label}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {cells.map((cell, index) => {
          if (!cell.iso || cell.day == null) {
            return <div key={`empty-${index}`} className="aspect-square" />;
          }

          const iso = cell.iso;
          const disabled = isDisabled(iso, disabledDates);
          const state = dayStates[iso];
          const selected = inSelectedRange(iso, selectedStart, selectedEnd);
          const isToday = iso === todayIso;
          const isRangeStart = selectedStart === iso;
          const isRangeEnd = (selectedEnd || selectedStart) === iso;

          let stateClass = "text-brand-900 hover:bg-brand-100";
          if (state === "approved") stateClass = "bg-brand-600/15 text-brand-700";
          else if (state === "pending") stateClass = "bg-amber-100 text-amber-900";
          else if (state === "unavailable") stateClass = "bg-brand-100 text-brand-300";

          if (selected) {
            stateClass = "bg-brand-600 text-white hover:bg-brand-700";
          }

          return (
            <button
              key={iso}
              type="button"
              disabled={disabled || !onSelectDate}
              onClick={() => onSelectDate?.(iso)}
              className={`aspect-square rounded-lg text-sm font-medium transition relative
                ${stateClass}
                ${isToday && !selected ? "ring-1 ring-brand-600" : ""}
                ${disabled ? "opacity-40 cursor-not-allowed hover:bg-transparent" : ""}
                ${isRangeStart || isRangeEnd ? "font-semibold" : ""}
              `}
              aria-label={iso}
              aria-pressed={selected}
            >
              {cell.day}
            </button>
          );
        })}
      </div>
    </div>
  );
}
