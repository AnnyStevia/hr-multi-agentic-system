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
  AssistantAgentId,
  ConversationMessage,
  KnowledgeCitation,
  RecruitmentPendingConfirmation,
} from "@/types/ai";

const CONVERSATION_STORAGE_KEY = "ai_assistant_conversation_id";

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
  clearConversation: () => Promise<void>;
  hasConversation: boolean;
  conversationId: number | null;
};

const AIAssistantContext = createContext<AIAssistantContextValue | null>(null);

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function readStoredConversationId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(CONVERSATION_STORAGE_KEY);
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function storeConversationId(id: number | null): void {
  if (typeof window === "undefined") return;
  if (id == null) {
    sessionStorage.removeItem(CONVERSATION_STORAGE_KEY);
    return;
  }
  sessionStorage.setItem(CONVERSATION_STORAGE_KEY, String(id));
}

function mapHistoryMessage(row: ConversationMessage): AIChatMessage {
  const agentId = (row.agent_id ?? undefined) as AssistantAgentId | undefined;
  const citations =
    row.citations && row.citations.length > 0 ? row.citations : undefined;
  const pendingHistorical =
    row.pending && !row.pending.resolved ? row.pending : null;
  const confirmationResolved =
    row.pending?.resolved === true ? ("confirmed" as const) : undefined;

  return {
    id: `srv-${row.id}`,
    role: row.role,
    content: row.content,
    agentId,
    citations,
    pendingConfirmation: null,
    pendingHistorical,
    confirmationResolved,
    serverMessageId: row.id,
  };
}

function mapError(err: unknown, confirmAgentId?: AssistantAgentId): string {
  if (err instanceof ApiClientError) {
    if (err.status === 403) {
      return "You do not have access to perform this assistant action.";
    }
    if (err.status === 409) {
      if (confirmAgentId === "leave" && err.message) {
        return err.message;
      }
      if (confirmAgentId === "onboarding" && err.message) {
        return err.message;
      }
      if (confirmAgentId === "training" && err.message) {
        return err.message;
      }
      if (confirmAgentId === "offboarding" && err.message) {
        return err.message;
      }
      if (confirmAgentId === "recruitment") {
        return "This confirmation is no longer valid or the action cannot be applied in the current state.";
      }
      return err.message || "This request conflicts with the current state.";
    }
    if (err.status === 404) {
      return "That conversation was not found. Starting a new thread.";
    }
    if (err.status === 422) {
      return "Please enter a valid question.";
    }
    if (err.status === 0) {
      return "Cannot reach the server. Please try again in a moment.";
    }
    return "Something went wrong with Pulse. Please try again.";
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
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const skipCloseOnMount = useRef(true);
  const conversationIdRef = useRef<number | null>(null);

  const openAssistant = useCallback(() => setOpen(true), []);
  const closeAssistant = useCallback(() => setOpen(false), []);
  const toggleAssistant = useCallback(() => setOpen((value) => !value), []);
  const clearError = useCallback(() => setError(null), []);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  useEffect(() => {
    if (skipCloseOnMount.current) {
      skipCloseOnMount.current = false;
      return;
    }
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;
    const stored = readStoredConversationId();
    if (stored == null) {
      setHydrated(true);
      return;
    }

    void (async () => {
      try {
        const detail = await api.getAIConversation(stored);
        if (cancelled) return;
        setConversationId(detail.id);
        storeConversationId(detail.id);
        setMessages(detail.messages.map(mapHistoryMessage));
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiClientError && err.status === 404) {
          storeConversationId(null);
          setConversationId(null);
        }
      } finally {
        if (!cancelled) setHydrated(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!open || !hydrated) return;
    const stored = readStoredConversationId();
    if (stored == null || messages.length > 0 || conversationId != null) return;

    let cancelled = false;
    void (async () => {
      try {
        const detail = await api.getAIConversation(stored);
        if (cancelled) return;
        setConversationId(detail.id);
        storeConversationId(detail.id);
        setMessages(detail.messages.map(mapHistoryMessage));
      } catch {
        if (!cancelled) {
          storeConversationId(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, hydrated, messages.length, conversationId]);

  const ask = useCallback(
    async (question?: string) => {
      const text = (question ?? draft).trim();
      if (!text) {
        setError("Please enter a question.");
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
        const activeId = conversationIdRef.current;
        const result = await api.askAssistant({
          message: text,
          conversation_id: activeId,
        });
        if (result.conversation_id != null) {
          setConversationId(result.conversation_id);
          storeConversationId(result.conversation_id);
          conversationIdRef.current = result.conversation_id;
        }
        const pending: RecruitmentPendingConfirmation | null =
          result.pending_confirmation ?? null;
        const citations: KnowledgeCitation[] = result.citations ?? [];
        const agentId: AssistantAgentId | undefined =
          result.agent_id ?? undefined;

        const assistantMessage: AIChatMessage = {
          id: newId(),
          role: "assistant",
          content: result.answer,
          agentId,
          citations: citations.length > 0 ? citations : undefined,
          pendingConfirmation: pending,
          serverMessageId: result.message_id ?? undefined,
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        if (err instanceof ApiClientError && err.status === 404) {
          storeConversationId(null);
          setConversationId(null);
          conversationIdRef.current = null;
        }
        setError(mapError(err));
      } finally {
        setLoading(false);
      }
    },
    [draft, loading]
  );

  const confirmPending = useCallback(
    async (messageId: string) => {
      if (loading) return;
      const target = messages.find((m) => m.id === messageId);
      const token = target?.pendingConfirmation?.token;
      if (!token) return;

      const agentId = target?.agentId;
      if (
        agentId !== "leave" &&
        agentId !== "recruitment" &&
        agentId !== "onboarding" &&
        agentId !== "training" &&
        agentId !== "offboarding"
      ) {
        setError("Cannot confirm: missing agent for this action.");
        return;
      }

      setError(null);
      setLoading(true);
      try {
        const result =
          agentId === "leave"
            ? await api.confirmLeaveAction({ confirmation_token: token })
            : agentId === "recruitment"
              ? await api.confirmRecruitmentAction({
                  confirmation_token: token,
                })
              : agentId === "training"
                ? await api.confirmTrainingAction({
                    confirmation_token: token,
                  })
                : agentId === "offboarding"
                  ? await api.confirmOffboardingAction({
                      confirmation_token: token,
                    })
                  : await api.confirmOnboardingAction({
                      confirmation_token: token,
                    });
        setMessages((prev) =>
          prev.map((m) =>
            m.id === messageId
              ? {
                  ...m,
                  pendingConfirmation: null,
                  pendingHistorical: null,
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
            agentId,
          },
        ]);
      } catch (err) {
        setError(mapError(err, agentId));
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
              content: m.content + "\n\n(Cancelled — no changes were made.)",
            }
          : m
      )
    );
  }, []);

  const clearConversation = useCallback(async () => {
    if (loading) return;
    const idToDelete = conversationIdRef.current ?? readStoredConversationId();
    setError(null);
    if (idToDelete != null) {
      setLoading(true);
      try {
        await api.deleteAIConversation(idToDelete);
      } catch (err) {
        if (!(err instanceof ApiClientError && err.status === 404)) {
          setError(mapError(err));
          setLoading(false);
          return;
        }
      } finally {
        setLoading(false);
      }
    }
    setMessages([]);
    setDraft("");
    setConversationId(null);
    conversationIdRef.current = null;
    storeConversationId(null);
  }, [loading]);

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
      clearConversation,
      hasConversation: messages.length > 0,
      conversationId,
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
      clearConversation,
      conversationId,
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
