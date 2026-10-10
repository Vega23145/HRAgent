import {
  Activity, BriefcaseBusiness, ClipboardList, FileText, LayoutDashboard,
  Mail, ShieldCheck, Users,
} from '@lucide/svelte'
import type { ResourceDefinition } from './types'

export const resources: ResourceDefinition[] = [
  {
    id: 'resumes', label: 'Resumes', noun: 'resume', endpoint: '/api/v1/resumes', create: 'resume',
    columns: [
      { label: 'Candidate', path: 'resume.name', alternatives: ['name', 'candidate_name'] },
      { label: 'Email', path: 'email.sender', alternatives: ['contact.emails', 'email'] },
      { label: 'Skills', path: 'resume.skills', alternatives: ['skills'] },
      { label: 'Experience', path: 'resume.experience', alternatives: ['experience'] },
      { label: 'Education', path: 'resume.education', alternatives: ['education'] },
      { label: 'Match', path: 'match', alternatives: ['score'] },
    ],
    filters: [
      { name: 'skill', label: 'Skill' }, { name: 'role', label: 'Role' },
      { name: 'status', label: 'Status', type: 'select', options: ['rejected'] },
      { name: 'min_score', label: 'Min score', type: 'number' },
      { name: 'has_match', label: 'Match', type: 'select', options: ['true', 'false'] },
      { name: 'sort', label: 'Sort', type: 'select', options: ['_id', 'name', '-name', 'score', '-score'] },
    ],
  },
  {
    id: 'roles', label: 'Job roles', noun: 'role', endpoint: '/api/v1/job-roles', create: 'role',
    columns: [
      { label: 'Title', path: 'title', alternatives: ['role.title'] }, { label: 'Department', path: 'department' },
      { label: 'Employment', path: 'employment_type' }, { label: 'Work mode', path: 'work_mode' },
      { label: 'Experience', path: 'experience_level' }, { label: 'Required skills', path: 'required_skills' },
      { label: 'Responsibilities', path: 'responsibilities' }, { label: 'Nice to have', path: 'nice_to_have' },
    ],
    filters: [
      { name: 'department', label: 'Department' }, { name: 'experience_level', label: 'Experience' },
    ],
  },
  {
    id: 'tasks', label: 'Tasks', noun: 'task', endpoint: '/api/v1/task-review/tasks', create: 'task',
    columns: [
      { label: 'Title', path: 'title' }, { label: 'Role', path: 'role_id' },
      { label: 'Description', path: 'description' }, { label: 'Instructions', path: 'instructions' },
      { label: 'Deadline', path: 'deadline' }, { label: 'Open', path: 'is_open' },
    ],
    filters: [
      { name: 'role_id', label: 'Role ID' }, { name: 'is_open', label: 'Open', type: 'select', options: ['true', 'false'] },
    ],
  },
  {
    id: 'submissions', label: 'Submissions', noun: 'submission', endpoint: '/api/v1/task-review/candidates', create: 'submission',
    columns: [
      { label: 'Candidate', path: 'candidate_name' }, { label: 'Email', path: 'candidate_email' },
      { label: 'Task', path: 'task_id' }, { label: 'Status', path: 'status' },
      { label: 'Score', path: 'score' }, { label: 'Submitted', path: 'created_at' },
    ],
    filters: [
      { name: 'candidate_id', label: 'Candidate ID' },
      { name: 'status', label: 'Status', type: 'select', options: ['pending', 'under_review', 'accepted', 'rejected'] },
    ],
  },
  {
    id: 'email-jobs', label: 'Email jobs', noun: 'email job', endpoint: '/api/v1/email-agent/jobs',
    columns: [
      { label: 'Action', path: 'action' }, { label: 'Subject', path: 'subject' },
      { label: 'Status', path: 'status' }, { label: 'Recipients', path: 'recipient_count' },
      { label: 'Created', path: 'created_at' }, { label: 'Completed', path: 'completed_at' },
    ],
    filters: [
      { name: 'status', label: 'Status' }, { name: 'action', label: 'Action', type: 'select', options: ['interview', 'task_assigned', 'rejected', 'hired', 'custom'] },
    ],
  },
  {
    id: 'users', label: 'Users', noun: 'user', endpoint: '/api/v1/users', create: 'user',
    columns: [
      { label: 'Name', path: 'full_name', alternatives: ['user.full_name'] }, { label: 'Email', path: 'email', alternatives: ['user.email'] },
      { label: 'Active', path: 'is_active', alternatives: ['user.is_active'] },
      { label: 'Roles', path: 'roles', alternatives: ['user.roles'] },
      { label: 'Grants', path: 'grants', alternatives: ['effective_permissions', 'user.grants'] },
      { label: 'Denies', path: 'denies', alternatives: ['user.denies'] },
    ],
    filters: [
      { name: 'role', label: 'Role' }, { name: 'is_active', label: 'Active', type: 'select', options: ['true', 'false'] },
    ],
  },
  {
    id: 'access-roles', label: 'Access roles', noun: 'access role', endpoint: '/api/v1/access-roles',
    columns: [
      { label: 'Name', path: '_id' }, { label: 'Description', path: 'description' },
      { label: 'Permissions', path: 'permissions' },
    ],
  },
  {
    id: 'audit', label: 'Audit log', noun: 'audit entry', endpoint: '/api/v1/admin/audit',
    columns: [
      { label: 'Action', path: 'action' }, { label: 'Actor', path: 'actor_email' },
      { label: 'Resource', path: 'resource' }, { label: 'Timestamp', path: 'created_at' },
      { label: 'Details', path: 'details' },
    ],
    filters: [
      { name: 'actor_email', label: 'Actor email' }, { name: 'action', label: 'Action' },
    ],
  },
  {
    id: 'permissions', label: 'Permissions', noun: 'permission', endpoint: '/api/v1/permissions',
    columns: [
      { label: 'Permission', path: 'name' }, { label: 'Description', path: 'description' },
      { label: 'Resource', path: 'resource' }, { label: 'Action', path: 'action' },
    ],
  },
  {
    id: 'email-templates', label: 'Email templates', noun: 'email template', endpoint: '/api/v1/email-agent/templates',
    columns: [
      { label: 'Action', path: 'action' }, { label: 'Subject', path: 'subject' },
      { label: 'Description', path: 'description' }, { label: 'Template', path: 'body' },
    ],
  },
]

export const navigation = [
  { label: 'Overview', icon: LayoutDashboard, resourceId: null },
  { label: 'Resumes', icon: FileText, resourceId: 'resumes' },
  { label: 'Job roles', icon: BriefcaseBusiness, resourceId: 'roles' },
  { label: 'Matching', icon: Activity, resourceId: 'matching' },
  { label: 'Tasks', icon: ClipboardList, resourceId: 'tasks' },
  { label: 'Submissions', icon: ClipboardList, resourceId: 'submissions' },
  { label: 'Email agent', icon: Mail, resourceId: 'email-agent' },
  { label: 'Users', icon: Users, resourceId: 'users' },
  { label: 'Access roles', icon: ShieldCheck, resourceId: 'access-roles' },
  { label: 'Audit log', icon: ShieldCheck, resourceId: 'audit' },
  { label: 'Permissions', icon: ShieldCheck, resourceId: 'permissions' },
] as const