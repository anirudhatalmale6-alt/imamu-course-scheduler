/**
 * LoginPage.js - User Login Page
 *
 * This component renders the login form for the IMAMU Course Scheduler.
 * It collects a username and password, sends them to the backend via the
 * AuthContext's login function, and handles success/error states.
 * On successful login, the user is automatically redirected to their
 * role-appropriate dashboard (handled by App.js routing logic).
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  // Get the login function from the authentication context
  const { login } = useAuth();

  // Form state - stores username and password input values
  const [form, setForm] = useState({ username: '', password: '' });
  // Error message to display if login fails (e.g., wrong credentials)
  const [error, setError] = useState('');
  // Loading flag to disable the submit button while the request is in progress
  const [loading, setLoading] = useState(false);

  /**
   * handleSubmit - Called when the user submits the login form.
   * Prevents the default form submission (which would reload the page),
   * calls the login function from AuthContext, and catches any errors.
   */
  const handleSubmit = async (e) => {
    e.preventDefault(); // Prevent full-page reload on form submit
    setError('');        // Clear any previous error messages
    setLoading(true);    // Show loading state on the button
    try {
      // Attempt to log in - on success, AuthContext updates the user state
      // which triggers a redirect via the routing logic in App.js
      await login(form.username, form.password);
    } catch (err) {
      // Display the backend's error message, or a generic fallback
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false); // Re-enable the submit button regardless of outcome
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Welcome Back</h1>
        <p className="subtitle">IMAMU Course Scheduler - Sign in to continue</p>

        {/* Show error message banner if login failed */}
        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          {/* Username input field */}
          <div className="form-group">
            <label>Username</label>
            <input type="text" value={form.username} onChange={e => setForm({...form, username: e.target.value})} required />
          </div>

          {/* Password input field */}
          <div className="form-group">
            <label>Password</label>
            <input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} required />
          </div>

          {/* Submit button - shows "Signing in..." while loading, disabled to prevent double-submit */}
          <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        {/* Link to the registration page for new users */}
        <p className="auth-link">Don't have an account? <Link to="/register">Register</Link></p>
      </div>
    </div>
  );
}
