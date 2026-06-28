import React from 'react';
import { X } from 'lucide-react';

const ROUTING_COLORS = {
  auto_accept: 'var(--lime)',
  flag_for_review: 'var(--yellow)',
  reject: 'var(--pink)',
};

const ROUTING_LABELS = {
  auto_accept: 'AUTO ACCEPT',
  flag_for_review: 'FLAG FOR REVIEW',
  reject: 'REJECT',
};

export default function PatientDetail({ patient, onClose }) {
  if (!patient) return null;
  const p = patient;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.85)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 24,
        animation: 'fadeInUp 0.3s ease-out',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--bg-card)',
          border: '3px solid #444',
          borderRadius: 'var(--radius)',
          boxShadow: '8px 8px 0px rgba(255,255,255,0.1)',
          width: '100%',
          maxWidth: 720,
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '22px 28px',
          borderBottom: '3px solid #333',
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          background: ROUTING_COLORS[p.routing_decision] || '#333',
          color: 'var(--black)',
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <h2 style={{ fontSize: 28, fontWeight: 800 }}>{p.name}</h2>
              <span style={{
                fontFamily: "'Space Mono', monospace",
                fontSize: 16,
                fontWeight: 700,
                background: 'rgba(255,255,255,0.9)',
                border: '2px solid var(--black)',
                borderRadius: 8,
                padding: '4px 12px',
              }}>
                {p.patient_id}
              </span>
            </div>
            <span style={{
              fontWeight: 800,
              fontSize: 16,
              letterSpacing: '0.1em',
              background: 'rgba(255,255,255,0.9)',
              border: '2px solid var(--black)',
              borderRadius: 8,
              padding: '5px 14px',
              textTransform: 'uppercase',
            }}>
              {ROUTING_LABELS[p.routing_decision] || p.routing_decision}
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255,255,255,0.9)',
              border: '2px solid var(--black)',
              borderRadius: 10,
              padding: 10,
              cursor: 'pointer',
              boxShadow: '3px 3px 0px rgba(0,0,0,0.2)',
              display: 'flex',
            }}
          >
            <X size={22} />
          </button>
        </div>

        {/* Reason */}
        <div style={{
          padding: '18px 28px',
          borderBottom: '1px solid #222',
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--gray)', marginBottom: 8 }}>
            Routing Reason
          </div>
          <p style={{ fontSize: 18, lineHeight: 1.6, color: 'var(--white)', fontWeight: 500 }}>
            {p.reason || 'No reason provided.'}
          </p>
        </div>

        {/* Details Grid */}
        <div style={{ padding: '22px 28px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
          <Card title="🩺 Wound Info" color="var(--lavender)">
            <Row label="Type" value={p.wound_type} />
            <Row label="Stage" value={p.wound_stage} />
            <Row label="Location" value={p.wound_location} />
            <Row label="Drainage" value={p.drainage_amount} />
          </Card>

          <Card title="📏 Measurements" color="var(--cyan)">
            <Row label="Length" value={p.length_cm ? `${p.length_cm} cm` : null} />
            <Row label="Width" value={p.width_cm ? `${p.width_cm} cm` : null} />
            <Row label="Depth" value={p.depth_cm != null ? `${p.depth_cm} cm` : null} />
            <div style={{ marginTop: 8, padding: '8px 12px', background: '#111', borderRadius: 8, fontFamily: "'Space Mono', monospace", fontSize: 18, fontWeight: 700, textAlign: 'center', color: 'var(--cyan)' }}>
              {p.length_cm && p.width_cm ? `${p.length_cm} × ${p.width_cm}${p.depth_cm != null ? ` × ${p.depth_cm}` : ''} cm` : '—'}
            </div>
          </Card>

          <Card title="🛡️ Coverage" color="var(--mint)">
            <Row label="Medicare B" value={p.has_mcb_coverage ? '✅ Active' : '❌ Not Active'} />
            <Row label="Facility" value={`Facility ${String.fromCharCode(64 + (p.facility_id - 100))}`} />
            <Row label="ICD-10" value={p.icd10_codes?.join(', ') || null} />
          </Card>

          <Card title="🔍 Extraction" color="var(--orange)">
            <Row label="Source" value={p.extraction_source} />
            <Row label="Format" value={p.note_format} />
            <Row label="Assessment" value={p.last_assessment_date} />
          </Card>
        </div>

        {/* Clinical Note */}
        {p.note_text && (
          <div style={{ padding: '0 28px 24px' }}>
            <div style={{
              background: '#0A0A0A',
              border: '2px solid #333',
              borderRadius: 'var(--radius)',
              padding: 18,
            }}>
              <div style={{ fontSize: 12, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--gray)', marginBottom: 10 }}>
                📄 Clinical Note
              </div>
              <pre style={{
                fontFamily: "'Space Mono', monospace",
                fontSize: 13,
                color: '#bbb',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                lineHeight: 1.7,
                margin: 0,
                maxHeight: 200,
                overflowY: 'auto',
              }}>
                {p.note_text}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Card({ title, color, children }) {
  return (
    <div style={{
      border: `2px solid ${color}`,
      borderRadius: 12,
      overflow: 'hidden',
      boxShadow: `4px 4px 0px ${color}33`,
    }}>
      <div style={{
        background: color,
        padding: '10px 14px',
        borderBottom: `2px solid ${color}`,
        fontSize: 14,
        fontWeight: 800,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--black)',
      }}>
        {title}
      </div>
      <div style={{ padding: '12px 14px' }}>
        {children}
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', fontSize: 15 }}>
      <span style={{ color: 'var(--gray)', fontWeight: 500 }}>{label}</span>
      <span style={{ fontWeight: 700, color: value ? 'var(--white)' : '#444' }}>
        {value != null ? String(value) : '—'}
      </span>
    </div>
  );
}
