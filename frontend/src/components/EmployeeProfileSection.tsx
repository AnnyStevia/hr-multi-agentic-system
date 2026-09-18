"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { ApplicationSection } from "@/components/ApplicationSection";
import { api } from "@/lib/api";
import type {
  EducationPayload,
  EmployeeEducation,
  EmployeeExperience,
  EmployeeProfile,
  ExperiencePayload,
} from "@/types/profile";

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

type EmployeeProfileSectionProps = {
  mode: "employee" | "hr";
  employeeId?: number;
};

function emptyEducation(): EducationPayload {
  return {
    institution: "",
    degree: "",
    field_of_study: "",
    start_date: "",
    end_date: "",
    description: "",
  };
}

function emptyExperience(): ExperiencePayload {
  return {
    company: "",
    position: "",
    description: "",
    start_date: "",
    end_date: "",
  };
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return value;
}

export function EmployeeProfileSection({ mode, employeeId }: EmployeeProfileSectionProps) {
  const editable = mode === "employee";
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);
  const [educations, setEducations] = useState<EmployeeEducation[]>([]);
  const [experiences, setExperiences] = useState<EmployeeExperience[]>([]);
  const [pictureUrl, setPictureUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const [phone, setPhone] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");

  const [eduForm, setEduForm] = useState<EducationPayload>(emptyEducation());
  const [editingEduId, setEditingEduId] = useState<number | null>(null);
  const [expForm, setExpForm] = useState<ExperiencePayload>(emptyExperience());
  const [editingExpId, setEditingExpId] = useState<number | null>(null);

  const loadPicture = useCallback(
    async (hasPicture: boolean) => {
      if (!hasPicture) {
        setPictureUrl(null);
        return;
      }
      try {
        const result =
          mode === "employee"
            ? await api.getMyProfilePictureUrl()
            : await api.getEmployeeProfilePictureUrl(employeeId as number);
        setPictureUrl(result.url);
      } catch {
        setPictureUrl(null);
      }
    },
    [mode, employeeId],
  );

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      if (mode === "employee") {
        const [profileData, eduData, expData] = await Promise.all([
          api.getMyProfile(),
          api.listMyEducation(),
          api.listMyExperience(),
        ]);
        setProfile(profileData);
        setEducations(eduData);
        setExperiences(expData);
        setPhone(profileData.phone);
        setDateOfBirth(profileData.date_of_birth || "");
        setAddress(profileData.address || "");
        setCity(profileData.city || "");
        setCountry(profileData.country || "");
        await loadPicture(profileData.has_profile_picture);
      } else {
        if (!employeeId) {
          setProfile(null);
          return;
        }
        const [profileData, eduData, expData] = await Promise.all([
          api.getEmployeeProfile(employeeId),
          api.listEmployeeEducation(employeeId),
          api.listEmployeeExperience(employeeId),
        ]);
        setProfile(profileData);
        setEducations(eduData);
        setExperiences(expData);
        setPhone(profileData.phone);
        setDateOfBirth(profileData.date_of_birth || "");
        setAddress(profileData.address || "");
        setCity(profileData.city || "");
        setCountry(profileData.country || "");
        await loadPicture(profileData.has_profile_picture);
      }
    } catch (err) {
      setProfile(null);
      setEducations([]);
      setExperiences([]);
      setError(err instanceof Error ? err.message : "Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, [mode, employeeId, loadPicture]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSavePersonal = async (event: FormEvent) => {
    event.preventDefault();
    if (!editable) return;
    setSaving(true);
    setError("");
    try {
      const updated = await api.updateMyProfile({
        phone: phone.trim(),
        date_of_birth: dateOfBirth || null,
        address: address.trim() || null,
        city: city.trim() || null,
        country: country.trim() || null,
      });
      setProfile(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  const handleUploadPicture = async (file: File | null) => {
    if (!editable || !file) return;
    setUploading(true);
    setError("");
    try {
      const updated = await api.uploadMyProfilePicture(file);
      setProfile(updated);
      await loadPicture(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload picture");
    } finally {
      setUploading(false);
    }
  };

  const handleDeletePicture = async () => {
    if (!editable) return;
    setUploading(true);
    setError("");
    try {
      await api.deleteMyProfilePicture();
      setProfile((current) =>
        current
          ? {
              ...current,
              has_profile_picture: false,
              profile_picture_filename: null,
              profile_picture_content_type: null,
            }
          : current,
      );
      setPictureUrl(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove picture");
    } finally {
      setUploading(false);
    }
  };

  const handleSaveEducation = async (event: FormEvent) => {
    event.preventDefault();
    if (!editable) return;
    setSaving(true);
    setError("");
    try {
      const payload: EducationPayload = {
        institution: eduForm.institution.trim(),
        degree: eduForm.degree.trim(),
        field_of_study: eduForm.field_of_study.trim(),
        start_date: eduForm.start_date,
        end_date: eduForm.end_date || null,
        description: eduForm.description?.trim() || null,
      };
      if (editingEduId) {
        await api.updateMyEducation(editingEduId, payload);
      } else {
        await api.createMyEducation(payload);
      }
      setEduForm(emptyEducation());
      setEditingEduId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save education");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveExperience = async (event: FormEvent) => {
    event.preventDefault();
    if (!editable) return;
    setSaving(true);
    setError("");
    try {
      const payload: ExperiencePayload = {
        company: expForm.company.trim(),
        position: expForm.position.trim(),
        start_date: expForm.start_date,
        end_date: expForm.end_date || null,
        description: expForm.description?.trim() || null,
      };
      if (editingExpId) {
        await api.updateMyExperience(editingExpId, payload);
      } else {
        await api.createMyExperience(payload);
      }
      setExpForm(emptyExperience());
      setEditingExpId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save experience");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="py-8 flex justify-center">
        <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
        {error || "Profile not found"}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <ApplicationSection title="Personal information">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm mb-4">
          <div>
            <p className="text-xs text-gray-500">Full name</p>
            <p className="mt-0.5 text-gray-900">{profile.full_name}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Email</p>
            <p className="mt-0.5 text-gray-900">{profile.email}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Department</p>
            <p className="mt-0.5 text-gray-900">{profile.department}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Position</p>
            <p className="mt-0.5 text-gray-900">{profile.position}</p>
          </div>
        </div>

        {editable ? (
          <form onSubmit={handleSavePersonal} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Phone</label>
                <input className={inputClass} value={phone} onChange={(e) => setPhone(e.target.value)} required />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Date of birth</label>
                <input
                  type="date"
                  className={inputClass}
                  value={dateOfBirth}
                  onChange={(e) => setDateOfBirth(e.target.value)}
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs text-gray-500 mb-1">Address</label>
                <input className={inputClass} value={address} onChange={(e) => setAddress(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">City</label>
                <input className={inputClass} value={city} onChange={(e) => setCity(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Country</label>
                <input className={inputClass} value={country} onChange={(e) => setCountry(e.target.value)} />
              </div>
            </div>
            <button
              type="submit"
              disabled={saving}
              className="bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save personal information"}
            </button>
          </form>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-500">Phone</p>
              <p className="mt-0.5 text-gray-900">{profile.phone}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Date of birth</p>
              <p className="mt-0.5 text-gray-900">{formatDate(profile.date_of_birth)}</p>
            </div>
            <div className="sm:col-span-2">
              <p className="text-xs text-gray-500">Address</p>
              <p className="mt-0.5 text-gray-900">{profile.address || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">City</p>
              <p className="mt-0.5 text-gray-900">{profile.city || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Country</p>
              <p className="mt-0.5 text-gray-900">{profile.country || "—"}</p>
            </div>
          </div>
        )}
      </ApplicationSection>

      <ApplicationSection title="Profile picture">
        <div className="flex flex-wrap items-start gap-4">
          {pictureUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={pictureUrl}
              alt="Profile"
              className="h-24 w-24 rounded-full object-cover border border-gray-200"
            />
          ) : (
            <div className="h-24 w-24 rounded-full bg-gray-100 border border-gray-200 flex items-center justify-center text-xs text-gray-500">
              No photo
            </div>
          )}
          {editable && (
            <div className="space-y-2">
              <input
                type="file"
                accept="image/jpeg,image/png,.jpg,.jpeg,.png"
                disabled={uploading}
                onChange={(e) => handleUploadPicture(e.target.files?.[0] || null)}
              />
              {profile.has_profile_picture && (
                <button
                  type="button"
                  disabled={uploading}
                  onClick={handleDeletePicture}
                  className="block text-sm text-red-600 hover:text-red-700 disabled:opacity-50"
                >
                  {uploading ? "Working..." : "Remove picture"}
                </button>
              )}
            </div>
          )}
        </div>
      </ApplicationSection>

      <ApplicationSection title="Education">
        {educations.length === 0 ? (
          <p className="text-sm text-gray-500 mb-4">No education records yet.</p>
        ) : (
          <ul className="space-y-3 mb-4">
            {educations.map((item) => (
              <li key={item.id} className="border border-gray-200 rounded-lg p-3 text-sm">
                <p className="font-medium text-gray-900">
                  {item.degree} — {item.institution}
                </p>
                <p className="text-gray-600">{item.field_of_study}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {item.start_date} → {item.end_date || "Present"}
                </p>
                {item.description && <p className="mt-1 text-gray-600">{item.description}</p>}
                {editable && (
                  <div className="mt-2 flex gap-3">
                    <button
                      type="button"
                      className="text-xs text-brand-700"
                      onClick={() => {
                        setEditingEduId(item.id);
                        setEduForm({
                          institution: item.institution,
                          degree: item.degree,
                          field_of_study: item.field_of_study,
                          start_date: item.start_date,
                          end_date: item.end_date || "",
                          description: item.description || "",
                        });
                      }}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="text-xs text-red-600"
                      onClick={async () => {
                        if (!window.confirm("Delete this education record?")) return;
                        try {
                          await api.deleteMyEducation(item.id);
                          await load();
                        } catch (err) {
                          setError(err instanceof Error ? err.message : "Failed to delete education");
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        {editable && (
          <form onSubmit={handleSaveEducation} className="space-y-3 border-t pt-4">
            <h3 className="text-sm font-medium text-gray-900">
              {editingEduId ? "Edit education" : "Add education"}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                className={inputClass}
                placeholder="Institution"
                required
                value={eduForm.institution}
                onChange={(e) => setEduForm({ ...eduForm, institution: e.target.value })}
              />
              <input
                className={inputClass}
                placeholder="Degree"
                required
                value={eduForm.degree}
                onChange={(e) => setEduForm({ ...eduForm, degree: e.target.value })}
              />
              <input
                className={inputClass}
                placeholder="Field of study"
                required
                value={eduForm.field_of_study}
                onChange={(e) => setEduForm({ ...eduForm, field_of_study: e.target.value })}
              />
              <input
                type="date"
                className={inputClass}
                required
                value={eduForm.start_date}
                onChange={(e) => setEduForm({ ...eduForm, start_date: e.target.value })}
              />
              <input
                type="date"
                className={inputClass}
                value={eduForm.end_date || ""}
                onChange={(e) => setEduForm({ ...eduForm, end_date: e.target.value })}
              />
              <input
                className={inputClass}
                placeholder="Description (optional)"
                value={eduForm.description || ""}
                onChange={(e) => setEduForm({ ...eduForm, description: e.target.value })}
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={saving}
                className="bg-brand-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
              >
                {editingEduId ? "Update" : "Add"} education
              </button>
              {editingEduId && (
                <button
                  type="button"
                  className="text-sm text-gray-600"
                  onClick={() => {
                    setEditingEduId(null);
                    setEduForm(emptyEducation());
                  }}
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        )}
      </ApplicationSection>

      <ApplicationSection title="Experience">
        {experiences.length === 0 ? (
          <p className="text-sm text-gray-500 mb-4">No experience records yet.</p>
        ) : (
          <ul className="space-y-3 mb-4">
            {experiences.map((item) => (
              <li key={item.id} className="border border-gray-200 rounded-lg p-3 text-sm">
                <p className="font-medium text-gray-900">
                  {item.position} — {item.company}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {item.start_date} → {item.end_date || "Present"}
                </p>
                {item.description && <p className="mt-1 text-gray-600">{item.description}</p>}
                {editable && (
                  <div className="mt-2 flex gap-3">
                    <button
                      type="button"
                      className="text-xs text-brand-700"
                      onClick={() => {
                        setEditingExpId(item.id);
                        setExpForm({
                          company: item.company,
                          position: item.position,
                          description: item.description || "",
                          start_date: item.start_date,
                          end_date: item.end_date || "",
                        });
                      }}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="text-xs text-red-600"
                      onClick={async () => {
                        if (!window.confirm("Delete this experience record?")) return;
                        try {
                          await api.deleteMyExperience(item.id);
                          await load();
                        } catch (err) {
                          setError(err instanceof Error ? err.message : "Failed to delete experience");
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        {editable && (
          <form onSubmit={handleSaveExperience} className="space-y-3 border-t pt-4">
            <h3 className="text-sm font-medium text-gray-900">
              {editingExpId ? "Edit experience" : "Add experience"}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                className={inputClass}
                placeholder="Company"
                required
                value={expForm.company}
                onChange={(e) => setExpForm({ ...expForm, company: e.target.value })}
              />
              <input
                className={inputClass}
                placeholder="Position"
                required
                value={expForm.position}
                onChange={(e) => setExpForm({ ...expForm, position: e.target.value })}
              />
              <input
                type="date"
                className={inputClass}
                required
                value={expForm.start_date}
                onChange={(e) => setExpForm({ ...expForm, start_date: e.target.value })}
              />
              <input
                type="date"
                className={inputClass}
                value={expForm.end_date || ""}
                onChange={(e) => setExpForm({ ...expForm, end_date: e.target.value })}
              />
              <input
                className={`${inputClass} sm:col-span-2`}
                placeholder="Description (optional)"
                value={expForm.description || ""}
                onChange={(e) => setExpForm({ ...expForm, description: e.target.value })}
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={saving}
                className="bg-brand-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
              >
                {editingExpId ? "Update" : "Add"} experience
              </button>
              {editingExpId && (
                <button
                  type="button"
                  className="text-sm text-gray-600"
                  onClick={() => {
                    setEditingExpId(null);
                    setExpForm(emptyExperience());
                  }}
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        )}
      </ApplicationSection>
    </div>
  );
}
