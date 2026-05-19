/**
 * StudentDashboard.js - Student Dashboard Page
 *
 * This is the main interface for students in the IMAMU Course Scheduler.
 * It provides six views accessible via a sidebar navigation:
 *
 *   1. Browse Courses   - View all available courses, filtered by department/level,
 *                          and register for sections (respects prerequisite locks).
 *   2. Completed Courses - Mark courses the student has already passed, which
 *                          unlocks courses that list them as prerequisites.
 *   3. My Registrations - View currently enrolled sections with stats (count, credits).
 *   4. Generate Schedule - Select an optimization algorithm (GA or PSO) and objective
 *                          (student/instructor/university/all) to generate schedules.
 *   5. View Results     - Display generated schedule options ranked by fitness score,
 *                          with an option to save the preferred schedule.
 *   6. Saved Schedules  - View and manage previously saved schedules.
 *
 * The dashboard loads all data (courses, registrations, departments, time slots,
 * completed courses) in parallel on mount for fast initial rendering.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { courseAPI, registrationAPI, scheduleAPI, dataAPI } from '../services/api';
import ScheduleCalendar from '../components/ScheduleCalendar';

export default function StudentDashboard() {
  const { user, logout } = useAuth();

  // --- State variables ---
  const [activePage, setActivePage] = useState('courses');       // Currently visible page/tab
  const [courses, setCourses] = useState([]);                    // All courses from the backend
  const [registrations, setRegistrations] = useState([]);        // Sections the student is enrolled in
  const [completedCourses, setCompletedCourses] = useState([]);  // Courses the student has passed
  const [departments, setDepartments] = useState([]);            // Department list for filters
  const [scheduleResults, setScheduleResults] = useState([]);    // Generated schedule options from the algorithm
  const [savedSchedules, setSavedSchedules] = useState([]);      // Previously saved schedules
  const [selectedTab, setSelectedTab] = useState(0);             // Which schedule result tab is active
  const [generating, setGenerating] = useState(false);           // True while the algorithm is running
  const [algorithm, setAlgorithm] = useState('GA');              // Selected algorithm: 'GA' or 'PSO'
  const [objective, setObjective] = useState('student');          // Optimization objective for GA
  const [filterDept, setFilterDept] = useState('');              // Department filter for course browsing
  const [filterLevel, setFilterLevel] = useState('');            // Level filter for course browsing
  const [timeSlots, setTimeSlots] = useState([]);                // Time slot definitions for the calendar
  const [msg, setMsg] = useState('');                            // Feedback message (success/error)

  /**
   * loadData - Fetches all primary data in parallel using Promise.all.
   * Called on initial mount and after any registration/completion change.
   * useCallback ensures this function reference stays stable across renders.
   */
  const loadData = useCallback(async () => {
    try {
      const [coursesRes, regRes, deptRes, tsRes, completedRes] = await Promise.all([
        courseAPI.list(),                    // All courses with their sections
        registrationAPI.myRegistrations(),   // Student's current registrations
        dataAPI.departments(),               // Department list for dropdowns
        dataAPI.timeslots(),                 // Time slot definitions
        registrationAPI.getCompleted(),      // Courses marked as completed
      ]);
      setCourses(coursesRes.data);
      setRegistrations(regRes.data);
      setDepartments(deptRes.data);
      // Filter to only "Class" type time slots (exclude lab/break slots)
      setTimeSlots(tsRes.data.filter(t => t.slot_type === 'Class'));
      setCompletedCourses(completedRes.data);
    } catch (err) { console.error(err); }
  }, []);

  // Load all data when the component first mounts
  useEffect(() => { loadData(); }, [loadData]);

  /**
   * loadSaved - Fetches the user's saved schedules from the backend.
   * Only called when the user navigates to the "Saved Schedules" tab.
   */
  const loadSaved = async () => {
    try {
      const res = await scheduleAPI.getSaved();
      setSavedSchedules(res.data);
    } catch (err) { console.error(err); }
  };

  // Fetch saved schedules whenever the user switches to the "saved" page
  useEffect(() => {
    if (activePage === 'saved') loadSaved();
  }, [activePage]);

  /**
   * handleRegister - Enrolls the student in a specific section.
   * Shows a success/error message and refreshes data to update the UI.
   */
  const handleRegister = async (sectionId) => {
    try {
      await registrationAPI.register(sectionId);
      setMsg('Registered!');
      loadData(); // Refresh to reflect the new registration
      setTimeout(() => setMsg(''), 2000); // Auto-hide message after 2 seconds
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Registration failed');
      setTimeout(() => setMsg(''), 4000);
    }
  };

  /**
   * handleUnregister - Drops the student from a specific section.
   */
  const handleUnregister = async (sectionId) => {
    try {
      await registrationAPI.unregister(sectionId);
      setMsg('Unregistered');
      loadData();
      setTimeout(() => setMsg(''), 2000);
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Failed');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  /**
   * handleMarkCompleted - Marks a course as already passed by the student.
   * This is used to satisfy prerequisites for other courses.
   */
  const handleMarkCompleted = async (courseId) => {
    try {
      await registrationAPI.markCompleted(courseId);
      setMsg('Course marked as completed!');
      loadData();
      setTimeout(() => setMsg(''), 2000);
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Failed');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  /**
   * handleUnmarkCompleted - Removes the completed status from a course.
   */
  const handleUnmarkCompleted = async (courseId) => {
    try {
      await registrationAPI.unmarkCompleted(courseId);
      setMsg('Removed from completed');
      loadData();
      setTimeout(() => setMsg(''), 2000);
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Failed');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  /**
   * handleGenerate - Triggers the schedule generation algorithm on the backend.
   *
   * Steps:
   *   1. Collects unique course IDs from current registrations.
   *   2. Validates that the student has at least one registration.
   *   3. Sends the request with algorithm type, objective, and gender preference.
   *   4. On success, stores the results and switches to the results view.
   *
   * Note: PSO always uses 'student' objective; GA supports multiple objectives.
   */
  const handleGenerate = async () => {
    // Extract unique course IDs from registrations (a student may have multiple sections)
    const courseIds = [...new Set(registrations.map(r => r.course_id))];
    if (courseIds.length === 0) {
      setMsg('Please register for courses first');
      setTimeout(() => setMsg(''), 3000);
      return;
    }
    setGenerating(true); // Show loading overlay
    try {
      const res = await scheduleAPI.generate({
        selected_course_ids: courseIds,
        algorithm,
        objective: algorithm === 'GA' ? objective : 'student', // PSO only supports student objective
        preferred_gender: user.gender, // Filter sections by the student's gender
      });
      setScheduleResults(res.data); // Store the array of generated schedule options
      setSelectedTab(0);            // Select the first (best) schedule by default
      setActivePage('schedule');     // Navigate to the results view
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Generation failed');
      setTimeout(() => setMsg(''), 3000);
    } finally {
      setGenerating(false);
    }
  };

  /**
   * handleSave - Saves the currently selected schedule result to the backend.
   * Includes metadata like algorithm type, fitness score, and conflict count.
   */
  const handleSave = async (result) => {
    try {
      await scheduleAPI.save({
        name: `${result.label} - ${new Date().toLocaleDateString()}`,
        algorithm,
        objective: result.objective,
        fitness: result.fitness,
        conflicts: result.conflicts,
        schedule_data: JSON.stringify(result.slots), // Serialize slot data as JSON string
      });
      setMsg('Schedule saved!');
      setTimeout(() => setMsg(''), 2000);
    } catch (err) {
      setMsg('Failed to save');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  /**
   * handleDeleteSaved - Deletes a previously saved schedule.
   */
  const handleDeleteSaved = async (id) => {
    try {
      await scheduleAPI.deleteSaved(id);
      loadSaved(); // Refresh the saved schedules list
    } catch (err) { console.error(err); }
  };

  // --- Derived data for quick lookups ---
  // Sets for O(1) membership checks when rendering the course table
  const registeredSectionIds = new Set(registrations.map(r => r.section_id || r.id));
  const registeredCourseIds = new Set(registrations.map(r => r.course_id));
  const completedCourseCodes = new Set(completedCourses.map(c => c.code));
  const completedCourseIds = new Set(completedCourses.map(c => c.id));

  /**
   * getPrerequisiteStatus - Checks if a course's prerequisites are satisfied.
   * Compares the course's prerequisite codes against the student's completed courses.
   * Returns { met: boolean, missing: string[] } where missing lists unsatisfied prereqs.
   */
  const getPrerequisiteStatus = (course) => {
    if (!course.prerequisites || course.prerequisites.length === 0) {
      return { met: true, missing: [] }; // No prerequisites required
    }
    // Find prerequisite codes that are NOT in the student's completed set
    const missing = course.prerequisites.filter(code => !completedCourseCodes.has(code));
    return { met: missing.length === 0, missing };
  };

  // Apply department and level filters to the course list
  const filteredCourses = courses.filter(c => {
    if (filterDept && c.department_id !== parseInt(filterDept)) return false;
    if (filterLevel && c.level !== parseInt(filterLevel)) return false;
    return true;
  });

  return (
    <div className="dashboard">
      {/* Sidebar navigation */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>IMAMU Scheduler</h2>
          <span className="role-badge role-student">Student</span>
          <div style={{ marginTop: 8, fontSize: '0.8rem', opacity: 0.7 }}>{user.full_name}</div>
        </div>
        <nav className="sidebar-nav">
          {/* Navigation buttons - activePage state controls which view is shown */}
          <button className={`nav-item ${activePage === 'courses' ? 'active' : ''}`} onClick={() => setActivePage('courses')}>
            Browse Courses
          </button>
          <button className={`nav-item ${activePage === 'completed' ? 'active' : ''}`} onClick={() => setActivePage('completed')}>
            Completed Courses ({completedCourses.length})
          </button>
          <button className={`nav-item ${activePage === 'registered' ? 'active' : ''}`} onClick={() => setActivePage('registered')}>
            My Registrations ({registrations.length})
          </button>
          <button className={`nav-item ${activePage === 'generate' ? 'active' : ''}`} onClick={() => setActivePage('generate')}>
            Generate Schedule
          </button>
          {/* "View Results" button only appears after a schedule has been generated */}
          {scheduleResults.length > 0 && (
            <button className={`nav-item ${activePage === 'schedule' ? 'active' : ''}`} onClick={() => setActivePage('schedule')}>
              View Results
            </button>
          )}
          <button className={`nav-item ${activePage === 'saved' ? 'active' : ''}`} onClick={() => setActivePage('saved')}>
            Saved Schedules
          </button>
        </nav>
        <div className="sidebar-footer">
          <button className="nav-item" onClick={logout}>Sign Out</button>
        </div>
      </aside>

      <main className="main-content">
        {/* Global feedback message - color changes based on success (green) vs error (red) */}
        {msg && <div className="error-msg" style={{ marginBottom: 16, background: msg.includes('fail') || msg.includes('Please') || msg.includes('not met') || msg.includes('must complete') ? '#fef2f2' : '#ecfdf5', color: msg.includes('fail') || msg.includes('Please') || msg.includes('not met') || msg.includes('must complete') ? '#dc2626' : '#059669' }}>{msg}</div>}

        {/* Full-screen loading overlay shown while the scheduling algorithm runs */}
        {generating && (
          <div className="generating-overlay">
            <div className="big-spinner"></div>
            <p>Generating optimal schedules using {algorithm}...</p>
            <p style={{ fontSize: '0.85rem', opacity: 0.7, marginTop: 8 }}>This may take a moment</p>
          </div>
        )}

        {/* ===================== BROWSE COURSES PAGE ===================== */}
        {activePage === 'courses' && (
          <>
            <div className="page-header">
              <h1>Browse Courses</h1>
              <p style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: 4 }}>
                Mark courses you already passed in "Completed Courses" to unlock prerequisites.
              </p>
            </div>
            {/* Department and level filter dropdowns */}
            <div className="filters">
              <select value={filterDept} onChange={e => setFilterDept(e.target.value)}>
                <option value="">All Departments</option>
                {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <select value={filterLevel} onChange={e => setFilterLevel(e.target.value)}>
                <option value="">All Levels</option>
                {[1,2,3,4,5,6,7,8].map(l => <option key={l} value={l}>Level {l}</option>)}
              </select>
            </div>
            <div className="card">
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Course Name</th>
                      <th>Department</th>
                      <th>Level</th>
                      <th>Credits</th>
                      <th>Prerequisites</th>
                      <th>Sections</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCourses.map(course => {
                      // Check if the student has met all prerequisites for this course
                      const prereqStatus = getPrerequisiteStatus(course);
                      const isCompleted = completedCourseIds.has(course.id);
                      // Only show sections matching the student's gender
                      const genderSections = (course.sections || []).filter(s => s.gender === user.gender);

                      // Completed courses are shown grayed out with a "Completed" badge
                      if (isCompleted) {
                        return (
                          <tr key={course.id} style={{ opacity: 0.5 }}>
                            <td><strong>{course.code}</strong></td>
                            <td>{course.name}</td>
                            <td><span className="badge badge-blue">{course.department_name}</span></td>
                            <td>Level {course.level}</td>
                            <td>{course.credits}</td>
                            <td>-</td>
                            <td>-</td>
                            <td><span className="badge badge-green">Completed</span></td>
                          </tr>
                        );
                      }

                      // If no sections exist for the student's gender, show a warning
                      if (genderSections.length === 0) {
                        return (
                          <tr key={course.id}>
                            <td><strong>{course.code}</strong></td>
                            <td>{course.name}</td>
                            <td><span className="badge badge-blue">{course.department_name}</span></td>
                            <td>Level {course.level}</td>
                            <td>{course.credits}</td>
                            <td>
                              {course.prerequisites.length > 0
                                ? course.prerequisites.map(p => (
                                    <span key={p} className={`badge ${completedCourseCodes.has(p) ? 'badge-green' : 'badge-red'}`} style={{ marginRight: 4, fontSize: '0.7rem' }}>{p}</span>
                                  ))
                                : <span style={{ color: '#9ca3af', fontSize: '0.8rem' }}>None</span>
                              }
                            </td>
                            <td><span className="badge badge-orange">No sections for {user.gender}</span></td>
                            <td>-</td>
                          </tr>
                        );
                      }

                      // Render one row per section, using rowSpan to merge course-level cells
                      return (
                        <React.Fragment key={course.id}>
                          {genderSections.map((section, sIdx) => (
                            <tr key={section.id} style={!prereqStatus.met ? { opacity: 0.6 } : {}}>
                              {/* Only render merged course-level cells on the first section row */}
                              {sIdx === 0 ? (
                                <>
                                  <td rowSpan={genderSections.length}><strong>{course.code}</strong></td>
                                  <td rowSpan={genderSections.length}>{course.name}</td>
                                  <td rowSpan={genderSections.length}><span className="badge badge-blue">{course.department_name}</span></td>
                                  <td rowSpan={genderSections.length}>Level {course.level}</td>
                                  <td rowSpan={genderSections.length}>{course.credits}</td>
                                  <td rowSpan={genderSections.length}>
                                    {/* Show each prerequisite as a colored badge: green=met, red=missing */}
                                    {course.prerequisites.length > 0
                                      ? course.prerequisites.map(p => (
                                          <span key={p} className={`badge ${completedCourseCodes.has(p) ? 'badge-green' : 'badge-red'}`} style={{ marginRight: 4, fontSize: '0.7rem' }}>{p}</span>
                                        ))
                                      : <span style={{ color: '#9ca3af', fontSize: '0.8rem' }}>None</span>
                                    }
                                  </td>
                                </>
                              ) : null}
                              {/* Section-specific cells: section ID with enrollment count */}
                              <td>
                                <span className="badge badge-gray">{section.section_id}</span>
                                <span style={{ fontSize: '0.75rem', color: '#6b7280', marginLeft: 4 }}>
                                  ({section.enrolled}/{section.capacity})
                                </span>
                              </td>
                              {/* Action cell: locked, register, drop, or already enrolled */}
                              <td>
                                {!prereqStatus.met ? (
                                  // Prerequisites not met - show which courses need to be completed
                                  <span style={{ fontSize: '0.75rem', color: '#dc2626' }}>
                                    Locked - complete: {prereqStatus.missing.join(', ')}
                                  </span>
                                ) : registeredSectionIds.has(section.id) ? (
                                  // Already enrolled in this section - show drop button
                                  <button className="btn btn-danger btn-sm" onClick={() => handleUnregister(section.id)}>Drop</button>
                                ) : registeredCourseIds.has(course.id) ? (
                                  // Enrolled in a different section of the same course
                                  <span className="badge badge-green">Enrolled (other section)</span>
                                ) : (
                                  // Available to register
                                  <button className="btn btn-primary btn-sm" onClick={() => handleRegister(section.id)}>Register</button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* ===================== COMPLETED COURSES PAGE ===================== */}
        {activePage === 'completed' && (
          <>
            <div className="page-header">
              <h1>Completed Courses</h1>
              <p style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: 4 }}>
                Mark courses you have already passed. This unlocks courses that require them as prerequisites.
              </p>
            </div>

            {/* Table of courses already marked as completed (with remove option) */}
            {completedCourses.length > 0 && (
              <div className="card" style={{ marginBottom: 24 }}>
                <h3 style={{ marginBottom: 12 }}>Courses You Have Passed</h3>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr><th>Code</th><th>Course Name</th><th>Level</th><th>Credits</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                      {completedCourses.map(c => (
                        <tr key={c.id}>
                          <td><strong>{c.code}</strong></td>
                          <td>{c.name}</td>
                          <td>Level {c.level}</td>
                          <td>{c.credits}</td>
                          <td><button className="btn btn-danger btn-sm" onClick={() => handleUnmarkCompleted(c.id)}>Remove</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Full course list where students can click "Mark Completed" */}
            <div className="card">
              <h3 style={{ marginBottom: 12 }}>All Courses - Click to Mark as Completed</h3>
              <div className="filters" style={{ marginBottom: 16 }}>
                <select value={filterDept} onChange={e => setFilterDept(e.target.value)}>
                  <option value="">All Departments</option>
                  {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
                <select value={filterLevel} onChange={e => setFilterLevel(e.target.value)}>
                  <option value="">All Levels</option>
                  {[1,2,3,4,5,6,7,8].map(l => <option key={l} value={l}>Level {l}</option>)}
                </select>
              </div>
              <div className="table-container">
                <table>
                  <thead>
                    <tr><th>Code</th><th>Course Name</th><th>Department</th><th>Level</th><th>Credits</th><th>Action</th></tr>
                  </thead>
                  <tbody>
                    {filteredCourses.map(course => (
                      <tr key={course.id}>
                        <td><strong>{course.code}</strong></td>
                        <td>{course.name}</td>
                        <td><span className="badge badge-blue">{course.department_name}</span></td>
                        <td>Level {course.level}</td>
                        <td>{course.credits}</td>
                        <td>
                          {completedCourseIds.has(course.id) ? (
                            <span className="badge badge-green">Completed</span>
                          ) : (
                            <button className="btn btn-success btn-sm" onClick={() => handleMarkCompleted(course.id)}>
                              Mark Completed
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* ===================== MY REGISTRATIONS PAGE ===================== */}
        {activePage === 'registered' && (
          <>
            <div className="page-header">
              <h1>My Registrations</h1>
            </div>
            {/* Summary statistics cards */}
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{registrations.length}</div>
                <div className="stat-label">Registered Courses</div>
              </div>
              <div className="stat-card">
                {/* Calculate total credits by looking up each registered course's credit value */}
                <div className="stat-value">{registrations.reduce((sum, r) => sum + (courses.find(c => c.id === r.course_id)?.credits || 3), 0)}</div>
                <div className="stat-label">Total Credits</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{completedCourses.length}</div>
                <div className="stat-label">Completed Courses</div>
              </div>
            </div>
            <div className="card">
              {registrations.length === 0 ? (
                <div className="empty-state">
                  <p>No registrations yet. Browse courses and register to get started.</p>
                </div>
              ) : (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr><th>Course Code</th><th>Course Name</th><th>Section</th><th>Gender</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                      {registrations.map(reg => (
                        <tr key={reg.id}>
                          <td><strong>{reg.course_code}</strong></td>
                          <td>{reg.course_name}</td>
                          <td><span className="badge badge-gray">{reg.section_id}</span></td>
                          <td><span className="badge badge-purple">{reg.gender}</span></td>
                          <td><button className="btn btn-danger btn-sm" onClick={() => handleUnregister(reg.id)}>Drop</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}

        {/* ===================== GENERATE SCHEDULE PAGE ===================== */}
        {activePage === 'generate' && (
          <>
            <div className="page-header">
              <h1>Generate Schedule</h1>
            </div>
            <div className="card">
              {/* Algorithm selection: Genetic Algorithm or Particle Swarm Optimization */}
              <h3 style={{ marginBottom: 16 }}>Algorithm Selection</h3>
              <div className="algo-selector">
                <button className={`algo-btn ${algorithm === 'GA' ? 'active' : ''}`} onClick={() => setAlgorithm('GA')}>
                  Genetic Algorithm (GA)
                </button>
                <button className={`algo-btn ${algorithm === 'PSO' ? 'active' : ''}`} onClick={() => setAlgorithm('PSO')}>
                  Particle Swarm (PSO)
                </button>
              </div>
              {/* Objective selection only shown for GA (PSO defaults to student objective) */}
              {algorithm === 'GA' && (
                <>
                  <h3 style={{ marginBottom: 12, marginTop: 20 }}>Optimization Objective</h3>
                  <div className="algo-selector">
                    <button className={`algo-btn ${objective === 'student' ? 'active' : ''}`} onClick={() => setObjective('student')}>
                      Student-Optimized
                    </button>
                    <button className={`algo-btn ${objective === 'instructor' ? 'active' : ''}`} onClick={() => setObjective('instructor')}>
                      Instructor-Optimized
                    </button>
                    <button className={`algo-btn ${objective === 'university' ? 'active' : ''}`} onClick={() => setObjective('university')}>
                      University-Optimized
                    </button>
                    <button className={`algo-btn ${objective === 'all' ? 'active' : ''}`} onClick={() => setObjective('all')}>
                      All Three
                    </button>
                  </div>
                </>
              )}
              <div style={{ marginTop: 24 }}>
                {/* Status message showing how many courses will be scheduled */}
                <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: 16 }}>
                  {registrations.length > 0
                    ? `Will generate schedules for your ${registrations.length} registered course(s).`
                    : 'You need to register for courses first before generating a schedule.'
                  }
                </p>
                {/* Generate button - disabled if no registrations or already generating */}
                <button className="btn btn-primary" onClick={handleGenerate} disabled={registrations.length === 0 || generating}>
                  {generating ? <><span className="spinner"></span> Generating...</> : 'Generate Schedule'}
                </button>
              </div>
            </div>
          </>
        )}

        {/* ===================== SCHEDULE RESULTS PAGE ===================== */}
        {activePage === 'schedule' && scheduleResults.length > 0 && (
          <>
            <div className="page-header">
              <h1>Generated Schedules</h1>
            </div>
            {/* Tab bar showing each generated schedule option ranked by fitness */}
            <div className="schedule-tabs">
              {scheduleResults.map((result, idx) => (
                <button key={idx} className={`schedule-tab ${selectedTab === idx ? 'active' : ''}`} onClick={() => setSelectedTab(idx)}>
                  <div className="tab-rank">#{result.rank}</div>
                  <div className="tab-label">{result.label}</div>
                  <div className="tab-fitness">Fitness: {result.fitness} | Conflicts: {result.conflicts}</div>
                </button>
              ))}
            </div>
            {/* Calendar view of the currently selected schedule */}
            <div className="card">
              <div className="card-header">
                <div>
                  <h3>{scheduleResults[selectedTab]?.label}</h3>
                  <p style={{ fontSize: '0.85rem', color: '#6b7280' }}>{scheduleResults[selectedTab]?.description}</p>
                </div>
                <button className="btn btn-success btn-sm" onClick={() => handleSave(scheduleResults[selectedTab])}>
                  Save This Schedule
                </button>
              </div>
              {/* Render the weekly calendar grid with the schedule's time slots */}
              <ScheduleCalendar slots={scheduleResults[selectedTab]?.slots || []} timeSlots={timeSlots} />
            </div>
          </>
        )}

        {/* ===================== SAVED SCHEDULES PAGE ===================== */}
        {activePage === 'saved' && (
          <>
            <div className="page-header">
              <h1>Saved Schedules</h1>
            </div>
            {savedSchedules.length === 0 ? (
              <div className="card">
                <div className="empty-state">
                  <p>No saved schedules. Generate a schedule and save it to see it here.</p>
                </div>
              </div>
            ) : (
              // Render each saved schedule as a separate card with its calendar
              savedSchedules.map(saved => (
                <div key={saved.id} className="card">
                  <div className="card-header">
                    <div>
                      <h3>{saved.name}</h3>
                      <p style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                        {saved.algorithm} | Fitness: {saved.fitness} | Conflicts: {saved.conflicts}
                      </p>
                    </div>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDeleteSaved(saved.id)}>Delete</button>
                  </div>
                  <ScheduleCalendar slots={saved.schedule_data || []} timeSlots={timeSlots} />
                </div>
              ))
            )}
          </>
        )}
      </main>
    </div>
  );
}
