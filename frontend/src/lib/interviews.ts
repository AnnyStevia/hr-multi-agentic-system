export function formatSlotRange(startsAt: string, endsAt: string): string {
  const start = new Date(startsAt);
  const end = new Date(endsAt);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return `${startsAt} → ${endsAt}`;
  }

  const datePart = start.toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
  const startTime = start.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  const endTime = end.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return `${datePart} — ${startTime} → ${endTime}`;
}

export function formatSlotDate(startsAt: string): string {
  const start = new Date(startsAt);
  if (Number.isNaN(start.getTime())) return startsAt;
  return start.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export function formatSlotTimeRange(startsAt: string, endsAt: string): string {
  const start = new Date(startsAt);
  const end = new Date(endsAt);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return `${startsAt} → ${endsAt}`;
  }
  const startTime = start.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  const endTime = end.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return `${startTime} → ${endTime}`;
}

export function toIsoFromDateAndTime(date: string, time: string): string {
  return new Date(`${date}T${time}:00`).toISOString();
}

export function hasActiveInterviewInvitation(
  interviews: Array<{ status: string; outcome?: string | null }>,
): boolean {
  return interviews.some(
    (interview) =>
      interview.status === "proposed" ||
      interview.status === "scheduled" ||
      (interview.status === "completed" && !interview.outcome),
  );
}
