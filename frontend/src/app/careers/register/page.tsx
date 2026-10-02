"use client";

import { FormEvent, Suspense, useState, type ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";
import { Manrope } from "next/font/google";
import { useSearchParams } from "next/navigation";
import { ArrowRight, Bell, FileText, Lock, Mail, Search } from "lucide-react";
import { PasswordInput } from "@/components/PasswordInput";
import { useAuth } from "@/hooks/useAuth";
import { resolvePostAuthPath } from "@/lib/roles";

const manrope = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

function TalentMark({ tone = "dark" }: { tone?: "dark" | "light" }) {
  const isLight = tone === "light";

  return (
    <div className="flex items-center gap-3">
      <div
        className={`flex h-9 w-9 items-center justify-center ${
          isLight
            ? "border border-white/35 bg-white/10"
            : "border border-brand-200 bg-brand-50"
        }`}
        aria-hidden="true"
      >
        <div className="grid grid-cols-2 gap-[3px]">
          <span
            className={`h-1.5 w-1.5 ${isLight ? "bg-white" : "bg-brand-500"}`}
          />
          <span
            className={`h-1.5 w-1.5 ${isLight ? "bg-white/65" : "bg-brand-500/65"}`}
          />
          <span
            className={`h-1.5 w-1.5 ${isLight ? "bg-white/65" : "bg-brand-500/65"}`}
          />
          <span
            className={`h-1.5 w-1.5 ${isLight ? "bg-white" : "bg-brand-500"}`}
          />
        </div>
      </div>
      <div className="leading-none">
        <p
          className={`text-[13px] font-semibold tracking-[0.14em] uppercase ${
            isLight ? "text-white" : "text-brand-900"
          }`}
        >
          Talent Portal
        </p>
        <p
          className={`mt-1 text-[10px] font-medium tracking-[0.18em] uppercase ${
            isLight ? "text-white/55" : "text-brand-300"
          }`}
        >
          Careers access
        </p>
      </div>
    </div>
  );
}

function HeroPoint({
  icon,
  title,
  body,
}: {
  icon: ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center border border-white/20 bg-white/10 text-white">
        {icon}
      </div>
      <div>
        <p className="text-sm font-semibold text-white">{title}</p>
        <p className="mt-0.5 text-[13px] leading-snug text-white/65">{body}</p>
      </div>
    </div>
  );
}

function RegisterForm() {
  const { register, loading: authLoading, user } = useAuth();
  const searchParams = useSearchParams();
  const next = searchParams.get("next");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (authLoading) {
    return (
      <div
        className={`${manrope.className} flex h-dvh items-center justify-center bg-[#f4f6f8]`}
      >
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-brand-600" />
      </div>
    );
  }

  if (user) {
    window.location.href = resolvePostAuthPath(user, next);
    return null;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setSubmitting(true);
    try {
      await register(
        {
          first_name: firstName,
          last_name: lastName,
          email,
          password,
        },
        next,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  const loginHref = next
    ? `/careers/login?next=${encodeURIComponent(next)}`
    : "/careers/login?next=%2Fcareers%2Fjobs";

  const fieldClass =
    "w-full rounded-sm border border-brand-200 bg-white py-2 px-3 text-sm text-brand-900 outline-none transition placeholder:text-brand-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30";
  const passwordClass =
    "!rounded-sm !py-2 border-brand-200 pl-11 text-sm text-brand-900 placeholder:text-brand-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30";

  return (
    <div className={`${manrope.className} h-dvh overflow-hidden bg-[#f4f6f8]`}>
      <div className="flex h-full w-full flex-col lg:flex-row">
        {/* Corporate hero */}
        <section className="relative hidden h-full overflow-hidden lg:block lg:w-[48%]">
          <div className="absolute inset-0 animate-dash-fade-in">
            <Image
              src="/images/careers/pexels-tima-miroshnichenko-5439375.jpg"
              alt="Professional interview in a corporate office"
              fill
              className="object-cover object-[center_30%]"
              sizes="48vw"
              priority
            />
          </div>

          <div
            className="absolute inset-0 bg-[#0f224a]/55"
            aria-hidden="true"
          />
          <div
            className="absolute inset-0 bg-gradient-to-t from-[#0f224a] via-[#0f224a]/50 to-[#0f224a]/30"
            aria-hidden="true"
          />
          <div
            className="absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-white/25 to-transparent"
            aria-hidden="true"
          />
          <div
            className="absolute bottom-0 left-0 h-1 w-full bg-brand-500"
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.07]"
            style={{
              backgroundImage:
                "linear-gradient(rgba(255,255,255,0.55) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.55) 1px, transparent 1px)",
              backgroundSize: "48px 48px",
            }}
            aria-hidden="true"
          />

          <div className="relative z-10 flex h-full flex-col px-10 py-8 xl:px-12 xl:py-10">
            <div className="animate-dash-fade-in">
              <TalentMark tone="light" />
            </div>

            <div className="mt-auto max-w-lg pb-8 animate-dash-fade-up">
              <div className="mb-4 flex items-center gap-3">
                <span className="h-px w-10 bg-brand-500" />
                <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-white/65">
                  Your next opportunity
                </span>
              </div>
              <h1 className="text-[2.35rem] font-semibold leading-[1.12] tracking-[-0.02em] text-white xl:text-[2.65rem]">
                Create your{" "}
                <span className="text-[#5fd4a8]">candidate account</span>
              </h1>
              <p className="mt-4 max-w-md text-[14px] leading-relaxed text-white/70">
                Register once to explore published roles, submit applications,
                and follow your progress with confidence.
              </p>

              <div className="mt-7 space-y-4">
                <HeroPoint
                  icon={<Search className="h-3.5 w-3.5" strokeWidth={2} />}
                  title="Explore opportunities"
                  body="Find roles that match your skills."
                />
                <HeroPoint
                  icon={<FileText className="h-3.5 w-3.5" strokeWidth={2} />}
                  title="Track your applications"
                  body="Stay up to date at every step."
                />
                <HeroPoint
                  icon={<Bell className="h-3.5 w-3.5" strokeWidth={2} />}
                  title="Get notified"
                  body="Receive updates on your application status."
                />
              </div>
            </div>
          </div>
        </section>

        {/* Registration panel — locked to viewport, no scroll */}
        <section className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden">
          <div
            className="pointer-events-none absolute inset-0"
            aria-hidden="true"
          >
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_50%_at_100%_0%,rgba(2,152,112,0.07),transparent_55%)]" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_50%_40%_at_0%_100%,rgba(15,34,74,0.05),transparent_50%)]" />
          </div>

          <div className="relative flex h-full min-h-0 flex-col overflow-hidden px-5 py-4 sm:px-10 lg:px-12 lg:py-5">
            <div className="mb-3 flex shrink-0 items-center justify-between lg:hidden">
              <TalentMark />
            </div>

            <div className="flex min-h-0 flex-1 flex-col justify-center overflow-hidden">
              <div className="mx-auto w-full max-w-[400px] animate-dash-fade-up">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-brand-300">
                  Candidate registration
                </p>
                <h2 className="mt-1 text-[1.45rem] font-semibold tracking-tight text-brand-900">
                  Create a candidate account
                </h2>
                <p className="mt-1 text-[13px] text-brand-300">
                  Register to browse published job openings.
                </p>

                <form onSubmit={handleSubmit} className="mt-4 space-y-2.5">
                  {error ? (
                    <div className="border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
                      {error}
                    </div>
                  ) : null}

                  <div className="grid grid-cols-2 gap-2.5">
                    <div>
                      <label
                        htmlFor="talent-first-name"
                        className="mb-1 block text-[12px] font-semibold text-brand-900"
                      >
                        First name
                      </label>
                      <input
                        id="talent-first-name"
                        required
                        autoComplete="given-name"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        className={fieldClass}
                        placeholder="First name"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="talent-last-name"
                        className="mb-1 block text-[12px] font-semibold text-brand-900"
                      >
                        Last name
                      </label>
                      <input
                        id="talent-last-name"
                        required
                        autoComplete="family-name"
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                        className={fieldClass}
                        placeholder="Last name"
                      />
                    </div>
                  </div>

                  <div>
                    <label
                      htmlFor="talent-register-email"
                      className="mb-1 block text-[12px] font-semibold text-brand-900"
                    >
                      Email address
                    </label>
                    <div className="relative">
                      <Mail
                        className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-brand-300"
                        aria-hidden
                      />
                      <input
                        id="talent-register-email"
                        type="email"
                        required
                        autoComplete="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className={`${fieldClass} pl-10`}
                        placeholder="name@email.com"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <label
                        htmlFor="talent-register-password"
                        className="block text-[12px] font-semibold text-brand-900"
                      >
                        Password
                      </label>
                      <span className="text-[10px] text-brand-300">
                        Min. 8 characters
                      </span>
                    </div>
                    <div className="relative">
                      <Lock
                        className="pointer-events-none absolute left-3 top-1/2 z-10 h-3.5 w-3.5 -translate-y-1/2 text-brand-300"
                        aria-hidden
                      />
                      <PasswordInput
                        id="talent-register-password"
                        required
                        minLength={8}
                        autoComplete="new-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Create a password"
                        className={passwordClass}
                      />
                    </div>
                  </div>

                  <div>
                    <label
                      htmlFor="talent-confirm-password"
                      className="mb-1 block text-[12px] font-semibold text-brand-900"
                    >
                      Confirm password
                    </label>
                    <div className="relative">
                      <Lock
                        className="pointer-events-none absolute left-3 top-1/2 z-10 h-3.5 w-3.5 -translate-y-1/2 text-brand-300"
                        aria-hidden
                      />
                      <PasswordInput
                        id="talent-confirm-password"
                        required
                        minLength={8}
                        autoComplete="new-password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="Confirm your password"
                        className={passwordClass}
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="mt-0.5 inline-flex w-full items-center justify-center gap-2 bg-brand-600 px-4 py-2.5 text-[12px] font-semibold uppercase tracking-[0.08em] text-white transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500/35 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {submitting ? "Creating account..." : "Create account"}
                    {!submitting ? (
                      <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                    ) : null}
                  </button>
                </form>

                <p className="mt-3.5 text-[13px] text-brand-300">
                  Already have an account?{" "}
                  <Link
                    href={loginHref}
                    className="font-semibold text-brand-600 underline-offset-4 hover:text-brand-700 hover:underline"
                  >
                    Sign in
                  </Link>
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-dvh items-center justify-center bg-[#f4f6f8]">
          <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-brand-600" />
        </div>
      }
    >
      <RegisterForm />
    </Suspense>
  );
}
