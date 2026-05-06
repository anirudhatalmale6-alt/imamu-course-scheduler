import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || '';

const api = axios.create({
  baseURL: API_BASE,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  register: (data) => api.post('/api/auth/register', data),
  login: (data) => api.post('/api/auth/login', data),
  getMe: () => api.get('/api/auth/me'),
};

export const courseAPI = {
  list: (params) => api.get('/api/courses', { params }),
  get: (id) => api.get(`/api/courses/${id}`),
  create: (data) => api.post('/api/courses', data),
  update: (id, data) => api.put(`/api/courses/${id}`, data),
  delete: (id) => api.delete(`/api/courses/${id}`),
};

export const sectionAPI = {
  list: (params) => api.get('/api/sections', { params }),
  create: (data) => api.post('/api/sections', data),
};

export const registrationAPI = {
  register: (sectionId) => api.post(`/api/registration/register/${sectionId}`),
  unregister: (sectionId) => api.delete(`/api/registration/unregister/${sectionId}`),
  myRegistrations: () => api.get('/api/registration/my-registrations'),
  getCompleted: () => api.get('/api/registration/completed'),
  markCompleted: (courseId) => api.post(`/api/registration/complete/${courseId}`),
  unmarkCompleted: (courseId) => api.delete(`/api/registration/uncomplete/${courseId}`),
};

export const scheduleAPI = {
  generate: (data) => api.post('/api/schedule/generate', data),
  save: (data) => api.post('/api/schedule/save', data),
  getSaved: () => api.get('/api/schedule/saved'),
  deleteSaved: (id) => api.delete(`/api/schedule/saved/${id}`),
};

export const dataAPI = {
  departments: () => api.get('/api/departments'),
  instructors: () => api.get('/api/instructors'),
  rooms: () => api.get('/api/rooms'),
  days: () => api.get('/api/days'),
  timeslots: () => api.get('/api/timeslots'),
};

export default api;
