import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { courseAPI, registrationAPI, scheduleAPI, dataAPI } from '../services/api';
import ScheduleCalendar from '../components/ScheduleCalendar';

export default function StudentDashboard() {
  const { user, logout } = useAuth();
  const [activePage, setActivePage] = useState('courses');
  const [courses, setCourses] = useState([]);
  const [registrations, setRegistrations] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [scheduleResults, setScheduleResults] = useState([]);
  const [savedSchedules, setSavedSchedules] = useState([]);
  const [selectedTab, setSelectedTab] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [algorithm, setAlgorithm] = useState('GA');
  const [objective, setObjective] = useState('student');
  const [filterDept, setFilterDept] = useState('');
  const [filterLevel, setFilterLevel] = useState('');
  const [timeSlots, setTimeSlots] = useState([]);
  const [msg, setMsg] = useState('');

  const loadData = useCallback(async () => {
    try {
      const [coursesRes, regRes, deptRes, tsRes] = await Promise.all([
        courseAPI.list(),
        registrationAPI.myRegistrations(),
        dataAPI.departments(),
        dataAPI.timeslots(),
      ]);
      setCourses(coursesRes.data);
      setRegistrations(regRes.data);
      setDepartments(deptRes.data);
      setTimeSlots(tsRes.data.filter(t => t.slot_type === 'Class'));
    } catch (err) { console.error(err); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const loadSaved = async () => {
    try {
      const res = await scheduleAPI.getSaved();
      setSavedSchedules(res.data);
    } catch (err) { console.error(err); }
  };

  useEffect(() => {
    if (activePage === 'saved') loadSaved();
  }, [activePage]);

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
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Failed');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const handleGenerate = async () => {
    const courseIds = [...new Set(registrations.map(r => r.course_id))];
    if (courseIds.length === 0) {
      setMsg('Please register for courses first');
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

  const handleSave = async (result) => {
    try {
      await scheduleAPI.save({
        name: `${result.label} - ${new Date().toLocaleDateString()}`,
        algorithm,
        objective: result.objective,
        fitness: result.fitness,
        conflicts: result.conflicts,
        schedule_data: JSON.stringify(result.slots),
      });
      setMsg('Schedule saved!');
      setTimeout(() => setMsg(''), 2000);
    } catch (err) {
      setMsg('Failed to save');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const handleDeleteSaved = async (id) => {
    try {
      await scheduleAPI.deleteSaved(id);
      loadSaved();
    } catch (err) { console.error(err); }
  };

  const registeredSectionIds = new Set(registrations.map(r => r.section_id || r.id));
  const registeredCourseIds = new Set(registrations.map(r => r.course_id));

  const filteredCourses = courses.filter(c => {
    if (filterDept && c.department_id !== parseInt(filterDept)) return false;
    if (filterLevel && c.level !== parseInt(filterLevel)) return false;
    return true;
  });

  return (
    <div className="dashboard">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>IMAMU Scheduler</h2>
          <span className="role-badge role-student">Student</span>
          <div style={{ marginTop: 8, fontSize: '0.8rem', opacity: 0.7 }}>{user.full_name}</div>
        </div>
        <nav className="sidebar-nav">
          <button className={`nav-item ${activePage === 'courses' ? 'active' : ''}`} onClick={() => setActivePage('courses')}>
            Browse Courses
          </button>
          <button className={`nav-item ${activePage === 'registered' ? 'active' : ''}`} onClick={() => setActivePage('registered')}>
            My Registrations ({registrations.length})
          </button>
          <button className={`nav-item ${activePage === 'generate' ? 'active' : ''}`} onClick={() => setActivePage('generate')}>
            Generate Schedule
          </button>
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
        {msg && <div className="error-msg" style={{ marginBottom: 16, background: msg.includes('fail') || msg.includes('Please') ? '#fef2f2' : '#ecfdf5', color: msg.includes('fail') || msg.includes('Please') ? '#dc2626' : '#059669' }}>{msg}</div>}

        {generating && (
          <div className="generating-overlay">
            <div className="big-spinner"></div>
            <p>Generating optimal schedules using {algorithm}...</p>
            <p style={{ fontSize: '0.85rem', opacity: 0.7, marginTop: 8 }}>This may take a moment</p>
          </div>
        )}

        {activePage === 'courses' && (
          <>
            <div className="page-header">
              <h1>Browse Courses</h1>
            </div>
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
                      <th>Sections</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCourses.map(course => (
                      <React.Fragment key={course.id}>
                        {(course.sections || []).filter(s => s.gender === user.gender).map(section => (
                          <tr key={section.id}>
                            <td><strong>{course.code}</strong></td>
                            <td>{course.name}</td>
                            <td><span className="badge badge-blue">{course.department_name}</span></td>
                            <td>Level {course.level}</td>
                            <td>{course.credits}</td>
                            <td>
                              <span className="badge badge-gray">{section.section_id}</span>
                              <span style={{ fontSize: '0.75rem', color: '#6b7280', marginLeft: 4 }}>
                                ({section.enrolled}/{section.capacity})
                              </span>
                            </td>
                            <td>
                              {registeredSectionIds.has(section.id) ? (
                                <button className="btn btn-danger btn-sm" onClick={() => handleUnregister(section.id)}>Drop</button>
                              ) : registeredCourseIds.has(course.id) ? (
                                <span className="badge badge-green">Enrolled (other section)</span>
                              ) : (
                                <button className="btn btn-primary btn-sm" onClick={() => handleRegister(section.id)}>Register</button>
                              )}
                            </td>
                          </tr>
                        ))}
                        {(course.sections || []).filter(s => s.gender === user.gender).length === 0 && (
                          <tr key={course.id}>
                            <td><strong>{course.code}</strong></td>
                            <td>{course.name}</td>
                            <td><span className="badge badge-blue">{course.department_name}</span></td>
                            <td>Level {course.level}</td>
                            <td>{course.credits}</td>
                            <td><span className="badge badge-orange">No sections for {user.gender}</span></td>
                            <td>-</td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {activePage === 'registered' && (
          <>
            <div className="page-header">
              <h1>My Registrations</h1>
            </div>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{registrations.length}</div>
                <div className="stat-label">Registered Courses</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{registrations.reduce((sum, r) => sum + (courses.find(c => c.id === r.course_id)?.credits || 3), 0)}</div>
                <div className="stat-label">Total Credits</div>
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

        {activePage === 'generate' && (
          <>
            <div className="page-header">
              <h1>Generate Schedule</h1>
            </div>
            <div className="card">
              <h3 style={{ marginBottom: 16 }}>Algorithm Selection</h3>
              <div className="algo-selector">
                <button className={`algo-btn ${algorithm === 'GA' ? 'active' : ''}`} onClick={() => setAlgorithm('GA')}>
                  Genetic Algorithm (GA)
                </button>
                <button className={`algo-btn ${algorithm === 'PSO' ? 'active' : ''}`} onClick={() => setAlgorithm('PSO')}>
                  Particle Swarm (PSO)
                </button>
              </div>
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
                <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: 16 }}>
                  {registrations.length > 0
                    ? `Will generate schedules for your ${registrations.length} registered course(s).`
                    : 'You need to register for courses first before generating a schedule.'
                  }
                </p>
                <button className="btn btn-primary" onClick={handleGenerate} disabled={registrations.length === 0 || generating}>
                  {generating ? <><span className="spinner"></span> Generating...</> : 'Generate Schedule'}
                </button>
              </div>
            </div>
          </>
        )}

        {activePage === 'schedule' && scheduleResults.length > 0 && (
          <>
            <div className="page-header">
              <h1>Generated Schedules</h1>
            </div>
            <div className="schedule-tabs">
              {scheduleResults.map((result, idx) => (
                <button key={idx} className={`schedule-tab ${selectedTab === idx ? 'active' : ''}`} onClick={() => setSelectedTab(idx)}>
                  <div className="tab-rank">#{result.rank}</div>
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
                <button className="btn btn-success btn-sm" onClick={() => handleSave(scheduleResults[selectedTab])}>
                  Save This Schedule
                </button>
              </div>
              <ScheduleCalendar slots={scheduleResults[selectedTab]?.slots || []} timeSlots={timeSlots} />
            </div>
          </>
        )}

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
