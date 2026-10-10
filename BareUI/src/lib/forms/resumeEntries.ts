export type ResumeEntryField = {
  name: string
  label: string
  multiline?: boolean
  list?: boolean
}

export type ResumeEntrySection = 'experience' | 'education' | 'projects' | 'certifications'

export const resumeEntryFields: Record<ResumeEntrySection, ResumeEntryField[]> = {
  experience: [
    { name: 'title', label: 'Role' },
    { name: 'company', label: 'Company' },
    { name: 'location', label: 'Location' },
    { name: 'start', label: 'Start date' },
    { name: 'end', label: 'End date' },
    { name: 'highlights', label: 'Highlights, one per line', multiline: true, list: true },
  ],
  education: [
    { name: 'institution', label: 'School or institution' },
    { name: 'degree', label: 'Degree' },
    { name: 'major', label: 'Major or field of study' },
    { name: 'start', label: 'Start date' },
    { name: 'end', label: 'End date' },
  ],
  projects: [
    { name: 'name', label: 'Project name' },
    { name: 'tech', label: 'Technologies, one per line', multiline: true, list: true },
    { name: 'highlights', label: 'Highlights, one per line', multiline: true, list: true },
  ],
  certifications: [
    { name: 'name', label: 'Certification' },
    { name: 'issuer', label: 'Issuing organization' },
    { name: 'score', label: 'Score or credential ID' },
  ],
} satisfies Record<string, ResumeEntryField[]>