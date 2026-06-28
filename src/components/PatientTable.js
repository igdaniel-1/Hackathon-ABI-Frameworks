import React, { useState, useMemo } from 'react';
import { Search, ChevronUp, ChevronDown } from 'lucide-react';

const ROUTING_CONFIG = {
  auto_accept: { bg: 'var(--lime)', label: 'ACCEPT', textColor: '#000' },
  flag_for_review: { bg: 'var(--yellow)', label: 'REVIEW', textColor: '#000' },
  reject: { bg: 'var(--pink)', label: 'REJECT', textColor: '#000' },
};

function RoutingBadge({ decision }) {
  const c = ROUTING_CONFIG[decision] || { bg: '#333', label: decision, textColor: '#fff' };
  return (
    <span style={{
      display: 'inline-block',
      background: c.bg,
      border: '2px solid var(--white)',
      borderRadius: 8,
      padding: '6px 14px',
      fontSize: 14,
      fontWeight: 800,
      letterSpacing: '0.08em',
      fontFamily: "'Space Mono', monospace",
      color: c.textColor,
      textTransform: 'uppercase',
    }}>
      {c.label}
    </span>
  );
}

export default function PatientTable({ results, onSelectPatient }) {
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [routingFilter, setRoutingFilter] = useState('all');

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  };

  const filtered = useMemo(() => {
    return results
      .filter(r => {
        const q = search.toLowerCase();
        const matchSearch = !q ||
          r.patient_id.toLowerCase().includes(q) ||
          r.name.toLowerCase().includes(q) ||
          (r.wound_type || '').toLowerCase().includes(q);
        const matchRouting = routingFilter === 'all' || r.routing_decision === routingFilter;
        return matchSearch && matchRouting;
      })
      .sort((a, b) => {
        if (!sortKey) return 0;
        const av = String(a[sortKey] || '');
        const bv = String(b[sortKey] || '');
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      });
  }, [results, search, sortKey, sortDir, routingFilter]);

  const SortHeader = ({ field, children }) => {
    const active = sortKey === field;
    return (
      <th onClick={() => handleSort(field)} style={{
        padding: '14px 18px',
        textAlign: 'left',
        fontSize: 14,
        fontWeight: 700,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        cursor: 'pointer',
        userSelect: 'none',
        borderBottom: '2px solid #333',
        color: active ? 'var(--cyan)' : 'var(--gray)',
        whiteSpace: 'nowrap',
        background: 'var(--bg-card)',
      }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {children}
          {active && (sortDir === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
        </span>
      </th>
    );
  };

  const filterButtons = [
    { key: 'all', label: 'ALL', color: 'var(--cyan)' },
    { key: 'auto_accept', label: 'ACCEPT', color: 'var(--lime)' },
    { key: 'flag_for_review', label: 'REVIEW', color: 'var(--yellow)' },
    { key: 'reject', label: 'REJECT', color: 'var(--pink)' },
  ];

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '3px solid #333',
      borderRadius: 'var(--radius)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '18px 22px',
        borderBottom: '2px solid #333',
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        flexWrap: 'wrap',
      }}>
        <h3 style={{
          fontSize: 22,
          fontWeight: 800,
          flex: 1,
          minWidth: 140,
          color: 'var(--white)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          🎯 Patient Routing
          <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--gray)' }}>
            {filtered.length}/{results.length}
          </span>
        </h3>

        <div style={{ display: 'flex', gap: 8 }}>
          {filterButtons.map(f => (
            <button
              key={f.key}
              onClick={() => setRoutingFilter(f.key)}
              style={{
                padding: '8px 18px',
                border: routingFilter === f.key ? '2px solid var(--white)' : '2px solid #333',
                borderRadius: 10,
                background: routingFilter === f.key ? f.color : 'transparent',
                boxShadow: routingFilter === f.key ? `3px 3px 0px ${f.color}44` : 'none',
                fontFamily: 'inherit',
                fontWeight: 700,
                fontSize: 14,
                cursor: 'pointer',
                color: routingFilter === f.key ? 'var(--black)' : 'var(--gray)',
                letterSpacing: '0.05em',
                transition: 'all 0.15s',
              }}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div style={{ position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#555' }} />
          <input
            type="text"
            placeholder="Search..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              padding: '10px 14px 10px 36px',
              border: '2px solid #333',
              borderRadius: 10,
              fontFamily: 'inherit',
              fontSize: 16,
              width: 200,
              background: '#111',
              color: 'var(--white)',
              outline: 'none',
            }}
          />
        </div>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', maxHeight: 'calc(100vh - 360px)', overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ position: 'sticky', top: 0, zIndex: 2 }}>
            <tr>
              <SortHeader field="patient_id">ID</SortHeader>
              <SortHeader field="name">Patient</SortHeader>
              <SortHeader field="wound_type">Wound</SortHeader>
              <SortHeader field="routing_decision">Routing</SortHeader>
              <SortHeader field="has_mcb_coverage">MCB</SortHeader>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: 48, textAlign: 'center', color: '#555', fontSize: 18 }}>
                  No patients match filters.
                </td>
              </tr>
            ) : (
              filtered.map((r, i) => (
                <tr
                  key={r.patient_id}
                  onClick={() => onSelectPatient(r)}
                  style={{
                    borderBottom: '1px solid #222',
                    cursor: 'pointer',
                    transition: 'background 0.15s',
                    animation: `slideInRow 0.3s ease-out ${Math.min(i * 0.05, 1)}s both`,
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = '#252525'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ padding: '14px 18px', fontFamily: "'Space Mono', monospace", fontSize: 16, fontWeight: 700, color: 'var(--cyan)' }}>
                    {r.patient_id}
                  </td>
                  <td style={{ padding: '14px 18px', fontSize: 18, fontWeight: 600 }}>
                    {r.name}
                  </td>
                  <td style={{ padding: '14px 18px', fontSize: 16 }}>
                    {r.wound_type ? (
                      <span>
                        {r.wound_type}
                        {r.wound_stage != null && <span style={{ color: 'var(--orange)', fontWeight: 700 }}> S{r.wound_stage}</span>}
                        {r.wound_location && <span style={{ color: 'var(--gray)', fontSize: 13 }}> · {r.wound_location}</span>}
                      </span>
                    ) : (
                      <span style={{ color: '#444' }}>No wound data</span>
                    )}
                  </td>
                  <td style={{ padding: '14px 18px' }}>
                    <RoutingBadge decision={r.routing_decision} />
                  </td>
                  <td style={{ padding: '14px 18px' }}>
                    <span style={{
                      display: 'inline-block',
                      padding: '5px 12px',
                      borderRadius: 8,
                      fontSize: 14,
                      fontWeight: 800,
                      background: r.has_mcb_coverage ? 'var(--mint)' : '#2a2a2a',
                      color: r.has_mcb_coverage ? 'var(--black)' : '#555',
                      border: r.has_mcb_coverage ? '2px solid var(--white)' : '2px solid #333',
                    }}>
                      {r.has_mcb_coverage ? 'YES' : 'NO'}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
