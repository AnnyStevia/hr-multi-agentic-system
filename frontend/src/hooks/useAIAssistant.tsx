"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import { api, ApiClientError } from "@/lib/api";
import type {
  AIChatMessage,
  KnowledgeCitation,
  RecruitmentPendingConfirmation,
} from "@/types/ai";

type AIAssistantContextValue = {
  open: boolean;
  openAssistant: () => void;
  closeAssistant: () => void;
  toggleAssistant: () => void;
  messages: AIChatMessage[];
  draft: string;
  setDraft: (value: string) => void;
  loading: boolean;
  error: string | null;
  clearError: () => void;
  ask: (question?: string) => Promise<void>;
  confirmPending: (messageId: string) => Promise<void>;
  cancelPending: (messageId: string) => void;
  hasConversation: boolean;
};

const AIAssistantContext = createContext<AIAssistantContextValue | null>(null);

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function mapError(err: unknown, options: { recruitment: boolean }): string {
  const recruitment = options.recruitment;
  if (err instanceof ApiClientError) {
    if (err.status === 403) {
      return recruitment
        ? "You do not have recruitment access for the HR assistant."
        : "You do not have access to company knowledge. Ask HR if you need document permissions.";
    }
    if (err.status === 409) {
      return recruitment
        ? "This confirmation is no longer valid or the action cannot be applied in the current state."
        : err.message || "This request conflicts with the current state.";
    }
    if (err.status === 422) {
      return recruitment
        ? "Please enter a valid question."
        : err.message || "Please enter a valid question.";
    }
    if (err.status === 0) {
      return "Cannot reach the server. Please try again in a moment.";
    }
    return recruitment
      ? "Something went wrong while consulting recruitment data. Please try again."
      : "Something went wrong while consulting company knowledge. Please try again.";
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return "Something went wrong. Please try again.";
}

export function AIAssistantProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<AIChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const skipCloseOnMount = useRef(true);
  const useRecruitment = pathname.startsWith("/hr");

  const openAssistant = useCallback(() => setOpen(true), []);
  const closeAssistant = useCallback(() => setOpen(false), []);
  const toggleAssistant = useCallback(() => setOpen((value) => !value), []);
  const clearError = useCallback(() => setError(null), []);

  useEffect(() => {
    if (skipCloseOnMount.current) {
      skipCloseOnMount.current = false;
      return;
    }
    setOpen(false);
  }, [pathname]);

  const ask = useCallback(
    async (question?: string) => {
      const text = (question ?? draft).trim();
      if (!text) {
        setError(
          useRecruitment
            ? "Please enter a recruitment or interview question."
            : "Please enter a question about company knowledge."
        );
        return;
      }
      if (loading) return;

      setError(null);
      setDraft("");
      const userMessage: AIChatMessage = {
        id: newId(),
        role: "user",
        content: text,
      };
      setMessages((prev) => [...prev, userMessage]);
      setLoading(true);

      try {
        if (useRecruitment) {
          const result = await api.askRecruitmentAgent({ question: text });
          const pending: RecruitmentPendingConfirmation | null =
            result.pending_confirmation ?? null;
          const assistantMessage: AIChatMessage = {
            id: newId(),
            role: "assistant",
            content: result.answer,
            pendingConfirmation: pending,
          };
          setMessages((prev) => [...prev, assistantMessage]);
        } else {
          const result = await api.askKnowledgeAgent({ question: text });
          const citations: KnowledgeCitation[] = result.citations ?? [];
          const assistantMessage: AIChatMessage = {
            id: newId(),
            role: "assistant",
            content: result.answer,
            citations,
            has_context: result.has_context,
          };
          setMessages((prev) => [...prev, assistantMessage]);
        }
      } catch (err) {
        setError(mapError(err, { recruitment: useRecruitment }));
      } finally {
        setLoading(false);
      }
    },
    [draft, loading, useRecruitment]
  );

  const confirmPending = useCallback(
    async (messageId: string) => {
      if (loading) return;
      const target = messages.find((m) => m.id === messageId);
      const token = target?.pendingConfirmation?.token;
      if (!token) return;

      setError(null);
      setLoading(true);
      try {
        const result = await api.confirmRecruitmentAction({
          confirmation_token: token,
        });
        setMessages((prev) =>
          prev.map((m) =>
            m.id === messageId
              ? {
                  ...m,
                  pendingConfirmation: null,
                  confirmationResolved: "confirmed" as const,
                }
              : m
          )
        );
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: result.answer,
          },
        ]);
      } catch (err) {
        setError(mapError(err, { recruitment: true }));
      } finally {
        setLoading(false);
      }
    },
    [loading, messages]
  );

  const cancelPending = useCallback((messageId: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? {
              ...m,
              pendingConfirmation: null,
              confirmationResolved: "cancelled" as const,
              content:
                m.content +
                "\n\n(Cancelled — no changes were made.)",
            }
          : m
      )
    );
  }, []);

  const value = useMemo(
    () => ({
      open,
      openAssistant,
      closeAssistant,
      toggleAssistant,
      messages,
      draft,
      setDraft,
      loading,
      error,
      clearError,
      ask,
      confirmPending,
      cancelPending,
      hasConversation: messages.length > 0,
    }),
    [
      open,
      openAssistant,
      closeAssistant,
      toggleAssistant,
      messages,
      draft,
      loading,
      error,
      clearError,
      ask,
      confirmPending,
      cancelPending,
    ]
  );

  return (
    <AIAssistantContext.Provider value={value}>{children}</AIAssistantContext.Provider>
  );
}

export function useAIAssistant(): AIAssistantContextValue {
  const context = useContext(AIAssistantContext);
  if (!context) {
    throw new Error("useAIAssistant must be used within AIAssistantProvider");
  }
  return context;
}
