"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { OffboardingStatusBadge } from "@/components/OffboardingStatusBadge";
import { api } from "@/lib/api";
import {
  OFFBOARDING_REASON_LABELS,
  type OffboardingDetail,
  type OffboardingStatus,
} from "@/types/offboarding";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function OffboardingDetailPage() {
  const params = useParams<{ id: string }>();
  const caseId = Number(params.id);

  const [detail, setDetail] = useState<OffboardingDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      setDetail(await api.getOffboarding(caseId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load offboarding case");
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    if (!Number.isFinite(caseId)) {
      setError("Invalid offboarding id");
      setLoading(false);
      return;
    }
    load();
  }, [caseId, load]);

  const runAction = async (
    label: string,
    action: () => Promise<OffboardingDetail>,
    confirmMessage: string,
  ) => {
    if (!window.confirm(confirmMessage)) return;
    setActing(label);
    setError("");
    try {
      setDetail(await action());
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${label}`);
    } finally {
      setActing(null);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="max-w-3xl mx-auto">
        <Link href="/hr/offboarding" className="text-sm text-brand-700 hover:underline">
          ← Back to offboarding
        </Link>
        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}
      </div>
    );
  }

  const status: OffboardingStatus = detail.status;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <Link href="/hr/offboarding" className="text-sm text-brand-700 hover:underline">
          ← Back to offboarding
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">{detail.employee.full_name}</h1>
          <OffboardingStatusBadge status={status} />
        </div>
        <p className="mt-1 text-sm text-gray-600">
          {detail.employee.position} · {detail.employee.employee_number}
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl border shadow-sm p-5 space-y-3 text-sm">
        <Row label="Employee email" value={detail.employee.email} />
        <Row label="Reason" value={OFFBOARDING_REASON_LABELS[detail.reason]} />
        <Row label="Reason details" value={detail.reason_details || "—"} />
        <Row label="Last working day" value={formatDate(detail.last_working_day)} />
        <Row label="Initiated" value={formatDateTime(detail.initiated_at)} />
        <Row label="Completed" value={formatDateTime(detail.completed_at)} />
        <Row
          label="Created by"
          value={
            detail.created_by
              ? `${detail.created_by.full_name} (${detail.created_by.email})`
              : "—"
          }
        />
        <Row label="Updated" value={formatDateTime(detail.updated_at)} />
      </div>

      <div className="flex flex-wrap gap-2">
        {status === "initiated" && (
          <ActionButton
            label="Start"
            disabled={acting !== null}
            busy={acting === "start"}
            onClick={() =>
              runAction(
                "start",
                () => api.startOffboarding(detail.id),
                "Start this offboarding case?",
              )
            }
          />
        )}
        {status === "in_progress" && (
          <ActionButton
            label="Move to pending clearance"
            disabled={acting !== null}
            busy={acting === "pending"}
            onClick={() =>
              runAction(
                "pending",
                () => api.moveOffboardingToPendingClearance(detail.id),
                "Move this case to pending clearance?",
              )
            }
          />
        )}
        {status === "pending_clearance" && (
          <>
            <ActionButton
              label="Back to in progress"
              disabled={acting !== null}
              busy={acting === "start"}
              onClick={() =>
                runAction(
                  "start",
                  () => api.startOffboarding(detail.id),
                  "Move this case back to in progress?",
                )
              }
            />
            <ActionButton
              label="Complete"
              disabled={acting !== null}
              busy={acting === "complete"}
              onClick={() =>
                runAction(
                  "complete",
                  () => api.completeOffboarding(detail.id),
                  "Complete this offboarding case? (Phase O.1: no checklist gates yet.)",
                )
              }
            />
          </>
        )}
        {(status === "initiated" ||
          status === "in_progress" ||
          status === "pending_clearance") && (
          <ActionButton
            label="Cancel"
            variant="danger"
            disabled={acting !== null}
            busy={acting === "cancel"}
            onClick={() =>
              runAction(
                "cancel",
                () => api.cancelOffboarding(detail.id),
                "Cancel this offboarding case? Historical record will be kept.",
              )
            }
          />
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col sm:flex-row sm:gap-4">
      <dt className="sm:w-40 shrink-0 text-gray-500">{label}</dt>
      <dd className="text-gray-900">{value}</dd>
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  disabled,
  busy,
  variant = "primary",
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  variant?: "primary" | "danger";
}) {
  const classes =
    variant === "danger"
      ? "bg-red-600 hover:bg-red-700 text-white"
      : "bg-brand-600 hover:bg-brand-700 text-white";
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`px-4 py-2.5 rounded-lg text-sm font-medium disabled:opacity-60 ${classes}`}
    >
      {busy ? "Working…" : label}
    </button>
  );
}
