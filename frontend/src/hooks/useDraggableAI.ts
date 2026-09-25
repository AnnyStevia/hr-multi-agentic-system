"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "ai-assistant-orb-position";
const MARGIN = 16;
const DRAG_THRESHOLD = 5;
const ORB_SIZE = 64;

type Position = { x: number; y: number };

function defaultPosition(): Position {
  if (typeof window === "undefined") {
    return { x: 24, y: 24 };
  }
  return {
    x: Math.max(MARGIN, window.innerWidth - ORB_SIZE - 28),
    y: Math.max(MARGIN, window.innerHeight - ORB_SIZE - 28),
  };
}

function clamp(pos: Position): Position {
  if (typeof window === "undefined") return pos;
  const maxX = Math.max(MARGIN, window.innerWidth - ORB_SIZE - MARGIN);
  const maxY = Math.max(MARGIN, window.innerHeight - ORB_SIZE - MARGIN);
  return {
    x: Math.min(maxX, Math.max(MARGIN, pos.x)),
    y: Math.min(maxY, Math.max(MARGIN, pos.y)),
  };
}

function loadPosition(): Position {
  if (typeof window === "undefined") return defaultPosition();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultPosition();
    const parsed = JSON.parse(raw) as Position;
    if (typeof parsed.x !== "number" || typeof parsed.y !== "number") {
      return defaultPosition();
    }
    return clamp(parsed);
  } catch {
    return defaultPosition();
  }
}

export function useDraggableAI(onClick: () => void) {
  const [position, setPosition] = useState<Position>(defaultPosition);
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef<{
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    moved: boolean;
    pointerId: number;
  } | null>(null);

  useEffect(() => {
    setPosition(loadPosition());
  }, []);

  useEffect(() => {
    const onResize = () => setPosition((prev) => clamp(prev));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const persist = useCallback((pos: Position) => {
    const next = clamp(pos);
    setPosition(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* ignore quota */
    }
  }, []);

  const onPointerDown = useCallback(
    (event: React.PointerEvent<HTMLButtonElement>) => {
      if (event.button !== 0) return;
      event.currentTarget.setPointerCapture(event.pointerId);
      dragRef.current = {
        startX: event.clientX,
        startY: event.clientY,
        originX: position.x,
        originY: position.y,
        moved: false,
        pointerId: event.pointerId,
      };
      setDragging(true);
    },
    [position.x, position.y]
  );

  const onPointerMove = useCallback((event: React.PointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    if (!drag || event.pointerId !== drag.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) > DRAG_THRESHOLD) {
      drag.moved = true;
    }
    if (drag.moved) {
      setPosition(clamp({ x: drag.originX + dx, y: drag.originY + dy }));
    }
  }, []);

  const onPointerUp = useCallback(
    (event: React.PointerEvent<HTMLButtonElement>) => {
      const drag = dragRef.current;
      if (!drag || event.pointerId !== drag.pointerId) return;
      try {
        event.currentTarget.releasePointerCapture(event.pointerId);
      } catch {
        /* already released */
      }
      const wasDrag = drag.moved;
      const next = clamp({
        x: drag.originX + (event.clientX - drag.startX),
        y: drag.originY + (event.clientY - drag.startY),
      });
      dragRef.current = null;
      setDragging(false);
      if (wasDrag) {
        persist(next);
      } else {
        onClick();
      }
    },
    [onClick, persist]
  );

  return {
    position,
    dragging,
    orbSize: ORB_SIZE,
    handlers: {
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel: onPointerUp,
    },
  };
}
