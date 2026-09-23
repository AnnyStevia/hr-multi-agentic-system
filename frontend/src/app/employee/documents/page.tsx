"use client";

import { DocumentsWorkspace } from "@/components/DocumentsWorkspace";

export default function EmployeeDocumentsPage() {
  return (
    <div className="max-w-5xl mx-auto space-y-6 px-4 py-6 sm:px-6">
      <div>
        <h1 className="text-2xl font-bold text-brand-900">Documents</h1>
        <p className="mt-1 text-sm text-brand-300">
          Browse company resources and manage your private files.
        </p>
      </div>
      <DocumentsWorkspace canManageLibrary={false} />
    </div>
  );
}
