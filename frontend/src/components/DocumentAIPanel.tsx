"use client";

import { FormEvent, useEffect, useId, useRef, useState } from "react";
import { X } from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import type {
  DocumentAnswer,
  DocumentCitation,
  DocumentSourceType,
  DocumentSummary,
} from "@/types/ai";

export function isPdfDocument(contentType: string, filename?: string): boolean {
  const mime = (contentType || "").toLowerCase();
  if (mime === "application/pdf" || mime.includes("pdf")) return true;
  const name = (filename || "").toLowerCase();
  return name.endsWith(".pdf");
}

function buildDocumentIdentityClause(opts: {
  documentId: number;
  documentType: DocumentSourceType;
  employeeId?: number;
}): string {
  const parts = [
    `document_id=${opts.documentId}`,
    `document_type=${opts.documentType}`,
  ];
  if (opts.documentType === "employee" && opts.employeeId != null) {
    parts.push(`employee_id=${opts.employeeId}`);
  }
  return parts.join(" ");
}

export function buildSummarizeMessage(opts: {
  documentId: number;
  documentType: DocumentSourceType;
  employeeId?: number;
}): string {
  return (
    `Summarize ${buildDocumentIdentityClause(opts)} using the summarize_document tool. ` +
    "Do not invent content."
  );
}

export function buildAskMessage(opts: {
  documentId: number;
  documentType: DocumentSourceType;
  employeeId?: number;
  question: string;
}): string {
  const { question, ...identity } = opts;
  return (
    `Answer this question about ${buildDocumentIdentityClause(identity)} ` +
    `using the ask_about_document tool: ${question}`
  );
}

function formatCitationLabel(citations: DocumentCitation[]): string {
  const pages = [
    ...new Set(
      citations
        .map((c) => c.page_number)
        .filter((n) => Number.isFinite(n) && n > 0),
    ),
  ].sort((a, b) => a - b);
  if (pages.length === 0) return "";
  if (pages.length === 1) return `Source: p. ${pages[0]}`;
  return `Sources: pp. ${pages.join(", ")}`;
}

function friendlyDocumentAiError(err: unknown): string {
  if (err instanceof ApiClientError) {
    if (err.status === 0) {
      return "Cannot reach the server. Check your connection and try again.";
    }
    if (err.status === 403) {
      return err.message || "You are not allowed to analyze this document.";
    }
    if (err.status === 404) {
      return err.message || "Document not found.";
    }
    if (err.status === 409) {
      return err.message || "This document cannot be analyzed in its current state.";
    }
    if (err.status === 422) {
      return err.message || "This document cannot be analyzed (unsupported or invalid).";
    }
    if (err.status === 502 || err.status >= 500) {
      return "Document AI is temporarily unavailable. Please try again shortly.";
    }
    return err.message || "Something went wrong while analyzing the document.";
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return "Something went wrong while analyzing the document.";
}

type QaTurn = {
  id: string;
  question: string;
  answer: DocumentAnswer | null;
  fallbackAnswer: string | null;
  error: string | null;
};

export type DocumentAIPanelProps = {
  documentId: number;
  documentType: DocumentSourceType;
  title: string;
  filename?: string;
  /** Required when HR analyzes another employee's document. */
  employeeId?: number;
  /** Auto-start summarize or focus the Ask input when the panel opens. */
  initialAction?: "summarize" | "ask";
  onClose?: () => void;
};

export function DocumentAIPanel({
  documentId,
  documentType,
  title,
  filename,
  employeeId,
  initialAction,
  onClose,
}: DocumentAIPanelProps) {
  const questionInputId = useId();
  const panelRef = useRef<HTMLElement>(null);
  const questionRef = useRef<HTMLTextAreaElement>(null);
  const autoStartedRef = useRef<string | null>(null);
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [summaryFallback, setSummaryFallback] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [question, setQuestion] = useState("");
  const [qaLoading, setQaLoading] = useState(false);
  const [qaError, setQaError] = useState("");
  const [qaTurns, setQaTurns] = useState<QaTurn[]>([]);
  const [activeTab, setActiveTab] = useState<"summary" | "qa">(
    initialAction === "ask" ? "qa" : "summary",
  );

  const identity = { documentId, documentType, employeeId };
  const sessionKey = `${documentType}:${documentId}:${employeeId ?? ""}:${initialAction ?? ""}`;

  useEffect(() => {
    setSummary(null);
    setSummaryFallback(null);
    setSummaryError("");
    setQuestion("");
    setQaError("");
    setQaTurns([]);
    autoStartedRef.current = null;
  }, [documentId, documentType, employeeId]);

  useEffect(() => {
    setActiveTab(initialAction === "ask" ? "qa" : "summary");
  }, [sessionKey, initialAction]);

  useEffect(() => {
    panelRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [sessionKey]);

  const handleSummarize = async () => {
    if (summaryLoading || qaLoading) return;
    setActiveTab("summary");
    setSummaryLoading(true);
    setSummaryError("");
    try {
      const result = await api.askDocumentsAgent({
        message: buildSummarizeMessage(identity),
      });
      if (result.document_summary) {
        setSummary(result.document_summary);
        setSummaryFallback(null);
      } else if (result.answer?.trim()) {
        setSummary(null);
        setSummaryFallback(result.answer.trim());
      } else {
        setSummary(null);
        setSummaryFallback(null);
        setSummaryError("No summary was returned for this document.");
      }
    } catch (err) {
      setSummary(null);
      setSummaryFallback(null);
      setSummaryError(friendlyDocumentAiError(err));
    } finally {
      setSummaryLoading(false);
    }
  };

  useEffect(() => {
    if (autoStartedRef.current === sessionKey) return;
    autoStartedRef.current = sessionKey;
    if (initialAction === "summarize") {
      void handleSummarize();
    } else if (initialAction === "ask") {
      window.setTimeout(() => questionRef.current?.focus(), 50);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once per panel session
  }, [sessionKey, initialAction]);

  const handleAsk = async (event?: FormEvent) => {
    event?.preventDefault();
    if (summaryLoading || qaLoading) return;
    const trimmed = question.trim();
    if (!trimmed) {
      setQaError("Enter a question about this document.");
      return;
    }
    setActiveTab("qa");
    setQaLoading(true);
    setQaError("");
    const turnId = `qa-${Date.now()}`;
    try {
      const result = await api.askDocumentsAgent({
        message: buildAskMessage({ ...identity, question: trimmed }),
      });
      setQaTurns((prev) => [
        ...prev,
        {
          id: turnId,
          question: trimmed,
          answer: result.document_answer,
          fallbackAnswer: result.document_answer
            ? null
            : result.answer?.trim() || null,
          error: null,
        },
      ]);
      setQuestion("");
    } catch (err) {
      setQaTurns((prev) => [
        ...prev,
        {
          id: turnId,
          question: trimmed,
          answer: null,
          fallbackAnswer: null,
          error: friendlyDocumentAiError(err),
        },
      ]);
    } finally {
      setQaLoading(false);
    }
  };

  const displayTitle = title || filename || `Document #${documentId}`;
  const hasSummaryContent = Boolean(summary || summaryFallback);

  const renderSummaryBody = () => {
    if (summaryLoading) {
      return (
        <p className="text-sm text-brand-600 py-6 text-center">
          Analyzing document…
        </p>
      );
    }
    if (summaryError) {
      return (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {summaryError}
        </div>
      );
    }
    if (summary) {
      return (
        <div className="space-y-5">
          {(summary.title || summary.summary) && (
            <div>
              {summary.title ? (
                <p className="text-sm font-semibold text-brand-900">
                  {summary.title}
                </p>
              ) : null}
              {summary.summary ? (
                <p className="mt-2 text-sm leading-relaxed text-brand-700 whitespace-pre-wrap">
                  {summary.summary}
                </p>
              ) : null}
            </div>
          )}
          {summary.key_points.length > 0 ? (
            <div>
              <h5 className="text-xs font-semibold uppercase tracking-wide text-brand-500 mb-2">
                Key points
              </h5>
              <ul className="space-y-2">
                {summary.key_points.map((item, idx) => (
                  <li
                    key={`kp-${idx}`}
                    className="flex gap-2 text-sm text-brand-800 leading-relaxed"
                  >
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {summary.important_dates.length > 0 ? (
            <div>
              <h5 className="text-xs font-semibold uppercase tracking-wide text-brand-500 mb-2">
                Important dates
              </h5>
              <ul className="space-y-2">
                {summary.important_dates.map((item, idx) => (
                  <li
                    key={`dt-${idx}`}
                    className="flex gap-2 text-sm text-brand-800 leading-relaxed"
                  >
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {summary.action_items.length > 0 ? (
            <div>
              <h5 className="text-xs font-semibold uppercase tracking-wide text-brand-500 mb-2">
                Action items
              </h5>
              <ul className="space-y-2">
                {summary.action_items.map((item, idx) => (
                  <li
                    key={`ai-${idx}`}
                    className="flex gap-2 text-sm text-brand-800 leading-relaxed"
                  >
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {summary.truncated ? (
            <p className="text-xs text-amber-700 border-t border-brand-100 pt-3">
              Based on a truncated excerpt of the document.
            </p>
          ) : null}
        </div>
      );
    }
    if (summaryFallback) {
      return (
        <p className="text-sm leading-relaxed text-brand-700 whitespace-pre-wrap">
          {summaryFallback}
        </p>
      );
    }
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-brand-600">No summary yet.</p>
        <button
          type="button"
          disabled={summaryLoading || qaLoading}
          onClick={() => void handleSummarize()}
          className="mt-3 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          Summarize with AI
        </button>
      </div>
    );
  };

  return (
    <section
      ref={panelRef}
      className="rounded-xl border border-brand-200 bg-white shadow-sm overflow-hidden"
      aria-label="Document AI"
    >
      <div className="px-5 py-4 border-b border-brand-100 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
            Document AI
          </p>
          <h3 className="mt-1 text-base font-semibold text-brand-900 truncate">
            {displayTitle}
          </h3>
          {filename && filename !== displayTitle ? (
            <p className="mt-0.5 text-xs text-brand-300 truncate">{filename}</p>
          ) : null}
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-brand-200 p-1.5 text-brand-600 hover:bg-brand-50"
            aria-label="Close Document AI panel"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      <div className="flex border-b border-brand-100" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "summary"}
          onClick={() => setActiveTab("summary")}
          className={`flex-1 px-4 py-2.5 text-sm font-medium transition ${
            activeTab === "summary"
              ? "border-b-2 border-brand-600 text-brand-900 bg-brand-50/50"
              : "text-brand-500 hover:text-brand-800 hover:bg-brand-50/30"
          }`}
        >
          Summary
          {hasSummaryContent && !summaryLoading ? (
            <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-brand-500 align-middle" />
          ) : null}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "qa"}
          onClick={() => {
            setActiveTab("qa");
            window.setTimeout(() => questionRef.current?.focus(), 50);
          }}
          className={`flex-1 px-4 py-2.5 text-sm font-medium transition ${
            activeTab === "qa"
              ? "border-b-2 border-brand-600 text-brand-900 bg-brand-50/50"
              : "text-brand-500 hover:text-brand-800 hover:bg-brand-50/30"
          }`}
        >
          Q&amp;A
          {qaTurns.length > 0 ? (
            <span className="ml-1.5 text-xs font-normal text-brand-500">
              ({qaTurns.length})
            </span>
          ) : null}
        </button>
      </div>

      {activeTab === "summary" ? (
        <div className="px-5 py-5" role="tabpanel">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-brand-400">
              Structured overview of this document
            </p>
            <button
              type="button"
              disabled={summaryLoading || qaLoading}
              onClick={() => void handleSummarize()}
              className="rounded-lg border border-brand-200 px-3 py-1.5 text-xs font-medium text-brand-800 hover:bg-brand-50 disabled:opacity-50"
            >
              {summaryLoading
                ? "Analyzing…"
                : hasSummaryContent
                  ? "Refresh summary"
                  : "Summarize with AI"}
            </button>
          </div>
          {renderSummaryBody()}
        </div>
      ) : (
        <div className="flex flex-col" role="tabpanel">
          <div className="px-5 py-4 max-h-72 overflow-y-auto space-y-3 min-h-[8rem] bg-brand-50/30">
            {qaTurns.length === 0 && !qaLoading ? (
              <p className="text-sm text-brand-500 py-6 text-center">
                Ask a question about this document. Answers stay in this session
                only.
              </p>
            ) : null}
            {qaTurns.map((turn) => {
              const citations = turn.answer?.citations ?? [];
              const citationLabel = formatCitationLabel(citations);
              const answerText =
                turn.answer?.answer || turn.fallbackAnswer || "";
              return (
                <div key={turn.id} className="space-y-2">
                  <div className="ml-8 rounded-lg bg-brand-600 px-3 py-2 text-sm text-white">
                    {turn.question}
                  </div>
                  {turn.error ? (
                    <div className="mr-8 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {turn.error}
                    </div>
                  ) : (
                    <div className="mr-8 rounded-lg border border-brand-100 bg-white px-3 py-2.5 shadow-sm">
                      <p className="text-sm text-brand-800 whitespace-pre-wrap leading-relaxed">
                        {answerText || "No answer was returned."}
                      </p>
                      {citationLabel ? (
                        <p className="mt-2 text-xs font-medium text-brand-600">
                          {citationLabel}
                        </p>
                      ) : null}
                      {citations.some((c) => c.excerpt) ? (
                        <ul className="mt-2 space-y-1 border-t border-brand-50 pt-2">
                          {citations
                            .filter((c) => c.excerpt)
                            .map((c, idx) => (
                              <li
                                key={`ex-${turn.id}-${idx}`}
                                className="text-xs text-brand-500"
                              >
                                <span className="font-medium">
                                  p. {c.page_number}
                                </span>
                                {': "'}
                                {(c.excerpt || "").slice(0, 140)}
                                {(c.excerpt || "").length > 140 ? "…" : ""}
                                {'"'}
                              </li>
                            ))}
                        </ul>
                      ) : null}
                    </div>
                  )}
                </div>
              );
            })}
            {qaLoading ? (
              <p className="text-sm text-brand-600 text-center py-2">
                Reading document…
              </p>
            ) : null}
          </div>

          <form
            onSubmit={(e) => void handleAsk(e)}
            className="border-t border-brand-100 px-4 py-3 bg-white"
          >
            {qaError ? (
              <div className="mb-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {qaError}
              </div>
            ) : null}
            <div className="flex gap-2 items-end">
              <label htmlFor={questionInputId} className="sr-only">
                Question
              </label>
              <textarea
                id={questionInputId}
                ref={questionRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={2}
                placeholder="Ask a question about this document…"
                className="min-h-[2.75rem] flex-1 rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                disabled={qaLoading || summaryLoading}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void handleAsk();
                  }
                }}
              />
              <button
                type="submit"
                disabled={qaLoading || summaryLoading || !question.trim()}
                className="shrink-0 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {qaLoading ? "…" : "Ask"}
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
