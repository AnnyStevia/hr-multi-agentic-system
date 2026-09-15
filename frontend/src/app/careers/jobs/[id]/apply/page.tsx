"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { ApplicationDetail } from "@/types/applications";
import type { EducationEntry, ExperienceEntry } from "@/types/applications";
import type { Job, JobQuestion } from "@/types/jobs";

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

const emptyEducation = (): EducationEntry => ({ institution: "", degree: "", field_of_study: "" });
const emptyExperience = (): ExperienceEntry => ({ company: "", title: "", description: "" });

export default function ApplyPage() {
  const params = useParams<{ id: string }>();
  const jobId = Number(params.id);
  const { user } = useAuth();
  const [job, setJob] = useState<Job | null>(null);
  const [existing, setExisting] = useState<ApplicationDetail | null>(null);
  const [submitted, setSubmitted] = useState<ApplicationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [phone, setPhone] = useState("");
  const [education, setEducation] = useState<EducationEntry[]>([emptyEducation()]);
  const [experience, setExperience] = useState<ExperienceEntry[]>([emptyExperience()]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [cv, setCv] = useState<File | null>(null);
  const [coverLetter, setCoverLetter] = useState<File | null>(null);

  useEffect(() => {
    if (user?.phone) {
      setPhone(user.phone);
    }
  }, [user]);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        const jobData = await api.getCareerJob(jobId);
        setJob(jobData);
        try {
          setExisting(await api.getMyJobApplication(jobId));
        } catch {
          setExisting(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load job");
      } finally {
        setLoading(false);
      }
    };
    if (!Number.isNaN(jobId)) {
      load();
    }
  }, [jobId]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setFieldError("");
    if (!cv) {
      setFieldError("A CV is required (PDF, DOC, or DOCX).");
      return;
    }
    if (phone.trim().replace(/\D/g, "").length < 8) {
      setFieldError("Enter a valid phone number.");
      return;
    }
    if (education.some((item) => !item.institution.trim()) || experience.some((item) => !item.company.trim() || !item.title.trim())) {
      setFieldError("Complete at least one education and one experience entry.");
      return;
    }
    const missing = (job?.questions || []).filter((question) => question.required && !answers[question.id]?.trim());
    if (missing.length) {
      setFieldError(`Answer required: ${missing[0].prompt}`);
      return;
    }

    const form = new FormData();
    form.append("phone", phone.trim());
    form.append("education", JSON.stringify(education));
    form.append("experience", JSON.stringify(experience));
    form.append(
      "answers",
      JSON.stringify(
        Object.entries(answers)
          .filter(([, value]) => value.trim())
          .map(([question_id, value]) => ({ question_id: Number(question_id), value })),
      ),
    );
    form.append("cv", cv);
    if (coverLetter) {
      form.append("cover_letter", coverLetter);
    }

    setSubmitting(true);
    try {
      setSubmitted(await api.applyToJob(jobId, form));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit application");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!job) {
    return <p className="text-red-700">{error || "Job not found"}</p>;
  }

  if (existing || submitted) {
    const application = submitted || existing;
    return (
      <div className="bg-white rounded-xl border shadow-sm p-6 space-y-3">
        <h1 className="text-2xl font-bold text-gray-900">You have already applied to this job</h1>
        <p className="text-sm text-gray-600">
          Your application for <span className="font-medium">{job.title}</span> has been received.
          Status: {application?.status}.
        </p>
        <Link href={`/careers/jobs/${job.id}`} className="inline-block text-sm text-brand-700">
          Back to job
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/careers/jobs/${job.id}`} className="text-sm text-gray-500 hover:text-gray-800">
          {job.title}
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">Apply</h1>
        <p className="mt-1 text-sm text-gray-600">
          Required fields are marked. Cover letter is optional.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border shadow-sm p-6 space-y-6">
        {(error || fieldError) && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {fieldError || error}
          </div>
        )}

        <section className="space-y-3">
          <h2 className="text-sm font-medium text-gray-900">Contact</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="apply-email" className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                id="apply-email"
                type="email"
                value={user?.email || ""}
                readOnly
                className={`${inputClass} bg-gray-50 text-gray-700`}
              />
              <p className="mt-1 text-xs text-gray-500">This is the email on your candidate account.</p>
            </div>
            <div>
              <label htmlFor="apply-phone" className="block text-sm font-medium text-gray-700 mb-1">
                Phone number
              </label>
              <input
                id="apply-phone"
                type="tel"
                required
                minLength={8}
                maxLength={30}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+216 20 123 456"
                className={inputClass}
              />
            </div>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-medium text-gray-900">Education / training (required)</h2>
          {education.map((item, index) => (
            <div key={index} className="grid grid-cols-1 sm:grid-cols-2 gap-3 border border-gray-200 rounded-lg p-4">
              <input required placeholder="Institution" value={item.institution} onChange={(e) => {
                const next = [...education];
                next[index] = { ...item, institution: e.target.value };
                setEducation(next);
              }} className={inputClass} />
              <input placeholder="Degree (optional)" value={item.degree || ""} onChange={(e) => {
                const next = [...education];
                next[index] = { ...item, degree: e.target.value };
                setEducation(next);
              }} className={inputClass} />
              <input placeholder="Field of study (optional)" value={item.field_of_study || ""} onChange={(e) => {
                const next = [...education];
                next[index] = { ...item, field_of_study: e.target.value };
                setEducation(next);
              }} className={inputClass} />
            </div>
          ))}
          <button type="button" className="text-sm text-brand-700" onClick={() => setEducation([...education, emptyEducation()])}>
            Add education
          </button>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-medium text-gray-900">Experience (required)</h2>
          {experience.map((item, index) => (
            <div key={index} className="grid grid-cols-1 sm:grid-cols-2 gap-3 border border-gray-200 rounded-lg p-4">
              <input required placeholder="Company" value={item.company} onChange={(e) => {
                const next = [...experience];
                next[index] = { ...item, company: e.target.value };
                setExperience(next);
              }} className={inputClass} />
              <input required placeholder="Title" value={item.title} onChange={(e) => {
                const next = [...experience];
                next[index] = { ...item, title: e.target.value };
                setExperience(next);
              }} className={inputClass} />
              <textarea placeholder="Description (optional)" value={item.description || ""} onChange={(e) => {
                const next = [...experience];
                next[index] = { ...item, description: e.target.value };
                setExperience(next);
              }} className={`${inputClass} sm:col-span-2`} rows={3} />
            </div>
          ))}
          <button type="button" className="text-sm text-brand-700" onClick={() => setExperience([...experience, emptyExperience()])}>
            Add experience
          </button>
        </section>

        {(job.questions || []).length > 0 && (
          <section className="space-y-4">
            <h2 className="text-sm font-medium text-gray-900">Questions for this job</h2>
            {job.questions.map((question) => (
              <QuestionField
                key={question.id}
                question={question}
                value={answers[question.id] || ""}
                onChange={(value) => setAnswers({ ...answers, [question.id]: value })}
              />
            ))}
          </section>
        )}

        <section className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">CV (required)</label>
            <input
              type="file"
              accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => setCv(e.target.files?.[0] || null)}
            />
            <p className="mt-1 text-xs text-gray-500">PDF, DOC, or DOCX. Max 5 MB.</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cover letter (optional)</label>
            <input
              type="file"
              accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => setCoverLetter(e.target.files?.[0] || null)}
            />
          </div>
        </section>

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-brand-600 text-white py-2.5 rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Submitting..." : "Submit application"}
        </button>
      </form>
    </div>
  );
}

function QuestionField({
  question,
  value,
  onChange,
}: {
  question: JobQuestion;
  value: string;
  onChange: (value: string) => void;
}) {
  const label = `${question.prompt}${question.required ? " (required)" : " (optional)"}`;
  if (question.question_type === "long_text") {
    return (
      <label className="block text-sm text-gray-700">
        {label}
        <textarea required={question.required} value={value} onChange={(e) => onChange(e.target.value)} className={`${inputClass} mt-1`} rows={4} />
      </label>
    );
  }
  if (question.question_type === "yes_no") {
    return (
      <fieldset>
        <legend className="text-sm text-gray-700">{label}</legend>
        <div className="mt-2 flex gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="radio" name={`q-${question.id}`} checked={value === "yes"} onChange={() => onChange("yes")} required={question.required} />
            Yes
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name={`q-${question.id}`} checked={value === "no"} onChange={() => onChange("no")} />
            No
          </label>
        </div>
      </fieldset>
    );
  }
  return (
    <label className="block text-sm text-gray-700">
      {label}
      <input
        required={question.required}
        type={question.question_type === "number" ? "number" : "text"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`${inputClass} mt-1`}
      />
    </label>
  );
}
