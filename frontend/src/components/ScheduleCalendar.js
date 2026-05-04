import React from 'react';

const DAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU'];
const DAY_NAMES = { SUN: 'Sunday', MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday', THU: 'Thursday' };

export default function ScheduleCalendar({ slots = [], timeSlots = [] }) {
  const usedTimes = [...new Set(slots.map(s => s.time))].sort();
  const displayTimes = timeSlots.length > 0
    ? timeSlots.map(t => t.label || t)
    : (usedTimes.length > 0 ? usedTimes : ['08:25-09:15', '09:20-10:10', '10:15-11:05', '11:10-12:00', '12:30-13:20', '13:25-14:15', '14:20-15:10', '15:40-16:30', '16:35-17:25']);

  const getSlotForCell = (day, time) => {
    return slots.filter(s => s.day === day && s.time === time);
  };

  const colors = {};
  let colorIdx = 0;
  const palette = [
    { bg: '#dbeafe', border: '#2563eb', text: '#1e40af' },
    { bg: '#dcfce7', border: '#16a34a', text: '#166534' },
    { bg: '#fef3c7', border: '#d97706', text: '#92400e' },
    { bg: '#f3e8ff', border: '#7c3aed', text: '#5b21b6' },
    { bg: '#ffe4e6', border: '#e11d48', text: '#9f1239' },
    { bg: '#e0f2fe', border: '#0284c7', text: '#075985' },
    { bg: '#fce7f3', border: '#db2777', text: '#9d174d' },
    { bg: '#ecfdf5', border: '#059669', text: '#065f46' },
    { bg: '#fff7ed', border: '#ea580c', text: '#9a3412' },
    { bg: '#f5f3ff', border: '#6d28d9', text: '#4c1d95' },
  ];

  const getColor = (courseCode) => {
    if (!colors[courseCode]) {
      colors[courseCode] = palette[colorIdx % palette.length];
      colorIdx++;
    }
    return colors[courseCode];
  };

  return (
    <div className="schedule-calendar">
      <div className="calendar-grid" style={{ '--days': DAYS.length }}>
        <div className="calendar-header">Time</div>
        {DAYS.map(d => (
          <div key={d} className="calendar-header">{DAY_NAMES[d] || d}</div>
        ))}
        {displayTimes.map(time => (
          <React.Fragment key={time}>
            <div className="calendar-time">{time}</div>
            {DAYS.map(day => {
              const cellSlots = getSlotForCell(day, time);
              return (
                <div key={`${day}-${time}`} className="calendar-cell">
                  {cellSlots.map((slot, i) => {
                    const color = getColor(slot.course_code);
                    return (
                      <div key={i} className="calendar-event" style={{
                        background: color.bg,
                        borderLeftColor: color.border,
                      }}>
                        <div className="event-course" style={{ color: color.text }}>
                          {slot.course_code}
                        </div>
                        <div className="event-detail">{slot.course_name}</div>
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
