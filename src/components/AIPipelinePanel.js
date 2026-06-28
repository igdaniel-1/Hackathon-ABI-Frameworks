import React, { useRef, useEffect } from 'react';
import { Play, RotateCcw } from 'lucide-react';

const PHASES = [
  { key: 'ingesting', label: 'Ingest', icon: '📡', color: 'var(--cyan)' },
  { key: 'enriching', label: 'Extract', icon: '🧠', color: 'var(--yellow)' },
  { key: 'complete', label: 'Done', icon: '✅', color: 'var(--lime)' },
];

const LOG_COLORS = {
  info: '#9ca3af',
  success: '#6ee7b7',
  warn: '#fcd34d',
  error: '#ff6b6b',
};

export default function AIPipelinePanel({ logs, phase, mode, loading, onRun, resultCount }) {
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '3px solid #333',
      borderRadius: 'var(--radius)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      maxHeight: 'calc(100vh - 200px)',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '2px solid #333',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        background: mode === 'autonomous' ? 'var(--lime)' : 'var(--yellow)',
        color: 'var(--black)',
      }}>
        <span style={{ fontSize: 24 }}>🤖</span>
        <span style={{ fontWeight: 800, fontSize: 18, flex: 1, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
          AI Pipeline {mode === 'autonomous' ? '(Auto)' : '(Manual)'}
        </span>
        {loading && (
          <div style={{
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: 'var(--red)',
            border: '2px solid var(--black)',
            animation: 'pulse 0.8s ease-in-out infinite',
          }} />
        )}
      </div>

      {/* Phase Progress */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #222' }}>
        <div style={{ display: 'flex', gap: 10 }}>
          {PHASES.map(({ key, label, icon, color }, i) => {
            const phaseIdx = PHASES.findIndex(p => p.key === phase);
            const isDone = phase === 'complete' || phaseIdx > i;
            const isActive = key === phase;

            return (
              <div key={key} style={{
                flex: 1,
                padding: '12px 10px',
                border: isActive ? '2px solid var(--white)' : isDone ? `2px solid ${color}` : '2px solid #333',
                borderRadius: 10,
                background: isDone || isActive ? color : '#111',
                boxShadow: isActive ? `3px 3px 0px ${color}44` : 'none',
                textAlign: 'center',
                color: isDone || isActive ? 'var(--black)' : '#555',
                transition: 'all 0.3s',
              }}>
                <div style={{ fontSize: 22, marginBottom: 2 }}>{icon}</div>
                <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  {label}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Run Button */}
      {mode === 'manual' && (
        <div style={{ padding: '14px 20px', borderBottom: '1px solid #222' }}>
          <button
            onClick={onRun}
            disabled={loading}
            style={{
              width: '100%',
              padding: '12px',
              background: loading ? '#222' : 'var(--cyan)',
              border: '2px solid ' + (loading ? '#333' : 'var(--white)'),
              borderRadius: 10,
              boxShadow: loading ? 'none' : '3px 3px 0px rgba(0,212,255,0.3)',
              fontFamily: 'inherit',
              fontWeight: 800,
              fontSize: 16,
              cursor: loading ? 'not-allowed' : 'pointer',
              color: loading ? '#555' : 'var(--black)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              transition: 'transform 0.1s, box-shadow 0.1s',
            }}
            onMouseDown={e => { if (!loading) { e.currentTarget.style.transform = 'translate(3px, 3px)'; e.currentTarget.style.boxShadow = 'none'; }}}
            onMouseUp={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '3px 3px 0px rgba(0,212,255,0.3)'; }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '3px 3px 0px rgba(0,212,255,0.3)'; }}
          >
            {loading ? <RotateCcw size={16} className="spin" /> : <Play size={16} />}
            {loading ? 'Processing...' : resultCount > 0 ? 'Re-run' : 'Run Pipeline'}
          </button>
        </div>
      )}

      {/* Log Stream */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '14px 16px',
        background: '#0A0A0A',
        fontFamily: "'Space Mono', monospace",
        fontSize: 12,
        lineHeight: 1.8,
        minHeight: 240,
        borderTop: '2px solid #1a1a1a',
      }}>
        {logs.length === 0 ? (
          <div style={{ color: '#333', textAlign: 'center', padding: 30, fontSize: 14 }}>
            {mode === 'autonomous' ? '⚡ Auto-running...' : '▶ Click Run to start'}
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} style={{
              animation: `fadeInUp 0.2s ease-out`,
              paddingLeft: 4,
            }}>
              <span style={{ color: '#333' }}>{log.ts}</span>{' '}
              <span style={{ color: LOG_COLORS[log.type] || '#666' }}>{log.msg}</span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
