/**
 * AuthContext.js - Authentication State Management
 *
 * This file creates a React Context that provides authentication state
 * (current user, loading status) and auth actions (login, register, logout)
 * to every component in the application. It uses localStorage to persist
 * the JWT token and user data so the session survives page refreshes.
 *
 * Usage pattern:
 *   - Wrap your app with <AuthProvider> (done in App.js)
 *   - In any child component, call useAuth() to get { user, loading, login, register, logout }
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../services/api';

// Create a Context object with a default value of null (no auth state yet)
const AuthContext = createContext(null);

/**
 * AuthProvider - Context provider component that manages authentication state.
 * It wraps the entire app and makes auth data available via useAuth().
 */
export function AuthProvider({ children }) {
  // user holds the current user object (null if not logged in)
  const [user, setUser] = useState(null);
  // loading is true while we check localStorage for an existing session
  const [loading, setLoading] = useState(true);

  /**
   * On initial mount, check if a token and user data exist in localStorage.
   * If they do, restore the user session without requiring a new login.
   * This runs only once (empty dependency array).
   */
  useEffect(() => {
    const token = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    if (token && savedUser) {
      // Parse the stored JSON string back into a user object
      setUser(JSON.parse(savedUser));
    }
    // Mark loading as complete so the app can render
    setLoading(false);
  }, []);

  /**
   * login - Sends credentials to the backend and stores the returned
   * JWT token and user data in both state and localStorage.
   * Returns the user object so the caller can read the role for redirects.
   */
  const login = async (username, password) => {
    const res = await authAPI.login({ username, password });
    const { access_token, user: userData } = res.data;
    // Persist token and user info for future page loads
    localStorage.setItem('token', access_token);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
    return userData;
  };

  /**
   * register - Creates a new account via the backend API.
   * On success, the backend returns a token and user object just like login,
   * so the user is automatically logged in after registration.
   */
  const register = async (data) => {
    const res = await authAPI.register(data);
    const { access_token, user: userData } = res.data;
    localStorage.setItem('token', access_token);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
    return userData;
  };

  /**
   * logout - Clears the stored token and user data from localStorage
   * and resets the user state to null, effectively ending the session.
   */
  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  };

  // Provide the auth state and actions to all child components
  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * useAuth - Custom hook that provides convenient access to the AuthContext.
 * Any component can call: const { user, login, logout } = useAuth();
 */
export function useAuth() {
  return useContext(AuthContext);
}
