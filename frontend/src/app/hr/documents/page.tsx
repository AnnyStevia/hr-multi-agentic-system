"use client";

import { DocumentsWorkspace } from "@/components/DocumentsWorkspace";

export default function HrDocumentsPage() {
  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-brand-900">Documents</h1>
        <p className="mt-1 text-sm text-brand-300">
          Manage the company library and your own private files.
        </p>
      </div>
      <DocumentsWorkspace canManageLibrary />
    </div>
  );
}
