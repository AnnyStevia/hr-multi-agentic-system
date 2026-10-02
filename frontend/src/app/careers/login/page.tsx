"use client";

import { FormEvent, Suspense, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Manrope } from "next/font/google";
import { useSearchParams } from "next/navigation";
import { ArrowRight, Lock, Mail } from "lucide-react";
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

function TalentLoginForm() {
  const { login, loading: authLoading, user } = useAuth();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/careers/jobs";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
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
    setInfo("");
    setSubmitting(true);
    try {
      await login(email, password, next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  const registerHref = `/careers/register?next=${encodeURIComponent(next)}`;

  return (
    <div className={`${manrope.className} h-dvh overflow-hidden bg-[#f4f6f8]`}>
      <div className="flex h-full w-full flex-col lg:flex-row">
        {/* Corporate hero */}
        <section className="relative hidden h-full overflow-hidden lg:block lg:w-[52%]">
          <div className="absolute inset-0 animate-dash-fade-in">
            <Image
              src="/images/careers/pexels-tima-miroshnichenko-5439375.jpg"
              alt="Professional interview in a corporate office"
              fill
              className="object-cover object-[center_30%]"
              sizes="52vw"
              priority
            />
          </div>

          {/* Structured overlays — navy authority, emerald accent */}
          <div
            className="absolute inset-0 bg-[#0f224a]/55"
            aria-hidden="true"
          />
          <div
            className="absolute inset-0 bg-gradient-to-t from-[#0f224a] via-[#0f224a]/45 to-[#0f224a]/25"
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

          <div className="relative z-10 flex h-full flex-col px-11 py-9 xl:px-14 xl:py-11">
            <div className="animate-dash-fade-in">
              <TalentMark tone="light" />
            </div>

            <div className="mt-auto max-w-xl pb-10 animate-dash-fade-up">
              <div className="mb-5 flex items-center gap-3">
                <span className="h-px w-10 bg-brand-500" />
                <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-white/65">
                  Enterprise careers
                </span>
              </div>
              <h1 className="text-[2.65rem] font-semibold leading-[1.12] tracking-[-0.02em] text-white xl:text-[3rem]">
                Advance your career
                <span className="mt-1 block font-light text-white/85">
                  with purpose and precision.
                </span>
              </h1>
              <p className="mt-5 max-w-md text-[15px] leading-relaxed text-white/70">
                Access open roles, manage your applications, and stay informed
                throughout the hiring process.
              </p>
            </div>
          </div>
        </section>

        {/* Sign-in panel */}
        <section className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden">
          <div
            className="pointer-events-none absolute inset-0"
            aria-hidden="true"
          >
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_50%_at_100%_0%,rgba(2,152,112,0.07),transparent_55%)]" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_50%_40%_at_0%_100%,rgba(15,34,74,0.05),transparent_50%)]" />
          </div>

          <div className="relative flex h-full flex-col px-5 py-6 sm:px-10 lg:px-14 lg:py-8">
            <div className="mb-auto flex items-center justify-between lg:hidden">
              <TalentMark />
            </div>

            <div className="flex flex-1 flex-col justify-center">
              <div className="mx-auto w-full max-w-[400px] animate-dash-fade-up">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-brand-300">
                  Candidate sign in
                </p>
                <h2 className="mt-2 text-[1.75rem] font-semibold tracking-tight text-brand-900">
                  Welcome back
                </h2>
                <p className="mt-1.5 text-sm leading-relaxed text-brand-300">
                  Sign in to continue your application journey.
                </p>

                <form onSubmit={handleSubmit} className="mt-7 space-y-4">
                  {error ? (
                    <div className="border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                      {error}
                    </div>
                  ) : null}
                  {info ? (
                    <div className="border border-brand-200 bg-[#f0f7f4] px-3.5 py-2.5 text-sm text-brand-800">
                      {info}
                    </div>
                  ) : null}

                  <div>
                    <label
                      htmlFor="talent-email"
                      className="mb-1.5 block text-[13px] font-semibold text-brand-900"
                    >
                      Work email
                    </label>
                    <div className="relative">
                      <Mail
                        className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-300"
                        aria-hidden
                      />
                      <input
                        id="talent-email"
                        type="email"
                        required
                        autoComplete="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full rounded-sm border border-brand-200 bg-white py-2.5 pl-11 pr-4 text-sm text-brand-900 outline-none transition placeholder:text-brand-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30"
                        placeholder="name@email.com"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="mb-1.5 flex items-center justify-between">
                      <label
                        htmlFor="talent-password"
                        className="block text-[13px] font-semibold text-brand-900"
                      >
                        Password
                      </label>
                      <button
                        type="button"
                        className="text-[12px] font-medium text-brand-600 hover:text-brand-700"
                        onClick={() =>
                          setInfo(
                            "Password reset is not available yet. Contact HR if you need help accessing your account."
                          )
                        }
                      >
                        Forgot password?
                      </button>
                    </div>
                    <div className="relative">
                      <Lock
                        className="pointer-events-none absolute left-3.5 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-brand-300"
                        aria-hidden
                      />
                      <PasswordInput
                        id="talent-password"
                        required
                        autoComplete="current-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Enter your password"
                        className="!rounded-sm border-brand-200 py-2.5 pl-11 text-sm text-brand-900 placeholder:text-brand-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="mt-1 inline-flex w-full items-center justify-center gap-2 bg-brand-600 px-4 py-3 text-[13px] font-semibold uppercase tracking-[0.08em] text-white transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500/35 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {submitting ? "Signing in..." : "Sign in"}
                    {!submitting ? (
                      <ArrowRight className="h-4 w-4" aria-hidden />
                    ) : null}
                  </button>
                </form>

                <div className="mt-8 border-t border-brand-200 pt-5">
                  <p className="text-sm text-brand-300">
                    New candidate?{" "}
                    <Link
                      href={registerHref}
                      className="font-semibold text-brand-600 underline-offset-4 hover:text-brand-700 hover:underline"
                    >
                      Create an account
                    </Link>
                  </p>
                </div>
              </div>
            </div>

            <p className="mt-auto hidden text-[11px] tracking-wide text-brand-300 lg:block">
              Secure candidate access · Confidential hiring process
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

export default function CareersLoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-dvh items-center justify-center bg-[#f4f6f8]">
          <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-brand-600" />
        </div>
      }
    >
      <TalentLoginForm />
    </Suspense>
  );
}
