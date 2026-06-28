import React, { useState, useEffect } from 'react';

function AnimatedNumber({ target, duration = 1200 }) {
  const [current, setCurrent] = useState(0);
  useEffect(() => {
    if (target === 0) { setCurrent(0); return; }
    const start = Date.now();
    const tick = () => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.round(eased * target));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [target, duration]);
  return <span>{current}</span>;
}

export default function StatsBar({ results }) {
  const total = results.length;
  const accepted = results.filter(r => r.routing_decision === 'auto_accept').length;
  const review = results.filter(r => r.routing_decision === 'flag_for_review').length;
  const rejected = results.filter(r => r.routing_decision === 'reject').length;

  const stats = [
    { label: 'TOTAL', value: total, color: 'var(--cyan)', icon: '📊' },
    { label: 'AUTO ACCEPT', value: accepted, color: 'var(--lime)', icon: '✅' },
    { label: 'REVIEW', value: review, color: 'var(--yellow)', icon: '⚠️' },
    { label: 'REJECTED', value: rejected, color: 'var(--pink)', icon: '❌' },
  ];

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 20,
      marginBottom: 24,
    }}>
      {stats.map(({ label, value, color, icon }, i) => (
        <div key={label} style={{
          background: color,
          border: '3px solid var(--white)',
          borderRadius: 'var(--radius)',
          boxShadow: `5px 5px 0px ${color}44`,
          padding: '20px 24px',
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          animation: `fadeInUp 0.5s ease-out ${i * 0.1}s both`,
          color: 'var(--black)',
        }}>
          <div style={{ fontSize: 40 }}>{icon}</div>
          <div>
            <div style={{
              fontSize: 48,
              fontWeight: 800,
              lineHeight: 1,
              animation: 'countUp 0.5s ease-out',
            }}>
              <AnimatedNumber target={value} />
            </div>
            <div style={{
              fontSize: 14,
              fontWeight: 700,
              marginTop: 4,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              opacity: 0.7,
            }}>{label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
