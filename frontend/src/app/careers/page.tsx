import Link from "next/link";

export default function CareersPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-2xl text-center">
        <p className="text-sm font-medium text-brand-700">Careers</p>
        <h1 className="mt-2 text-3xl font-bold text-gray-900">Build your next role with us</h1>
        <p className="mt-4 text-gray-600">
          Browse published openings after you create a candidate account or sign in.
          Applications open in a later release.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/careers/jobs"
            className="inline-flex justify-center bg-brand-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700"
          >
            View job openings
          </Link>
          <Link
            href="/careers/register"
            className="inline-flex justify-center border border-gray-300 bg-white text-gray-800 px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            Create an account
          </Link>
          <Link
            href="/login?next=%2Fcareers%2Fjobs"
            className="inline-flex justify-center border border-gray-300 bg-white text-gray-800 px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
