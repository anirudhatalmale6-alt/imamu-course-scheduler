/**
 * RegisterPage.js - User Registration Page
 *
 * This component renders the registration form for new users of the IMAMU
 * Course Scheduler. Users provide their personal info, select a role
 * (student, instructor, or admin), choose a gender and department, and
 * (if student) select their academic level. On successful registration,
 * the backend returns a JWT token and the user is automatically logged in.
 *
 * The department list is fetched dynamically from the backend API on mount.
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { dataAPI } from '../services/api';

export default function RegisterPage() {
  // Get the register function from the authentication context
  const { register } = useAuth();

  // Form state - all fields needed for user registration
  const [form, setForm] = useState({
    username: '', email: '', password: '', full_name: '',
    role: 'student',       // Default role is student
    gender: 'Male',        // Default gender (used for section filtering)
    department: '',        // Will be populated from the departments dropdown
    level: 1,              // Academic level (1-8), only relevant for students
  });

  // List of departments fetched from the backend for the dropdown
  const [departments, setDepartments] = useState([]);
  // Error message displayed if registration fails
  const [error, setError] = useState('');
  // Loading state to prevent double-submission
  const [loading, setLoading] = useState(false);

  /**
   * Fetch the list of available departments from the backend when the
   * component first mounts. This populates the department dropdown.
   */
  useEffect(() => {
    dataAPI.departments().then(res => setDepartments(res.data)).catch(() => {});
  }, []);

  /**
   * handleSubmit - Validates and submits the registration form.
   * On success, the AuthContext stores the JWT token and user data,
   * and the routing logic in App.js redirects to the appropriate dashboard.
   */
  const handleSubmit = async (e) => {
    e.preventDefault(); // Prevent default form submission behavior
    setError('');
    setLoading(true);
    try {
      // Send registration data to the backend via AuthContext
      await register(form);
    } catch (err) {
      // Show backend validation errors or a generic fallback message
      setError(err.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Create Account</h1>
        <p className="subtitle">IMAMU Course Scheduler - Register to get started</p>

        {/* Display error banner if registration failed */}
        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          {/* Full name input */}
          <div className="form-group">
            <label>Full Name</label>
            <input type="text" value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} required />
          </div>

          {/* Username and email side by side */}
          <div className="form-row">
            <div className="form-group">
              <label>Username</label>
              <input type="text" value={form.username} onChange={e => setForm({...form, username: e.target.value})} required />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} required />
            </div>
          </div>

          {/* Password input - minimum 4 characters */}
          <div className="form-group">
            <label>Password</label>
            <input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} required minLength={4} />
          </div>

          {/* Role and gender dropdowns side by side */}
          <div className="form-row">
            <div className="form-group">
              <label>Role</label>
              <select value={form.role} onChange={e => setForm({...form, role: e.target.value})}>
                <option value="student">Student</option>
                <option value="instructor">Instructor</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="form-group">
              <label>Gender</label>
              <select value={form.gender} onChange={e => setForm({...form, gender: e.target.value})}>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
              </select>
            </div>
          </div>

          {/* Department dropdown and level selector (level only shown for students) */}
          <div className="form-row">
            <div className="form-group">
              <label>Department</label>
              <select value={form.department} onChange={e => setForm({...form, department: e.target.value})}>
                <option value="">Select...</option>
                {departments.map(d => <option key={d.id} value={d.name}>{d.name}</option>)}
              </select>
            </div>
            {/* Level selector is conditionally rendered only for students */}
            {form.role === 'student' && (
              <div className="form-group">
                <label>Level</label>
                <select value={form.level} onChange={e => setForm({...form, level: parseInt(e.target.value)})}>
                  {[1,2,3,4,5,6,7,8].map(l => <option key={l} value={l}>Level {l}</option>)}
                </select>
              </div>
            )}
          </div>

          {/* Submit button with loading state */}
          <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
            {loading ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>

        {/* Link to login page for existing users */}
        <p className="auth-link">Already have an account? <Link to="/login">Sign In</Link></p>
      </div>
    </div>
  );
}
