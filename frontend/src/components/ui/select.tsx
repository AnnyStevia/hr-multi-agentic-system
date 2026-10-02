"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export type SelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

export type SelectProps = {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  className?: string;
  triggerClassName?: string;
  disabled?: boolean;
  id?: string;
  name?: string;
  required?: boolean;
  "aria-label"?: string;
};

export function Select({
  value,
  onValueChange,
  options,
  placeholder = "Select…",
  className,
  triggerClassName,
  disabled = false,
  id,
  name,
  required = false,
  "aria-label": ariaLabel,
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const autoId = useId();
  const listboxId = `${autoId}-listbox`;

  const selected = useMemo(
    () => options.find((option) => option.value === value) ?? null,
    [options, value]
  );

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const selectedEl = listRef.current?.querySelector<HTMLElement>(
      '[data-selected="true"]'
    );
    selectedEl?.scrollIntoView({ block: "nearest" });
  }, [open, value]);

  return (
    <div ref={rootRef} className={cn("relative w-full", className)}>
      <select
        tabIndex={-1}
        aria-hidden
        required={required}
        name={name}
        value={value}
        disabled={disabled}
        onChange={() => {}}
        className="pointer-events-none absolute h-px w-px opacity-0 ui-select-native-proxy"
      >
        {placeholder && !options.some((option) => option.value === "") ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {options.map((option) => (
          <option key={`native-${option.value || "empty"}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <button
        type="button"
        id={id}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-label={ariaLabel}
        onClick={() => {
          if (!disabled) setOpen((prev) => !prev);
        }}
        className={cn(
          "flex h-10 w-full items-center justify-between gap-2 rounded-xl border border-[#0f224a]/28 bg-white px-3 text-left text-sm text-[#0f224a] outline-none transition",
          "hover:border-[#0f224a]/50",
          "focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/16",
          "disabled:cursor-not-allowed disabled:bg-[#f4f6f9] disabled:opacity-55",
          open && "border-[#0f224a] ring-2 ring-[#0f224a]/16",
          triggerClassName
        )}
      >
        <span className={cn("truncate", !selected && "text-[#0f224a]/45")}>
          {selected?.label ?? placeholder}
        </span>
        <ChevronDown
          className={cn(
            "size-4 shrink-0 text-[#0f224a]/70 transition-transform duration-200",
            open && "rotate-180"
          )}
          aria-hidden
        />
      </button>

      {open ? (
        <ul
          ref={listRef}
          id={listboxId}
          role="listbox"
          aria-activedescendant={
            selected ? `${listboxId}-option-${selected.value || "empty"}` : undefined
          }
          className="absolute left-0 right-0 z-50 mt-1.5 max-h-60 overflow-auto rounded-xl border border-[#0f224a]/20 bg-white p-1.5 shadow-[0_18px_40px_-18px_rgba(15,34,74,0.55),0_0_0_1px_rgba(15,34,74,0.06)]"
        >
          {options.map((option) => {
            const isSelected = option.value === value;
            const optionId = `${listboxId}-option-${option.value || "empty"}`;
            return (
              <li key={optionId} role="presentation">
                <button
                  type="button"
                  id={optionId}
                  role="option"
                  aria-selected={isSelected}
                  data-selected={isSelected ? "true" : undefined}
                  disabled={option.disabled}
                  onClick={() => {
                    if (option.disabled) return;
                    onValueChange(option.value);
                    setOpen(false);
                  }}
                  className={cn(
                    "flex w-full items-center rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors",
                    "disabled:cursor-not-allowed disabled:opacity-40",
                    isSelected
                      ? "bg-[#0f224a] text-white"
                      : "text-[#0f224a]/90 hover:bg-[#0f224a] hover:text-white"
                  )}
                >
                  {option.label}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
