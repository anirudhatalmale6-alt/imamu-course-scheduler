/**
 * ScheduleCalendar.js - Weekly Calendar Grid Component
 *
 * This component renders a visual weekly schedule as a grid/table.
 * It displays course slots arranged by day (columns: Sun-Thu, matching
 * the Saudi/IMAMU academic week) and time period (rows).
 *
 * Features:
 *   - Each course is automatically assigned a unique color from a
 *     10-color palette for easy visual distinction.
 *   - Each cell shows the course code, name, room, and instructor.
 *   - Time slots can come from the backend (timeSlots prop) or fall
 *     back to slots found in the data or hardcoded defaults.
 *   - Multiple courses in the same day/time cell are stacked vertically
 *     (this indicates a scheduling conflict).
 *
 * Props:
 *   - slots: Array of schedule slot objects, each with { day, time,
 *            course_code, course_name, room, instructor_name }
 *   - timeSlots: Array of time slot definitions from the backend
 *                (used to determine which rows to display)
 */

import React from 'react';

// Days of the academic week at IMAMU (Sunday through Thursday)
const DAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU'];
// Mapping from short day codes to full names for the column headers
const DAY_NAMES = { SUN: 'Sunday', MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday', THU: 'Thursday' };

export default function ScheduleCalendar({ slots = [], timeSlots = [] }) {
  // Collect unique time values from the slots data, sorted chronologically
  const usedTimes = [...new Set(slots.map(s => s.time))].sort();

  /**
   * Determine which time periods to display as rows.
   * Priority order:
   *   1. Backend-provided timeSlots (most accurate)
   *   2. Times actually used in the schedule data
   *   3. Hardcoded default time periods as a last resort
   */
  const displayTimes = timeSlots.length > 0
    ? timeSlots.map(t => t.label || t)
    : (usedTimes.length > 0 ? usedTimes : ['08:25-09:15', '09:20-10:10', '10:15-11:05', '11:10-12:00', '12:30-13:20', '13:25-14:15', '14:20-15:10', '15:40-16:30', '16:35-17:25']);

  /**
   * getSlotForCell - Returns all schedule slots that match a given day and time.
   * Returns an array because multiple courses could be scheduled in the same
   * cell (which represents a conflict the algorithm tries to minimize).
   */
  const getSlotForCell = (day, time) => {
    return slots.filter(s => s.day === day && s.time === time);
  };

  // Color assignment map: tracks which color has been assigned to each course code
  const colors = {};
  let colorIdx = 0;

  // A palette of 10 visually distinct color schemes (background, left border, text)
  const palette = [
    { bg: '#dbeafe', border: '#2563eb', text: '#1e40af' },  // Blue
    { bg: '#dcfce7', border: '#16a34a', text: '#166534' },  // Green
    { bg: '#fef3c7', border: '#d97706', text: '#92400e' },  // Amber
    { bg: '#f3e8ff', border: '#7c3aed', text: '#5b21b6' },  // Purple
    { bg: '#ffe4e6', border: '#e11d48', text: '#9f1239' },  // Rose
    { bg: '#e0f2fe', border: '#0284c7', text: '#075985' },  // Sky
    { bg: '#fce7f3', border: '#db2777', text: '#9d174d' },  // Pink
    { bg: '#ecfdf5', border: '#059669', text: '#065f46' },  // Emerald
    { bg: '#fff7ed', border: '#ea580c', text: '#9a3412' },  // Orange
    { bg: '#f5f3ff', border: '#6d28d9', text: '#4c1d95' },  // Violet
  ];

  /**
   * getColor - Assigns a consistent color to each unique course code.
   * The first course seen gets palette[0], the second gets palette[1], etc.
   * Colors wrap around using modulo if there are more than 10 courses.
   */
  const getColor = (courseCode) => {
    if (!colors[courseCode]) {
      colors[courseCode] = palette[colorIdx % palette.length];
      colorIdx++;
    }
    return colors[courseCode];
  };

  return (
    <div className="schedule-calendar">
      {/* CSS Grid layout: first column is time labels, remaining columns are days */}
      <div className="calendar-grid" style={{ '--days': DAYS.length }}>
        {/* Header row: "Time" label followed by day names */}
        <div className="calendar-header">Time</div>
        {DAYS.map(d => (
          <div key={d} className="calendar-header">{DAY_NAMES[d] || d}</div>
        ))}

        {/* Body rows: one row per time slot */}
        {displayTimes.map(time => (
          <React.Fragment key={time}>
            {/* Time label cell (leftmost column) */}
            <div className="calendar-time">{time}</div>

            {/* One cell per day for this time slot */}
            {DAYS.map(day => {
              // Find any courses scheduled at this day + time combination
              const cellSlots = getSlotForCell(day, time);
              return (
                <div key={`${day}-${time}`} className="calendar-cell">
                  {/* Render each scheduled course as a colored event card */}
                  {cellSlots.map((slot, i) => {
                    const color = getColor(slot.course_code);
                    return (
                      <div key={i} className="calendar-event" style={{
                        background: color.bg,
                        borderLeftColor: color.border,
                      }}>
                        {/* Course code (bold, colored) */}
                        <div className="event-course" style={{ color: color.text }}>
                          {slot.course_code}
                        </div>
                        {/* Course name */}
                        <div className="event-detail">{slot.course_name}</div>
                        {/* Room and instructor info */}
                        <div className="event-detail">{slot.room} | {slot.instructor_name}</div>
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
