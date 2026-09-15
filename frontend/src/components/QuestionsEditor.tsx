"use client";

import type { JobQuestionInput, QuestionType } from "@/types/jobs";

const QUESTION_TYPES: Array<{ value: QuestionType; label: string }> = [
  { value: "short_text", label: "Short text" },
  { value: "long_text", label: "Long text" },
  { value: "number", label: "Number" },
  { value: "yes_no", label: "Yes / No" },
];

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

export default function QuestionsEditor({
  questions,
  onChange,
}: {
  questions: JobQuestionInput[];
  onChange: (questions: JobQuestionInput[]) => void;
}) {
  const update = (index: number, patch: Partial<JobQuestionInput>) => {
    onChange(questions.map((question, i) => (i === index ? { ...question, ...patch } : question)));
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-medium text-gray-900">Application questions</h2>
          <p className="text-xs text-gray-500">Optional. Candidates answer these when they apply.</p>
        </div>
        <button
          type="button"
          onClick={() =>
            onChange([
              ...questions,
              { prompt: "", question_type: "short_text", required: true, display_order: questions.length },
            ])
          }
          className="text-sm text-brand-700 hover:text-brand-800"
        >
          Add question
        </button>
      </div>

      {questions.length === 0 ? (
        <p className="text-sm text-gray-500">No questions yet.</p>
      ) : (
        questions.map((question, index) => (
          <div key={index} className="border border-gray-200 rounded-lg p-4 space-y-3">
            <input
              required
              value={question.prompt}
              onChange={(e) => update(index, { prompt: e.target.value })}
              placeholder="Question"
              className={inputClass}
            />
            <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
              <select
                value={question.question_type}
                onChange={(e) => update(index, { question_type: e.target.value as QuestionType })}
                className={inputClass}
              >
                {QUESTION_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-2 text-sm text-gray-700 whitespace-nowrap">
                <input
                  type="checkbox"
                  checked={question.required}
                  onChange={(e) => update(index, { required: e.target.checked })}
                />
                Required
              </label>
              <button
                type="button"
                onClick={() => onChange(questions.filter((_, i) => i !== index))}
                className="text-sm text-red-700 hover:text-red-800"
              >
                Remove
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
