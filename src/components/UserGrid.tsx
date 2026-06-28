import React,{ useState } from 'react';

// ─── Sample data ────────────────────────────────────────────────────────────
const USER_DATA = [
  { USER_ID: "U-1001", ACCEPTANCE_STATUS: "Accepted",  INJURY_TYPE: "Fracture",       INSURANCE_TYPE: "Private"   },
  { USER_ID: "U-1002", ACCEPTANCE_STATUS: "Pending",   INJURY_TYPE: "Laceration",     INSURANCE_TYPE: "Medicare"  },
  { USER_ID: "U-1003", ACCEPTANCE_STATUS: "Rejected",  INJURY_TYPE: "Burn",           INSURANCE_TYPE: "Medicaid"  },
  { USER_ID: "U-1004", ACCEPTANCE_STATUS: "Accepted",  INJURY_TYPE: "Concussion",     INSURANCE_TYPE: "Private"   },
  { USER_ID: "U-1005", ACCEPTANCE_STATUS: "Pending",   INJURY_TYPE: "Sprain",         INSURANCE_TYPE: "Uninsured" },
  { USER_ID: "U-1006", ACCEPTANCE_STATUS: "Accepted",  INJURY_TYPE: "Dislocation",    INSURANCE_TYPE: "Medicare"  },
  { USER_ID: "U-1007", ACCEPTANCE_STATUS: "Rejected",  INJURY_TYPE: "Fracture",       INSURANCE_TYPE: "Private"   },
  { USER_ID: "U-1008", ACCEPTANCE_STATUS: "Accepted",  INJURY_TYPE: "Soft Tissue",    INSURANCE_TYPE: "Medicaid"  },
  { USER_ID: "U-1009", ACCEPTANCE_STATUS: "Pending",   INJURY_TYPE: "Laceration",     INSURANCE_TYPE: "Private"   },
  { USER_ID: "U-1010", ACCEPTANCE_STATUS: "Accepted",  INJURY_TYPE: "Nerve Damage",   INSURANCE_TYPE: "Medicare"  },
];

// ─── Column definitions ──────────────────────────────────────────────────────
const COLUMNS = [
  { key: "USER_ID",           label: "User ID"           },
  { key: "ACCEPTANCE_STATUS", label: "Acceptance Status" },
  { key: "INJURY_TYPE",       label: "Injury Type"       },
  { key: "INSURANCE_TYPE",    label: "Insurance Type"    },
];

// ─── Status badge config ─────────────────────────────────────────────────────
const STATUS_STYLES = {
  Accepted: { bg: "#e6f4ec", color: "#1a7a42", dot: "#2ca05a" },
  Pending:  { bg: "#fff8e6", color: "#8a6200", dot: "#f0a500" },
  Rejected: { bg: "#fdecea", color: "#b91c1c", dot: "#e53935" },
};

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || { bg: "#f0f0f0", color: "#555", dot: "#aaa" };
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      background: s.bg,
      color: s.color,
      padding: "3px 10px",
      borderRadius: 20,
      fontSize: 12,
      fontWeight: 500,
      letterSpacing: "0.02em",
    }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.dot, flexShrink: 0 }} />
      {status}
    </span>
  );
}

// ─── Main Grid Component ─────────────────────────────────────────────────────
export default function UserGrid({ data = USER_DATA }) {
  const [sortKey, setSortKey]     = useState(null);
  const [sortDir, setSortDir]     = useState("asc");
  const [filter, setFilter]       = useState("");
  const [statusFilter, setStatus] = useState("All");

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const statuses = ["All", ...Array.from(new Set(data.map((u) => u.ACCEPTANCE_STATUS)))];

  const filtered = data
    .filter((u) => {
      const q = filter.toLowerCase();
      const matchesSearch = !q || Object.values(u).some((v) => v.toLowerCase().includes(q));
      const matchesStatus = statusFilter === "All" || u.ACCEPTANCE_STATUS === statusFilter;
      return matchesSearch && matchesStatus;
    })
    .sort((a, b) => {
      if (!sortKey) return 0;
      const av = a[sortKey], bv = b[sortKey];
      return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
    });

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif", padding: 32, background: "#f8f9fb", minHeight: "100vh" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }

        .grid-card {
          background: #fff;
          border-radius: 12px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04);
          overflow: hidden;
        }
        .grid-header {
          padding: 20px 24px 16px;
          border-bottom: 1px solid #f0f0f0;
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
        }
        .grid-title {
          font-size: 15px;
          font-weight: 600;
          color: #111;
          flex: 1;
          min-width: 120px;
        }
        .grid-count {
          font-size: 12px;
          color: #999;
          font-weight: 400;
        }
        .search-input {
          border: 1px solid #e5e7eb;
          border-radius: 7px;
          padding: 7px 12px;
          font-size: 13px;
          font-family: inherit;
          color: #111;
          outline: none;
          width: 200px;
          transition: border-color 0.15s;
          background: #fafafa;
        }
        .search-input:focus { border-color: #4f6ef7; background: #fff; }
        .search-input::placeholder { color: #bbb; }

        .filter-pills {
          display: flex;
          gap: 6px;
        }
        .pill {
          border: 1px solid #e5e7eb;
          border-radius: 20px;
          padding: 4px 12px;
          font-size: 12px;
          font-family: inherit;
          cursor: pointer;
          background: #fff;
          color: #666;
          transition: all 0.15s;
        }
        .pill:hover { border-color: #4f6ef7; color: #4f6ef7; }
        .pill.active { background: #4f6ef7; color: #fff; border-color: #4f6ef7; }

        table {
          width: 100%;
          border-collapse: collapse;
        }
        thead th {
          padding: 11px 20px;
          text-align: left;
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: #9ca3af;
          background: #fafafa;
          border-bottom: 1px solid #f0f0f0;
          user-select: none;
          white-space: nowrap;
        }
        .th-inner {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          cursor: pointer;
        }
        .th-inner:hover { color: #4f6ef7; }
        .sort-icon { font-size: 10px; opacity: 0.5; }
        .sort-icon.active { opacity: 1; color: #4f6ef7; }

        tbody tr {
          border-bottom: 1px solid #f5f5f5;
          transition: background 0.1s;
        }
        tbody tr:last-child { border-bottom: none; }
        tbody tr:hover { background: #f8f9ff; }
        td {
          padding: 13px 20px;
          font-size: 13.5px;
          color: #374151;
          vertical-align: middle;
        }
        .user-id {
          font-family: 'SF Mono', 'Fira Code', monospace;
          font-size: 12.5px;
          color: #6366f1;
          font-weight: 500;
        }

        .empty-row td {
          text-align: center;
          padding: 48px;
          color: #bbb;
          font-size: 13px;
        }

        .grid-footer {
          padding: 12px 24px;
          border-top: 1px solid #f0f0f0;
          font-size: 12px;
          color: #bbb;
        }
      `}</style>

      <div className="grid-card">
        {/* Header */}
        <div className="grid-header">
          <span className="grid-title">
            User Records
            <span className="grid-count"> · {filtered.length} of {data.length}</span>
          </span>

          <div className="filter-pills">
            {statuses.map((s) => (
              <button
                key={s}
                className={`pill${statusFilter === s ? " active" : ""}`}
                onClick={() => setStatus(s)}
              >
                {s}
              </button>
            ))}
          </div>

          <input
            className="search-input"
            type="text"
            placeholder="Search users…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>

        {/* Table */}
        <table>
          <thead>
            <tr>
              {COLUMNS.map((col) => {
                const isActive = sortKey === col.key;
                const icon = isActive ? (sortDir === "asc" ? "↑" : "↓") : "↕";
                return (
                  <th key={col.key}>
                    <span className="th-inner" onClick={() => handleSort(col.key)}>
                      {col.label}
                      <span className={`sort-icon${isActive ? " active" : ""}`}>{icon}</span>
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr className="empty-row">
                <td colSpan={4}>No records match your search.</td>
              </tr>
            ) : (
              filtered.map((user, i) => (
                <tr key={user.USER_ID}>
                  <td><span className="user-id">{user.USER_ID}</span></td>
                  <td><StatusBadge status={user.ACCEPTANCE_STATUS} /></td>
                  <td>{user.INJURY_TYPE}</td>
                  <td>{user.INSURANCE_TYPE}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        <div className="grid-footer">
          Showing {filtered.length} record{filtered.length !== 1 ? "s" : ""}
        </div>
      </div>
    </div>
  );
}
