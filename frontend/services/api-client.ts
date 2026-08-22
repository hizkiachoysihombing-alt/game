import axios, { AxiosError, AxiosInstance } from 'axios';

// Browser traffic stays on the Next.js origin. The app proxy forwards /api and
// /health to the private FastAPI service.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

export type UserRole = 'student' | 'instructor' | 'admin';
export type SourceStatus = 'inbox' | 'review_pending' | 'published' | 'archived';
export type QuestionStatus =
  | 'draft'
  | 'pending_review'
  | 'rejected'
  | 'approved'
  | 'published'
  | 'archived';

export interface ApiUser {
  id: number;
  email: string;
  username: string;
  full_name: string;
  role: UserRole;
  avatar_url?: string | null;
  bio?: string | null;
  institution?: string | null;
  major?: string | null;
  semester?: number | null;
  created_at?: string;
}

export interface SubjectRef {
  id: number;
  name: string;
  slug?: string;
}

export interface TopicRef {
  id: number;
  name: string;
  slug?: string;
  parent_id?: number | null;
}

export interface CourseLesson {
  id: number;
  name: string;
  order: number;
  is_completed?: boolean;
}

export interface CourseModule {
  id: number;
  name: string;
  order: number;
  lessons: CourseLesson[];
}

export interface Course {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  thumbnail_url?: string | null;
  difficulty?: string | null;
  estimated_hours?: number | null;
  is_enrolled?: boolean;
  subject?: SubjectRef | null;
  modules: CourseModule[];
}

export interface Lesson {
  id: number;
  name: string;
  content_html: string;
  module_id: number;
  course?: { id: number; name: string } | null;
  progress: { is_completed: boolean };
  citations?: SourceCitation[];
}

export interface SourceVersion {
  id: number;
  version_number: number;
  page_count?: number | null;
  file_name?: string;
  extension?: string;
  content_type?: string;
  size_bytes?: number;
  created_at?: string;
}

export interface SourceDocument {
  id: string;
  legacy_id?: string | null;
  title: string;
  name: string;
  description?: string | null;
  extension: string;
  size_bytes: number;
  content_type: string;
  status: SourceStatus;
  subject?: SubjectRef | null;
  topics: TopicRef[];
  version: SourceVersion;
  is_bookmarked: boolean;
  reading_progress: number;
  last_page?: number | null;
  updated_at?: string | null;
  last_opened_at?: string | null;
}

// Compatibility alias for code written before source documents received stable
// public IDs and version metadata.
export type SourceFile = SourceDocument;

export interface SourceCategory {
  id: string;
  name: string;
  file_count: number;
  files: SourceDocument[];
}

export interface SourceLibrary {
  total_documents: number;
  total_files: number;
  total_categories: number;
  categories: SourceCategory[];
}

export interface SourceCitation {
  id?: number;
  source_id?: string;
  public_id?: string;
  version_id?: number | null;
  version?: number;
  source_title?: string;
  title?: string;
  subject?: string;
  topic?: string;
  page_start: number | null;
  page_end?: number | null;
  label?: string;
  section_label?: string | null;
  locator_text?: string | null;
  purpose?: string;
  href?: string;
}

export interface SourceManagementDashboard {
  sources: {
    inbox: number;
    review_pending: number;
    published: number;
    archived: number;
  };
  questions: Partial<Record<QuestionStatus, number>>;
  open_reports: number;
}

export interface SourceTaxonomy {
  subjects: Array<{ id: number; name: string; slug: string }>;
  topics: Array<{ id: number; subject_id: number; name: string; slug: string }>;
  courses: Array<{ id: number; subject_id: number; name: string }>;
}

export interface ManagedSource extends SourceDocument {
  created_at?: string;
  review_notes?: string | null;
  versions?: SourceVersion[];
}

export interface ManagedQuestion {
  id: number;
  title: string;
  content_html: string;
  solution_html?: string | null;
  explanation?: string | null;
  expected_answer?: string | null;
  numerical_tolerance?: number | null;
  accepted_units?: string[];
  bloom_level?: string | null;
  estimated_time_minutes?: number;
  xp_reward?: number | null;
  question_type: string;
  difficulty: string;
  workflow_status: QuestionStatus;
  status?: QuestionStatus;
  subject?: SubjectRef | null;
  topic?: TopicRef | null;
  citations: SourceCitation[];
  author?: { id: number; full_name: string } | null;
  reviewer?: { id: number; full_name: string } | null;
  review_notes?: string | null;
  updated_at?: string;
}

export interface QuestionCitationInput {
  source_version_id: number;
  page_start?: number | null;
  page_end?: number | null;
  section_label?: string | null;
  locator_text?: string | null;
  excerpt?: string | null;
  purpose?: 'prompt' | 'solution' | 'explanation';
}

export interface SourceQuery {
  q?: string;
  subject_id?: number;
  topic_id?: number;
  file_type?: string;
}

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    });

    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) config.headers.Authorization = `Bearer ${token}`;
        return config;
      },
      (error) => Promise.reject(error),
    );

    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const request = error.config as typeof error.config & { _retry?: boolean };
        const refreshToken = localStorage.getItem('refresh_token');
        const canRefresh =
          error.response?.status === 401 &&
          request &&
          !request._retry &&
          refreshToken &&
          !request.url?.includes('/api/auth/refresh') &&
          !request.url?.includes('/api/auth/login');

        if (canRefresh) {
          request._retry = true;
          try {
            const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
              refresh_token: refreshToken,
            });
            localStorage.setItem('access_token', response.data.access_token);
            localStorage.setItem('refresh_token', response.data.refresh_token);
            request.headers = request.headers || {};
            request.headers.Authorization = `Bearer ${response.data.access_token}`;
            return this.client.request(request);
          } catch {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
          }
        } else if (error.response?.status === 401) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      },
    );
  }

  async register(email: string, username: string, password: string, fullName: string) {
    const response = await this.client.post('/api/auth/register', {
      email,
      username,
      password,
      full_name: fullName,
    });
    return response.data;
  }

  async login(email: string, password: string) {
    const body = new URLSearchParams({ username: email, password });
    const response = await this.client.post('/api/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  }

  async refreshToken() {
    const refreshToken = localStorage.getItem('refresh_token');
    const response = await this.client.post('/api/auth/refresh', { refresh_token: refreshToken });
    return response.data;
  }

  async getCurrentUser(): Promise<ApiUser> {
    const response = await this.client.get<ApiUser>('/api/users/me');
    return response.data;
  }

  async updateProfile(data: Partial<ApiUser>): Promise<ApiUser> {
    const response = await this.client.put<ApiUser>('/api/users/me', data);
    return response.data;
  }

  async getCourses(): Promise<Course[]> {
    const response = await this.client.get<Course[]>('/api/courses/');
    return response.data;
  }

  async getCourse(courseId: number): Promise<Course> {
    const response = await this.client.get<Course>(`/api/courses/${courseId}`);
    return response.data;
  }

  async getLesson(lessonId: number): Promise<Lesson> {
    const response = await this.client.get<Lesson>(`/api/learning/lessons/${lessonId}`);
    return response.data;
  }

  async markLessonComplete(lessonId: number) {
    const response = await this.client.post(`/api/learning/lessons/${lessonId}/mark-complete`);
    return response.data;
  }

  async getLessonProgress() {
    const response = await this.client.get('/api/learning/progress');
    return response.data;
  }

  async getProblems() {
    const response = await this.client.get('/api/learning/problems/');
    return response.data;
  }

  async submitProblem(problemId: number, data: unknown) {
    const response = await this.client.post(`/api/learning/problems/${problemId}/submit`, data);
    return response.data;
  }

  async getMastery() {
    const response = await this.client.get('/api/learning/mastery');
    return response.data;
  }

  async getGamificationProfile() {
    const response = await this.client.get('/api/gamification/profile');
    return response.data;
  }

  async changePassword(currentPassword: string, newPassword: string) {
    const response = await this.client.put('/api/users/me/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  }

  async getStudentDashboard() {
    const response = await this.client.get('/api/dashboard/student');
    return response.data;
  }

  async getStreakDetails() {
    const response = await this.client.get('/api/dashboard/streak');
    return response.data;
  }

  async addStreakFriend(username: string) {
    const response = await this.client.post('/api/dashboard/streak/friends', { username });
    return response.data;
  }

  async getJourneyMap() {
    const response = await this.client.get('/api/journey/map');
    return response.data;
  }

  async getSources(params: SourceQuery = {}): Promise<SourceLibrary> {
    const response = await this.client.get<SourceLibrary>('/api/sources', { params });
    return response.data;
  }

  async getSource(sourceId: string): Promise<SourceDocument> {
    const response = await this.client.get<SourceDocument>(`/api/sources/${sourceId}`);
    return response.data;
  }

  async getSourceBookmarks(): Promise<unknown> {
    const response = await this.client.get('/api/sources/me/bookmarks');
    return response.data;
  }

  async getSourceHistory(): Promise<unknown> {
    const response = await this.client.get('/api/sources/me/history');
    return response.data;
  }

  async getSourceBlob(sourceId: string, versionId?: number): Promise<Blob> {
    const response = await this.client.get<Blob>(`/api/sources/${sourceId}/content`, {
      params: versionId ? { version_id: versionId } : undefined,
      responseType: 'blob',
      timeout: 120000,
    });
    return response.data;
  }

  async bookmarkSource(sourceId: string, page?: number) {
    const response = await this.client.put(`/api/sources/${sourceId}/bookmark`, {
      page: page ?? null,
    });
    return response.data;
  }

  async removeSourceBookmark(sourceId: string) {
    const response = await this.client.delete(`/api/sources/${sourceId}/bookmark`);
    return response.data;
  }

  async updateSourceProgress(sourceId: string, page: number, progressPercent: number) {
    const response = await this.client.put(`/api/sources/${sourceId}/progress`, {
      page,
      progress_percent: progressPercent,
    });
    return response.data;
  }

  async getSourceManagementDashboard(): Promise<SourceManagementDashboard> {
    const response = await this.client.get<SourceManagementDashboard>('/api/source-management/dashboard');
    return response.data;
  }

  async getSourceTaxonomy(): Promise<SourceTaxonomy> {
    const response = await this.client.get<SourceTaxonomy>('/api/source-management/taxonomy');
    return response.data;
  }

  async getManagedSources(params: { status?: SourceStatus; q?: string } = {}): Promise<unknown> {
    const response = await this.client.get('/api/source-management/', { params });
    return response.data;
  }

  async uploadManagedSource(payload: {
    file: File;
    title: string;
    description?: string;
    subjectId?: number;
    topicIds?: number[];
  }): Promise<{ document: ManagedSource; deduplicated: boolean }> {
    const body = new FormData();
    body.append('file', payload.file);
    body.append('title', payload.title);
    if (payload.description) body.append('description', payload.description);
    if (payload.subjectId) body.append('subject_id', String(payload.subjectId));
    if (payload.topicIds?.length) body.append('topic_ids', payload.topicIds.join(','));
    const response = await this.client.post<{ document: ManagedSource; deduplicated: boolean }>('/api/source-management/upload', body, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return response.data;
  }

  async updateManagedSource(sourceId: string, payload: Record<string, unknown>) {
    const response = await this.client.patch(`/api/source-management/${sourceId}`, payload);
    return response.data;
  }

  async addManagedSourceVersion(sourceId: string, file: File) {
    const body = new FormData();
    body.append('file', file);
    const response = await this.client.post(`/api/source-management/${sourceId}/version`, body, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return response.data;
  }

  async transitionManagedSource(sourceId: string, action: 'review' | 'publish' | 'archive') {
    const response = await this.client.post(`/api/source-management/${sourceId}/${action}`, { notes: null });
    return response.data;
  }

  async getManagedQuestions(params: { status?: QuestionStatus; q?: string } = {}): Promise<unknown> {
    const response = await this.client.get('/api/question-management/', {
      params: { workflow_status: params.status, q: params.q },
    });
    return response.data;
  }

  async createManagedQuestion(payload: Record<string, unknown>) {
    const response = await this.client.post<ManagedQuestion>('/api/question-management/', payload);
    return response.data;
  }

  async updateManagedQuestion(questionId: number, payload: Record<string, unknown>) {
    const response = await this.client.patch<ManagedQuestion>(`/api/question-management/${questionId}`, payload);
    return response.data;
  }

  async addQuestionCitation(questionId: number, payload: QuestionCitationInput): Promise<SourceCitation> {
    const response = await this.client.post<SourceCitation>(`/api/question-management/${questionId}/citations`, payload);
    return response.data;
  }

  async deleteQuestionCitation(questionId: number, citationId: number) {
    await this.client.delete(`/api/question-management/${questionId}/citations/${citationId}`);
  }

  async generateManagedQuestions(payload: Record<string, unknown>) {
    const response = await this.client.post('/api/question-management/generate', payload);
    return response.data;
  }

  async submitQuestionReview(questionId: number) {
    const response = await this.client.post(`/api/question-management/${questionId}/submit-review`);
    return response.data;
  }

  async reviewManagedQuestion(questionId: number, action: 'approve' | 'reject', notes: string) {
    const response = await this.client.post(`/api/question-management/${questionId}/review`, {
      action,
      notes,
    });
    return response.data;
  }

  async transitionManagedQuestion(questionId: number, action: 'publish' | 'archive') {
    const response = await this.client.post(`/api/question-management/${questionId}/${action}`);
    return response.data;
  }

  async getNextJourneyProblem(topicId?: number, unit?: number, excludeIds: number[] = []) {
    const response = await this.client.get('/api/journey/next', {
      params: topicId
        ? { topic_id: topicId, unit, exclude_ids: excludeIds.join(',') || undefined }
        : undefined,
    });
    return response.data;
  }

  async getAchievements() {
    const response = await this.client.get('/api/gamification/achievements');
    return response.data;
  }

  async getLeaderboard(period = 'weekly', category = 'overall') {
    const response = await this.client.get('/api/gamification/leaderboard', {
      params: { period, category },
    });
    return response.data;
  }

  async getXPHistory() {
    const response = await this.client.get('/api/gamification/xp-history');
    return response.data;
  }

  async getSubscriptionPlans() {
    const response = await this.client.get('/api/billing/plans');
    return response.data;
  }

  async getSubscription() {
    const response = await this.client.get('/api/billing/subscription');
    return response.data;
  }

  async getUsage() {
    const response = await this.client.get('/api/billing/usage');
    return response.data;
  }

  async createCheckout(planCode: string) {
    const response = await this.client.post('/billing/checkout', { plan_code: planCode });
    return response.data;
  }

  async cancelSubscription() {
    const response = await this.client.post('/billing/cancel');
    return response.data;
  }

  async getInvoices() {
    const response = await this.client.get('/billing/invoices');
    return response.data;
  }

  async healthCheck() {
    try {
      const response = await this.client.get('/health');
      return response.status === 200;
    } catch {
      return false;
    }
  }
}

export const apiClient = new APIClient();
