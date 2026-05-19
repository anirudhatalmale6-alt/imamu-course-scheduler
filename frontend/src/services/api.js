/**
 * api.js - Axios HTTP Client & API Service Layer
 *
 * This file configures a centralized Axios instance for communicating with
 * the FastAPI backend. It handles:
 *   1. Base URL configuration (from environment variable or same-origin)
 *   2. Automatic JWT token injection into every request header
 *   3. Global 401 (Unauthorized) error handling - auto-logout on expired tokens
 *   4. Organized API endpoint functions grouped by resource type
 *
 * All API calls throughout the app import from this file, ensuring consistent
 * headers, error handling, and base URL usage.
 */

import axios from 'axios';

// Read the API base URL from environment variables; fall back to same-origin ('')
const API_BASE = process.env.REACT_APP_API_URL || '';

// Create a reusable Axios instance with the base URL pre-configured
const api = axios.create({
  baseURL: API_BASE,
});

/**
 * Request Interceptor - Runs before every outgoing HTTP request.
 * It reads the JWT token from localStorage and attaches it as a
 * Bearer token in the Authorization header. This way, protected
 * backend endpoints can verify the user's identity.
 */
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Response Interceptor - Runs after every HTTP response is received.
 * On success: passes the response through unchanged.
 * On 401 error: the token has expired or is invalid, so we clear
 * the stored credentials and redirect the user to the login page.
 * All other errors are re-thrown so individual components can handle them.
 */
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - force logout and redirect
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

/**
 * authAPI - Authentication endpoints (register, login, get current user).
 */
export const authAPI = {
  register: (data) => api.post('/api/auth/register', data),  // Create a new user account
  login: (data) => api.post('/api/auth/login', data),          // Authenticate and receive JWT
  getMe: () => api.get('/api/auth/me'),                        // Fetch the currently logged-in user's profile
};

/**
 * courseAPI - CRUD operations for courses.
 * Used by both students (to browse) and instructors (to manage).
 */
export const courseAPI = {
  list: (params) => api.get('/api/courses', { params }),       // List courses with optional filters (dept, level, etc.)
  get: (id) => api.get(`/api/courses/${id}`),                  // Get a single course by its ID
  create: (data) => api.post('/api/courses', data),            // Create a new course (instructor/admin only)
  update: (id, data) => api.put(`/api/courses/${id}`, data),   // Update an existing course
  delete: (id) => api.delete(`/api/courses/${id}`),            // Delete a course
};

/**
 * sectionAPI - Manage course sections (e.g., CS101-M1, CS101-F2).
 * Sections are specific offerings of a course, separated by gender and capacity.
 */
export const sectionAPI = {
  list: (params) => api.get('/api/sections', { params }),      // List sections with optional filters
  create: (data) => api.post('/api/sections', data),           // Create a new section for a course
};

/**
 * registrationAPI - Student course registration and completion tracking.
 * Handles enrolling in sections, dropping sections, and marking courses as completed.
 */
export const registrationAPI = {
  register: (sectionId) => api.post(`/api/registration/register/${sectionId}`),      // Enroll in a section
  unregister: (sectionId) => api.delete(`/api/registration/unregister/${sectionId}`), // Drop a section
  myRegistrations: () => api.get('/api/registration/my-registrations'),               // Get all sections the user is enrolled in
  getCompleted: () => api.get('/api/registration/completed'),                          // Get courses the student has already passed
  markCompleted: (courseId) => api.post(`/api/registration/complete/${courseId}`),      // Mark a course as completed (for prerequisites)
  unmarkCompleted: (courseId) => api.delete(`/api/registration/uncomplete/${courseId}`), // Remove completed status from a course
};

/**
 * scheduleAPI - Schedule generation and saved schedules.
 * Interacts with the backend's optimization engine (Genetic Algorithm / PSO).
 */
export const scheduleAPI = {
  generate: (data) => api.post('/api/schedule/generate', data),  // Run the scheduling algorithm with given parameters
  save: (data) => api.post('/api/schedule/save', data),          // Save a generated schedule for later viewing
  getSaved: () => api.get('/api/schedule/saved'),                // Retrieve all previously saved schedules
  deleteSaved: (id) => api.delete(`/api/schedule/saved/${id}`),  // Delete a saved schedule
};

/**
 * dataAPI - Reference data endpoints for dropdowns and filters.
 * These return lists of departments, instructors, rooms, days, and time slots.
 */
export const dataAPI = {
  departments: () => api.get('/api/departments'),   // List all academic departments
  instructors: () => api.get('/api/instructors'),    // List all instructors
  rooms: () => api.get('/api/rooms'),                // List all available rooms
  days: () => api.get('/api/days'),                  // List teaching days (Sun-Thu)
  timeslots: () => api.get('/api/timeslots'),        // List all class/lab time slots
};

export default api;
