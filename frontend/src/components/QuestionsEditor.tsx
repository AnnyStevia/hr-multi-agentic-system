"use client";

import { Plus, Trash2 } from "lucide-react";
import { Select } from "@/components/ui/select";
import type { JobQuestionInput, QuestionType } from "@/types/jobs";

const QUESTION_TYPES: Array<{ value: QuestionType; label: string }> = [
  { value: "short_text", label: "Short text" },
  { value: "long_text", label: "Long text" },
  { value: "number", label: "Number" },
  { value: "yes_no", label: "Yes / No" },
];

const field =
  "h-10 w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15";

export default function QuestionsEditor({
  questions,
  onChange,
}: {
  questions: JobQuestionInput[];
  onChange: (questions: JobQuestionInput[]) => void;
}) {
  const update = (index: number, patch: Partial<JobQuestionInput>) => {
    onChange(
      questions.map((question, i) => (i === index ? { ...question, ...patch } : question))
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[12px] text-brand-300">
          Candidates see these on the application form.
        </p>
        <button
          type="button"
          onClick={() =>
            onChange([
              ...questions,
              {
                prompt: "",
                question_type: "short_text",
                required: true,
                display_order: questions.length,
              },
            ])
          }
          className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-brand-200 bg-white px-3 text-xs font-semibold text-brand-700 transition hover:bg-[#f3f6f5]"
        >
          <Plus className="size-3.5" />
          Add question
        </button>
      </div>

      {questions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-brand-200 bg-[#f7faf9] px-4 py-8 text-center">
          <p className="text-sm text-brand-300">No questions yet.</p>
        </div>
      ) : (
        questions.map((question, index) => (
          <div
            key={index}
            className="space-y-3 rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                Question {index + 1}
              </p>
              <button
                type="button"
                onClick={() => onChange(questions.filter((_, i) => i !== index))}
                className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700 transition hover:text-rose-800"
              >
                <Trash2 className="size-3.5" />
                Remove
              </button>
            </div>
            <input
              required
              value={question.prompt}
              onChange={(e) => update(index, { prompt: e.target.value })}
              placeholder="What do you want to ask?"
              className={field}
            />
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <Select
                  value={question.question_type}
                  onValueChange={(next) =>
                    update(index, { question_type: next as QuestionType })
                  }
                  triggerClassName={field}
                  options={QUESTION_TYPES.map((type) => ({
                    value: type.value,
                    label: type.label,
                  }))}
                />
              </div>
              <label className="inline-flex shrink-0 items-center gap-2 text-sm font-medium text-brand-700">
                <input
                  type="checkbox"
                  checked={question.required}
                  onChange={(e) => update(index, { required: e.target.checked })}
                  className="size-4 rounded border-[#0f224a]/30 text-brand-600 focus:ring-[#0f224a]/20"
                />
                Required
              </label>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
