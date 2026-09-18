export type EmployeeProfile = {
  employee_id: number;
  employee_number: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  department_id: number;
  department: string;
  position: string;
  hire_date: string;
  date_of_birth: string | null;
  address: string | null;
  city: string | null;
  country: string | null;
  has_profile_picture: boolean;
  profile_picture_filename: string | null;
  profile_picture_content_type: string | null;
};

export type ProfileUpdatePayload = {
  phone?: string;
  date_of_birth?: string | null;
  address?: string | null;
  city?: string | null;
  country?: string | null;
};

export type PresignedProfilePictureUrl = {
  url: string;
  filename: string;
  content_type: string;
  expires_in: number;
};

export type EmployeeEducation = {
  id: number;
  employee_id: number;
  institution: string;
  degree: string;
  field_of_study: string;
  start_date: string;
  end_date: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type EducationPayload = {
  institution: string;
  degree: string;
  field_of_study: string;
  start_date: string;
  end_date?: string | null;
  description?: string | null;
};

export type EmployeeExperience = {
  id: number;
  employee_id: number;
  company: string;
  position: string;
  description: string | null;
  start_date: string;
  end_date: string | null;
  created_at: string;
  updated_at: string;
};

export type ExperiencePayload = {
  company: string;
  position: string;
  description?: string | null;
  start_date: string;
  end_date?: string | null;
};
