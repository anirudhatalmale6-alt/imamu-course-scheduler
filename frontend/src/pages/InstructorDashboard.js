import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { courseAPI, sectionAPI, registrationAPI, scheduleAPI, dataAPI } from '../services/api';
import ScheduleCalendar from '../components/ScheduleCalendar';

export default function InstructorDashboard() {
  const { user, logout } = useAuth();
  const [activePage, setActivePage] = useState('courses');
  const [courses, setCourses] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [registrations, setRegistrations] = useState([]);
  const [scheduleResults, setScheduleResults] = useState([]);
  const [selectedTab, setSelectedTab] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [algorithm, setAlgorithm] = useState('GA');
  const [objective, setObjective] = useState('instructor');
  const [timeSlots, setTimeSlots] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [showSectionModal, setShowSectionModal] = useState(false);
  const [editCourse, setEditCourse] = useState(null);
  const [msg, setMsg] = useState('');
  const [filterDept, setFilterDept] = useState('');
  const [courseForm, setCourseForm] = useState({
    code: '', name: '', level: 1, credits: 3, is_lab: false, department_id: '', prerequisite_codes: [],
  });
  const [sectionForm, setSectionForm] = useState({
    section_id: '', gender: 'Male', capacity: 40, course_id: null,
  });

  const loadData = useCallback(async () => {
    try {
      const [coursesRes, deptRes, regRes, tsRes] = await Promise.all([
        courseAPI.list({ include_archived: true }),
        dataAPI.departments(),
        registrationAPI.myRegistrations(),
        dataAPI.timeslots(),
      ]);
      setCourses(coursesRes.data);
      setDepartments(deptRes.data);
      setRegistrations(regRes.data);
      setTimeSlots(tsRes.data.filter(t => t.slot_type === 'Class'));
    } catch (err) { console.error(err); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleCreateCourse = async (e) => {
    e.preventDefault();
    try {
      if (editCourse) {
        await courseAPI.update(editCourse.id, {
          name: courseForm.name,
          level: courseForm.level,
          credits: courseForm.credits,
          is_lab: courseForm.is_lab,
          prerequisite_codes: courseForm.prerequisite_codes,
        });
        setMsg('Course updated');
      } else {
        await courseAPI.create({
          ...courseForm,
          department_id: parseInt(courseForm.department_id),
        });
        setMsg('Course created');
      }
      setShowModal(false);
      setEditCourse(null);
      loadData();
      setTimeout(() => setMsg(''), 2000);
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Failed');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const handleDeleteCourse = async (id) => {
    if (!window.confirm('Delete this course?')) return;
    try {
      await courseAPI.delete(id);
      setMsg('Course deleted');
      loadData();
      setTimeout(() => setMsg(''), 2000);
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Failed');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const handleArchiveCourse = async (course) => {
    try {
      await courseAPI.update(course.id, { is_archived: !course.is_archived });
      setMsg(course.is_archived ? 'Course restored' : 'Course archived');
      loadData();
      setTimeout(() => setMsg(''), 2000);
    } catch (err) { setMsg('Failed'); setTimeout(() => setMsg(''), 3000); }
  };

  const handleCreateSection = async (e) => {
    e.preventDefault();
    try {
      await sectionAPI.create(sectionForm);
      setMsg('Section created');
      setShowSectionModal(false);
      loadData();
      setTimeout(() => setMsg(''), 2000);
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Failed');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const handleRegister = async (sectionId) => {
    try {
      await registrationAPI.register(sectionId);
      setMsg('Registered!');
      loadData();
      setTimeout(() => setMsg(''), 2000);
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Registration failed');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const handleUnregister = async (sectionId) => {
    try {
      await registrationAPI.unregister(sectionId);
      setMsg('Unregistered');
      loadData();
      setTimeout(() => setMsg(''), 2000);
    } catch (err) { setMsg('Failed'); setTimeout(() => setMsg(''), 3000); }
  };

  const handleGenerate = async () => {
    const courseIds = [...new Set(registrations.map(r => r.course_id))];
    if (courseIds.length === 0) {
      setMsg('Register for courses first');
      setTimeout(() => setMsg(''), 3000);
      return;
    }
    setGenerating(true);
    try {
      const res = await scheduleAPI.generate({
        selected_course_ids: courseIds,
        algorithm,
        objective: algorithm === 'GA' ? objective : 'student',
        preferred_gender: user.gender,
      });
      setScheduleResults(res.data);
      setSelectedTab(0);
      setActivePage('schedule');
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Generation failed');
      setTimeout(() => setMsg(''), 3000);
    } finally {
      setGenerating(false);
    }
  };

  const openEdit = (course) => {
    setEditCourse(course);
    setCourseForm({
      code: course.code,
      name: course.name,
      level: course.level,
      credits: course.credits,
      is_lab: course.is_lab,
      department_id: course.department_id,
      prerequisite_codes: course.prerequisites || [],
    });
    setShowModal(true);
  };

  const openCreate = () => {
    setEditCourse(null);
    setCourseForm({ code: '', name: '', level: 1, credits: 3, is_lab: false, department_id: departments[0]?.id || '', prerequisite_codes: [] });
    setShowModal(true);
  };

  const openAddSection = (courseId) => {
    setSectionForm({ section_id: '', gender: 'Male', capacity: 40, course_id: courseId });
    setShowSectionModal(true);
  };

  const registeredSectionIds = new Set(registrations.map(r => r.section_id || r.id));
  const registeredCourseIds = new Set(registrations.map(r => r.course_id));

  const filteredCourses = courses.filter(c => {
    if (filterDept && c.department_id !== parseInt(filterDept)) return false;
    return true;
  });

  return (
    <div className="dashboard">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>IMAMU Scheduler</h2>
          <span className="role-badge role-instructor">Instructor</span>
          <div style={{ marginTop: 8, fontSize: '0.8rem', opacity: 0.7 }}>{user.full_name}</div>
        </div>
        <nav className="sidebar-nav">
          <button className={`nav-item ${activePage === 'courses' ? 'active' : ''}`} onClick={() => setActivePage('courses')}>
            Manage Courses
          </button>
          <button className={`nav-item ${activePage === 'register' ? 'active' : ''}`} onClick={() => setActivePage('register')}>
            Course Registration
          </button>
          <button className={`nav-item ${activePage === 'generate' ? 'active' : ''}`} onClick={() => setActivePage('generate')}>
            Generate Schedule
          </button>
          {scheduleResults.length > 0 && (
            <button className={`nav-item ${activePage === 'schedule' ? 'active' : ''}`} onClick={() => setActivePage('schedule')}>
              View Results
            </button>
          )}
        </nav>
        <div className="sidebar-footer">
          <button className="nav-item" onClick={logout}>Sign Out</button>
        </div>
      </aside>

      <main className="main-content">
        {msg && <div className="error-msg" style={{ marginBottom: 16, background: msg.includes('fail') || msg.includes('Failed') ? '#fef2f2' : '#ecfdf5', color: msg.includes('fail') || msg.includes('Failed') ? '#dc2626' : '#059669' }}>{msg}</div>}

        {generating && (
          <div className="generating-overlay">
            <div className="big-spinner"></div>
            <p>Generating optimal schedules using {algorithm}...</p>
          </div>
        )}

        {activePage === 'courses' && (
          <>
            <div className="page-header">
              <h1>Manage Courses</h1>
              <button className="btn btn-primary" onClick={openCreate}>+ New Course</button>
            </div>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{courses.filter(c => !c.is_archived).length}</div>
                <div className="stat-label">Active Courses</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{courses.reduce((sum, c) => sum + (c.sections?.length || 0), 0)}</div>
                <div className="stat-label">Total Sections</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{departments.length}</div>
                <div className="stat-label">Departments</div>
              </div>
            </div>
            <div className="filters">
              <select value={filterDept} onChange={e => setFilterDept(e.target.value)}>
                <option value="">All Departments</option>
                {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
            <div className="card">
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Name</th>
                      <th>Dept</th>
                      <th>Level</th>
                      <th>Credits</th>
                      <th>Sections</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
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
                          {(course.sections || []).map(s => (
                            <span key={s.id} className="badge badge-gray" style={{ marginRight: 4 }}>{s.section_id}</span>
                          ))}
                          <button className="btn btn-outline btn-sm" style={{ marginLeft: 4 }} onClick={() => openAddSection(course.id)}>+</button>
                        </td>
                        <td>
                          <span className={`badge ${course.is_archived ? 'badge-orange' : 'badge-green'}`}>
                            {course.is_archived ? 'Archived' : 'Active'}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 4 }}>
                            <button className="btn btn-outline btn-sm" onClick={() => openEdit(course)}>Edit</button>
                            <button className="btn btn-outline btn-sm" onClick={() => handleArchiveCourse(course)}>
                              {course.is_archived ? 'Restore' : 'Archive'}
                            </button>
                            <button className="btn btn-danger btn-sm" onClick={() => handleDeleteCourse(course.id)}>Delete</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {activePage === 'register' && (
          <>
            <div className="page-header">
              <h1>Course Registration</h1>
            </div>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{registrations.length}</div>
                <div className="stat-label">Registered Courses</div>
              </div>
            </div>
            <div className="card">
              <h3 style={{ marginBottom: 16 }}>My Registrations</h3>
              {registrations.length === 0 ? (
                <div className="empty-state"><p>No registrations yet.</p></div>
              ) : (
                <div className="table-container">
                  <table>
                    <thead><tr><th>Code</th><th>Name</th><th>Section</th><th>Action</th></tr></thead>
                    <tbody>
                      {registrations.map(r => (
                        <tr key={r.id}>
                          <td><strong>{r.course_code}</strong></td>
                          <td>{r.course_name}</td>
                          <td><span className="badge badge-gray">{r.section_id}</span></td>
                          <td><button className="btn btn-danger btn-sm" onClick={() => handleUnregister(r.id)}>Drop</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="card">
              <h3 style={{ marginBottom: 16 }}>Available Courses</h3>
              <div className="table-container">
                <table>
                  <thead><tr><th>Code</th><th>Name</th><th>Dept</th><th>Credits</th><th>Section</th><th>Action</th></tr></thead>
                  <tbody>
                    {courses.filter(c => !c.is_archived).map(course => (
                      <React.Fragment key={course.id}>
                        {(course.sections || []).filter(s => s.gender === user.gender).map(section => (
                          <tr key={section.id}>
                            <td><strong>{course.code}</strong></td>
                            <td>{course.name}</td>
                            <td><span className="badge badge-blue">{course.department_name}</span></td>
                            <td>{course.credits}</td>
                            <td><span className="badge badge-gray">{section.section_id}</span></td>
                            <td>
                              {registeredSectionIds.has(section.id) ? (
                                <button className="btn btn-danger btn-sm" onClick={() => handleUnregister(section.id)}>Drop</button>
                              ) : registeredCourseIds.has(course.id) ? (
                                <span className="badge badge-green">Enrolled</span>
                              ) : (
                                <button className="btn btn-primary btn-sm" onClick={() => handleRegister(section.id)}>Register</button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {activePage === 'generate' && (
          <>
            <div className="page-header">
              <h1>Generate Schedule</h1>
            </div>
            <div className="card">
              <h3 style={{ marginBottom: 16 }}>Algorithm</h3>
              <div className="algo-selector">
                <button className={`algo-btn ${algorithm === 'GA' ? 'active' : ''}`} onClick={() => setAlgorithm('GA')}>GA</button>
                <button className={`algo-btn ${algorithm === 'PSO' ? 'active' : ''}`} onClick={() => setAlgorithm('PSO')}>PSO</button>
              </div>
              {algorithm === 'GA' && (
                <>
                  <h3 style={{ marginBottom: 12, marginTop: 20 }}>Objective</h3>
                  <div className="algo-selector">
                    <button className={`algo-btn ${objective === 'instructor' ? 'active' : ''}`} onClick={() => setObjective('instructor')}>Instructor</button>
                    <button className={`algo-btn ${objective === 'student' ? 'active' : ''}`} onClick={() => setObjective('student')}>Student</button>
                    <button className={`algo-btn ${objective === 'university' ? 'active' : ''}`} onClick={() => setObjective('university')}>University</button>
                    <button className={`algo-btn ${objective === 'all' ? 'active' : ''}`} onClick={() => setObjective('all')}>All Three</button>
                  </div>
                </>
              )}
              <div style={{ marginTop: 24 }}>
                <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: 16 }}>
                  {registrations.length > 0
                    ? `Generate for ${registrations.length} registered course(s).`
                    : 'Register for courses first.'
                  }
                </p>
                <button className="btn btn-primary" onClick={handleGenerate} disabled={registrations.length === 0}>
                  {generating ? <><span className="spinner"></span> Generating...</> : 'Generate Schedule'}
                </button>
              </div>
            </div>
          </>
        )}

        {activePage === 'schedule' && scheduleResults.length > 0 && (
          <>
            <div className="page-header"><h1>Generated Schedules</h1></div>
            <div className="schedule-tabs">
              {scheduleResults.map((result, idx) => (
                <button key={idx} className={`schedule-tab ${selectedTab === idx ? 'active' : ''}`} onClick={() => setSelectedTab(idx)}>
                  <div className="tab-label">{result.label}</div>
                  <div className="tab-fitness">Fitness: {result.fitness} | Conflicts: {result.conflicts}</div>
                </button>
              ))}
            </div>
            <div className="card">
              <div className="card-header">
                <div>
                  <h3>{scheduleResults[selectedTab]?.label}</h3>
                  <p style={{ fontSize: '0.85rem', color: '#6b7280' }}>{scheduleResults[selectedTab]?.description}</p>
                </div>
              </div>
              <ScheduleCalendar slots={scheduleResults[selectedTab]?.slots || []} timeSlots={timeSlots} />
            </div>
          </>
        )}

        {showModal && (
          <div className="modal-overlay" onClick={() => setShowModal(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <h2>{editCourse ? 'Edit Course' : 'New Course'}</h2>
              <form onSubmit={handleCreateCourse}>
                {!editCourse && (
                  <div className="form-row">
                    <div className="form-group">
                      <label>Course Code</label>
                      <input type="text" value={courseForm.code} onChange={e => setCourseForm({...courseForm, code: e.target.value})} required />
                    </div>
                    <div className="form-group">
                      <label>Department</label>
                      <select value={courseForm.department_id} onChange={e => setCourseForm({...courseForm, department_id: e.target.value})} required>
                        <option value="">Select...</option>
                        {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                      </select>
                    </div>
                  </div>
                )}
                <div className="form-group">
                  <label>Course Name</label>
                  <input type="text" value={courseForm.name} onChange={e => setCourseForm({...courseForm, name: e.target.value})} required />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Level</label>
                    <select value={courseForm.level} onChange={e => setCourseForm({...courseForm, level: parseInt(e.target.value)})}>
                      {[1,2,3,4,5,6,7,8].map(l => <option key={l} value={l}>Level {l}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Credits</label>
                    <select value={courseForm.credits} onChange={e => setCourseForm({...courseForm, credits: parseInt(e.target.value)})}>
                      {[1,2,3,4].map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                </div>
                <div className="form-group">
                  <label>
                    <input type="checkbox" checked={courseForm.is_lab} onChange={e => setCourseForm({...courseForm, is_lab: e.target.checked})} style={{ marginRight: 8 }} />
                    This is a lab course
                  </label>
                </div>
                <div className="modal-actions">
                  <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>Cancel</button>
                  <button type="submit" className="btn btn-primary">{editCourse ? 'Update' : 'Create'}</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {showSectionModal && (
          <div className="modal-overlay" onClick={() => setShowSectionModal(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <h2>Add Section</h2>
              <form onSubmit={handleCreateSection}>
                <div className="form-group">
                  <label>Section ID (e.g., CS101-M5)</label>
                  <input type="text" value={sectionForm.section_id} onChange={e => setSectionForm({...sectionForm, section_id: e.target.value})} required />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Gender</label>
                    <select value={sectionForm.gender} onChange={e => setSectionForm({...sectionForm, gender: e.target.value})}>
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Capacity</label>
                    <input type="number" value={sectionForm.capacity} onChange={e => setSectionForm({...sectionForm, capacity: parseInt(e.target.value)})} min={1} />
                  </div>
                </div>
                <div className="modal-actions">
                  <button type="button" className="btn btn-outline" onClick={() => setShowSectionModal(false)}>Cancel</button>
                  <button type="submit" className="btn btn-primary">Create Section</button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
