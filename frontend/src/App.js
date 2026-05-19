/**
 * App.js - Main Application Entry Point
 *
 * This is the root component of the IMAMU Course Scheduler React application.
 * It sets up client-side routing using React Router and implements role-based
 * access control (RBAC) so that students, instructors, and admins are each
 * directed to the correct dashboard. Unauthenticated users are redirected
 * to the login page, and authenticated users are prevented from revisiting
 * login/register pages.
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import StudentDashboard from './pages/StudentDashboard';
import InstructorDashboard from './pages/InstructorDashboard';
import './App.css';

/**
 * getHomePath - Determines the default dashboard URL based on the user's role.
 * Instructors and admins share the same dashboard (/instructor),
 * while students are sent to /student.
 */
function getHomePath(role) {
  if (role === 'instructor' || role === 'admin') return '/instructor';
  return '/student';
}

/**
 * ProtectedRoute - A wrapper component that guards child routes.
 * It checks three conditions in order:
 *   1. If auth state is still loading, show a loading indicator.
 *   2. If there is no logged-in user, redirect to the login page.
 *   3. If the user's role is not in the allowedRoles list, redirect
 *      them to their own dashboard (prevents students from accessing
 *      the instructor dashboard and vice versa).
 * If all checks pass, the child component is rendered normally.
 */
function ProtectedRoute({ children, allowedRoles }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={getHomePath(user.role)} />;
  }
  return children;
}

/**
 * AppRoutes - Defines all application routes.
 *
 * Route structure:
 *   /login       - Login page (redirects to dashboard if already authenticated)
 *   /register    - Registration page (same redirect behavior)
 *   /student/*   - Student dashboard (protected, students only)
 *   /instructor/* - Instructor/Admin dashboard (protected, instructors and admins)
 *   *            - Catch-all that redirects to the user's dashboard or login
 */
function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading...</div>;

  return (
    <Routes>
      {/* If logged in, redirect away from login; otherwise show LoginPage */}
      <Route path="/login" element={user ? <Navigate to={getHomePath(user.role)} /> : <LoginPage />} />
      {/* If logged in, redirect away from register; otherwise show RegisterPage */}
      <Route path="/register" element={user ? <Navigate to={getHomePath(user.role)} /> : <RegisterPage />} />
      {/* Student-only protected route */}
      <Route path="/student/*" element={<ProtectedRoute allowedRoles={['student']}><StudentDashboard /></ProtectedRoute>} />
      {/* Instructor and admin protected route */}
      <Route path="/instructor/*" element={<ProtectedRoute allowedRoles={['instructor', 'admin']}><InstructorDashboard /></ProtectedRoute>} />
      {/* Any unmatched URL redirects to the appropriate home page or login */}
      <Route path="*" element={<Navigate to={user ? getHomePath(user.role) : '/login'} />} />
    </Routes>
  );
}

/**
 * App - The top-level component.
 * AuthProvider wraps the entire app so every component can access auth state.
 * BrowserRouter enables client-side navigation without full page reloads.
 */
function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
