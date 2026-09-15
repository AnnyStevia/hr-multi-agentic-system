import type { ReactNode } from "react";

export function ApplicationSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="bg-white rounded-xl border shadow-sm p-6 space-y-3">
      <h2 className="text-sm font-medium text-gray-500">{title}</h2>
      {children}
    </section>
  );
}
