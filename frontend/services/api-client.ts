import axios, { AxiosInstance, AxiosError } from 'axios';

// Keep browser requests on the same origin. Next.js proxies /api and /health
// to the private backend, so a public deployment only needs one endpoint.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

export interface SourceFile {
  id: string;
  name: string;
  extension: string;
  size_bytes: number;
  content_type: string;
}

export interface SourceCategory {
  id: string;
  name: string;
  file_count: number;
  files: SourceFile[];
}

export interface SourceLibrary {
  total_files: number;
  total_categories: number;
  categories: SourceCategory[];
}

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor to include auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const request = error.config as (typeof error.config & { _retry?: boolean });
        const refreshToken = localStorage.getItem('refresh_token');
        if (error.response?.status === 401 && request && !request._retry && refreshToken && !request.url?.includes('/api/auth/refresh') && !request.url?.includes('/api/auth/login')) {
          request._retry = true;
          try {
            const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, { refresh_token: refreshToken });
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
      }
    );
  }

  // Authentication endpoints
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

  // User endpoints
  async getCurrentUser() {
    const response = await this.client.get('/api/users/me');
    return response.data;
  }

  async updateProfile(data: any) {
    const response = await this.client.put('/api/users/me', data);
    return response.data;
  }

  // Course endpoints
  async getCourses() {
    const response = await this.client.get('/api/courses/');
    return response.data;
  }

  async getCourse(courseId: number) {
    const response = await this.client.get(`/api/courses/${courseId}`);
    return response.data;
  }

  async getLesson(lessonId: number) {
    const response = await this.client.get(`/api/learning/lessons/${lessonId}`);
    return response.data;
  }

  async markLessonComplete(lessonId: number) {
    const response = await this.client.post(`/api/learning/lessons/${lessonId}/mark-complete`);
    return response.data;
  }

  // Learning endpoints
  async getLessonProgress() {
    const response = await this.client.get('/api/learning/progress');
    return response.data;
  }

  async getProblems() {
    const response = await this.client.get('/api/learning/problems/');
    return response.data;
  }

  async submitProblem(problemId: number, data: any) {
    const response = await this.client.post(`/api/learning/problems/${problemId}/submit`, data);
    return response.data;
  }

  async getMastery() {
    const response = await this.client.get('/api/learning/mastery');
    return response.data;
  }

  // Gamification endpoints
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

  async getSources(): Promise<SourceLibrary> {
    const response = await this.client.get<SourceLibrary>('/api/sources');
    return response.data;
  }

  async downloadSource(sourceId: string, fileName: string): Promise<void> {
    const response = await this.client.get<Blob>(`/api/sources/${sourceId}`, {
      params: { download: true },
      responseType: 'blob',
    });
    const objectUrl = URL.createObjectURL(response.data);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }

  async getNextJourneyProblem(topicId?: number, unit?: number, excludeIds: number[] = []) {
    const response = await this.client.get('/api/journey/next', {
      params: topicId ? { topic_id: topicId, unit, exclude_ids: excludeIds.join(',') || undefined } : undefined,
    });
    return response.data;
  }

  async getAchievements() {
    const response = await this.client.get('/api/gamification/achievements');
    return response.data;
  }

  async getLeaderboard(period: string = 'weekly', category: string = 'overall') {
    const response = await this.client.get('/api/gamification/leaderboard', {
      params: { period, category },
    });
    return response.data;
  }

  async getXPHistory() {
    const response = await this.client.get('/api/gamification/xp-history');
    return response.data;
  }

  // Billing endpoints
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

  // Health check
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
