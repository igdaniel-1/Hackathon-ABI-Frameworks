import React, { useState, useCallback, useEffect } from 'react';
import { RotateCcw, Zap } from 'lucide-react';
import PatientTable from './PatientTable';
import StatsBar from './StatsBar';
import AIPipelinePanel from './AIPipelinePanel';
import PatientDetail from './PatientDetail';

const API_BASE = 'https://hackathon.prod.pulsefoundry.ai';

export default function Dashboard() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pipelineMode, setPipelineMode] = useState('manual');
  const [pipelineLogs, setPipelineLogs] = useState([]);
  const [pipelinePhase, setPipelinePhase] = useState(null);
  const [selectedPatient, setSelectedPatient] = useState(null);

  const addLog = useCallback((msg, type = 'info') => {
    const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
    setPipelineLogs(prev => [...prev, { ts, msg, type }]);
  }, []);

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  const fetchWithRetry = useCallback(async (url, maxRetries = 6) => {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      const resp = await fetch(url);
      if (resp.status === 429) {
        const retryAfter = parseInt(resp.headers.get('Retry-After') || '2', 10);
        const wait = retryAfter + Math.pow(2, attempt) * 0.5 + Math.random();
        addLog(`429 — retry in ${wait.toFixed(1)}s (attempt ${attempt + 1})`, 'warn');
        await sleep(wait * 1000);
        continue;
      }
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json();
    }
    throw new Error('Max retries exceeded');
  }, [addLog]);

  const runPipeline = useCallback(async () => {
    setLoading(true);
    setPipelineLogs([]);
    setPipelinePhase('ingesting');
    const allResults = [];

    try {
      addLog('LASSO pipeline initiated...', 'info');
      addLog('Phase 1: Ingesting patient records from PCC', 'info');

      const facilities = [101, 102, 103];
      let allPatients = [];

      for (const fid of facilities) {
        addLog(`Fetching Facility ${fid === 101 ? 'A' : fid === 102 ? 'B' : 'C'} (id=${fid})...`);
        const patients = await fetchWithRetry(`${API_BASE}/pcc/patients?facility_id=${fid}`);
        allPatients = allPatients.concat(patients);
        addLog(`${patients.length} patients loaded from Facility ${fid === 101 ? 'A' : fid === 102 ? 'B' : 'C'}`, 'success');
      }

      addLog(`Total: ${allPatients.length} patients ingested`, 'success');
      setPipelinePhase('enriching');
      addLog('Phase 2: Enriching — diagnoses, coverage, notes, assessments', 'info');

      const sampleSize = Math.min(allPatients.length, 30);
      const sample = allPatients.slice(0, sampleSize);

      for (let i = 0; i < sample.length; i++) {
        const p = sample[i];
        try {
          const [diagnoses, coverage, notes, assessments] = await Promise.all([
            fetchWithRetry(`${API_BASE}/pcc/diagnoses?patient_id=${p.patient_id}`),
            fetchWithRetry(`${API_BASE}/pcc/coverage?patient_id=${p.patient_id}`),
            fetchWithRetry(`${API_BASE}/pcc/notes?patient_id=${p.id}`),
            fetchWithRetry(`${API_BASE}/pcc/assessments?patient_id=${p.id}`),
          ]);

          const hasMCB = coverage.some(c => c.payer_code === 'MCB' && !c.effective_to);
          const woundDiags = diagnoses.filter(d => d.clinical_status === 'active' && d.icd10_code);

          let woundType = null, woundStage = null, woundLocation = null;
          let lengthCm = null, widthCm = null, depthCm = null;
          let drainageAmount = null, noteFormat = 'unknown', extractionSource = 'none';
          let noteText = null, rawAssessment = null;

          // Try assessments first
          if (assessments.length > 0) {
            const a = assessments[0];
            rawAssessment = a.raw_json;
            if (a.raw_json) {
              try {
                const raw = JSON.parse(a.raw_json);
                if (raw.wound_type) {
                  woundType = raw.wound_type;
                  woundStage = raw.stage || null;
                  woundLocation = raw.location || null;
                  lengthCm = raw.length_cm || null;
                  widthCm = raw.width_cm || null;
                  depthCm = raw.depth_cm != null ? raw.depth_cm : null;
                  drainageAmount = raw.drainage_amount || raw.drainage_type || null;
                  extractionSource = 'assessment';
                  noteFormat = 'structured';
                } else if (raw.sections) {
                  extractionSource = 'assessment';
                  noteFormat = 'structured';
                  // Extract from nested sections
                  const allAnswers = raw.sections
                    ?.flatMap(s => s.questions || [])
                    ?.map(q => `${q.question}: ${q.answer}`)
                    ?.join('\n') || '';
                  // Parse wound info from narrative answers
                  const combined = allAnswers.toLowerCase();
                  if (combined.includes('pressure ulcer') || combined.includes('pressure injury')) {
                    woundType = 'Pressure Ulcer';
                  } else if (combined.includes('diabetic') || combined.includes('dfu')) {
                    woundType = 'Diabetic Foot Ulcer';
                  } else if (combined.includes('venous')) {
                    woundType = 'Venous Ulcer';
                  } else if (combined.includes('arterial')) {
                    woundType = 'Arterial Ulcer';
                  } else if (combined.includes('surgical')) {
                    woundType = 'Surgical Wound';
                  } else if (combined.includes('wound') || combined.includes('ulcer')) {
                    woundType = 'Wound (unspecified)';
                  }
                  // Parse stage
                  const stageMatch = combined.match(/stage[:\s]*(\d)/i);
                  if (stageMatch) woundStage = parseInt(stageMatch[1]);
                  // Parse location
                  const locPatterns = ['sacrum', 'sacral', 'heel', 'hip', 'buttock', 'coccyx', 'ankle', 'foot', 'leg', 'trochanter', 'elbow', 'back'];
                  for (const loc of locPatterns) {
                    if (combined.includes(loc)) {
                      const sideMatch = combined.match(new RegExp(`(left|right|l\\.|r\\.)\\s*${loc}|${loc}.*?(left|right)`, 'i'));
                      const side = sideMatch ? (sideMatch[1] || sideMatch[2] || '').replace('l.', 'Left').replace('r.', 'Right') : '';
                      woundLocation = `${side ? side.charAt(0).toUpperCase() + side.slice(1) + ' ' : ''}${loc.charAt(0).toUpperCase() + loc.slice(1)}`;
                      break;
                    }
                  }
                  // Parse measurements
                  const measMatch = combined.match(/(\d+\.?\d*)\s*(?:cm\s*)?x\s*(\d+\.?\d*)\s*(?:cm\s*)?(?:x\s*(\d+\.?\d*))?/);
                  if (measMatch) {
                    lengthCm = parseFloat(measMatch[1]);
                    widthCm = parseFloat(measMatch[2]);
                    if (measMatch[3]) depthCm = parseFloat(measMatch[3]);
                  } else {
                    const lMatch = combined.match(/(?:length|measures?)[:\s]*(\d+\.?\d*)/);
                    const wMatch = combined.match(/width[:\s]*(\d+\.?\d*)/);
                    const dMatch = combined.match(/depth[:\s]*(\d+\.?\d*)/);
                    if (lMatch) lengthCm = parseFloat(lMatch[1]);
                    if (wMatch) widthCm = parseFloat(wMatch[1]);
                    if (dMatch) depthCm = parseFloat(dMatch[1]);
                  }
                  // Parse drainage
                  if (combined.includes('heavy')) drainageAmount = 'Heavy';
                  else if (combined.includes('moderate') || combined.includes('mod ')) drainageAmount = 'Moderate';
                  else if (combined.includes('light') || combined.includes('scant') || combined.includes('minimal')) drainageAmount = 'Light';
                  else if (combined.includes('none') || combined.includes('no drainage')) drainageAmount = 'None';
                  else if (combined.includes('drainage')) drainageAmount = 'Present';
                }
              } catch (e) { /* skip */ }
            }
          }

          // Fall back to notes
          if (!woundType && notes.length > 0) {
            const n = notes[0];
            noteText = n.note_text;
            if (n.note_text) {
              extractionSource = 'progress_note';
              const text = n.note_text.toLowerCase();
              // Detect format
              if (text.includes('envive') || text.includes('care conference')) {
                noteFormat = 'envive';
              } else if (text.includes('wound 1') && text.includes('wound 2')) {
                noteFormat = 'multi_wound';
              } else if (text.includes('location:') && text.includes('wound type:')) {
                noteFormat = 'structured';
              } else {
                noteFormat = 'prose';
              }
              // Parse wound type
              if (text.includes('pressure ulcer') || text.includes('pressure injury')) {
                woundType = 'Pressure Ulcer';
              } else if (text.includes('diabetic foot') || text.includes('dfu')) {
                woundType = 'Diabetic Foot Ulcer';
              } else if (text.includes('venous ulcer') || text.includes('venous stasis')) {
                woundType = 'Venous Ulcer';
              } else if (text.includes('arterial ulcer')) {
                woundType = 'Arterial Ulcer';
              } else if (text.includes('surgical')) {
                woundType = 'Surgical Wound';
              } else if (text.includes('abscess')) {
                woundType = 'Abscess';
              } else if (text.includes('burn')) {
                woundType = 'Burn';
              } else if (text.includes('wound') || text.includes('ulcer')) {
                woundType = 'Wound (unspecified)';
              }
              // Parse stage
              const stageMatch = text.match(/stage[:\s]*(\d)/i);
              if (stageMatch) woundStage = parseInt(stageMatch[1]);
              // Parse location
              const locPatterns = ['sacrum', 'sacral', 'heel', 'hip', 'buttock', 'coccyx', 'ankle', 'foot', 'leg', 'trochanter', 'elbow', 'back'];
              for (const loc of locPatterns) {
                if (text.includes(loc)) {
                  const sideMatch = text.match(new RegExp(`(left|right|l\\s|r\\s)\\s*${loc}|${loc}[^.]*?(left|right)`, 'i'));
                  const side = sideMatch ? (sideMatch[1] || sideMatch[2] || '').trim() : '';
                  const sideLabel = side.toLowerCase().startsWith('l') ? 'Left' : side.toLowerCase().startsWith('r') ? 'Right' : '';
                  woundLocation = `${sideLabel ? sideLabel + ' ' : ''}${loc.charAt(0).toUpperCase() + loc.slice(1)}`;
                  break;
                }
              }
              // Parse measurements
              const measMatch = text.match(/(?:measures?|meas\.?)\s*(\d+\.?\d*)\s*(?:cm\s*)?x\s*(\d+\.?\d*)\s*(?:cm)?/i);
              if (measMatch) {
                lengthCm = parseFloat(measMatch[1]);
                widthCm = parseFloat(measMatch[2]);
              }
              const depthMatch = text.match(/depth[:\s]*(\d+\.?\d*)/i);
              if (depthMatch) depthCm = parseFloat(depthMatch[1]);
              const fullMeas = text.match(/(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*cm/i);
              if (fullMeas) {
                lengthCm = parseFloat(fullMeas[1]);
                widthCm = parseFloat(fullMeas[2]);
                depthCm = parseFloat(fullMeas[3]);
              }
              // Parse drainage
              if (text.includes('heavy')) drainageAmount = 'Heavy';
              else if (text.includes('moderate') || text.includes('mod ')) drainageAmount = 'Moderate';
              else if (text.includes('light') || text.includes('scant') || text.includes('minimal')) drainageAmount = 'Light';
              else if (text.includes('no drainage') || text.includes('drainage: none')) drainageAmount = 'None';
              else if (text.includes('drainage')) drainageAmount = 'Present';
            }
          }

          // Also try ICD-10 codes to get wound type if still missing
          if (!woundType && woundDiags.length > 0) {
            for (const d of woundDiags) {
              const code = (d.icd10_code || '').toUpperCase();
              if (code.startsWith('L89')) {
                woundType = 'Pressure Ulcer';
                const desc = (d.icd10_description || '').toLowerCase();
                const sm = desc.match(/stage (\d)/);
                if (sm) woundStage = parseInt(sm[1]);
                const locMap = { 'sacral': 'Sacrum', 'hip': 'Hip', 'heel': 'Heel', 'ankle': 'Ankle', 'elbow': 'Elbow', 'buttock': 'Buttock' };
                for (const [k, v] of Object.entries(locMap)) {
                  if (desc.includes(k)) {
                    const side = desc.includes('right') ? 'Right ' : desc.includes('left') ? 'Left ' : '';
                    woundLocation = side + v;
                    break;
                  }
                }
                break;
              } else if (code.startsWith('E11') && code.includes('621')) {
                woundType = 'Diabetic Foot Ulcer';
                break;
              } else if (code.startsWith('I87') || code.startsWith('I83')) {
                woundType = 'Venous Ulcer';
                break;
              }
            }
          }

          // Determine routing
          let routing = 'reject';
          let reason = '';

          if (!hasMCB) {
            routing = 'reject';
            reason = 'No active Medicare Part B coverage. MCB is required for wound care billing.';
          } else if (!woundType) {
            routing = 'reject';
            reason = 'No wound data found in clinical records or ICD-10 diagnoses.';
          } else if (woundType && lengthCm && widthCm && depthCm != null && drainageAmount && (noteFormat === 'structured' || extractionSource === 'assessment')) {
            routing = 'auto_accept';
            reason = `Active ${woundType}${woundStage ? ` Stage ${woundStage}` : ''}${woundLocation ? ` on ${woundLocation}` : ''} with complete measurements (${lengthCm}×${widthCm}×${depthCm} cm). Drainage: ${drainageAmount}. MCB active. All billing fields documented.`;
          } else {
            routing = 'flag_for_review';
            const issues = [];
            if (!lengthCm || !widthCm) issues.push('measurements incomplete');
            if (depthCm == null) issues.push('depth missing');
            if (!drainageAmount) issues.push('drainage not documented');
            if (noteFormat === 'envive') issues.push('Envive narrative format');
            if (noteFormat === 'prose') issues.push('prose shorthand format');
            if (noteFormat === 'multi_wound') issues.push('multi-wound note');
            reason = `${woundType}${woundStage ? ` Stage ${woundStage}` : ''}${woundLocation ? ` on ${woundLocation}` : ''} identified. MCB active. ${issues.length > 0 ? 'Issues: ' + issues.join(', ') + '.' : ''} Manual review recommended.`;
          }

          allResults.push({
            patient_id: p.patient_id,
            internal_id: p.id,
            name: `${p.first_name || ''} ${p.last_name || ''}`.trim() || 'Unknown',
            facility_id: p.facility_id,
            wound_type: woundType,
            wound_stage: woundStage,
            wound_location: woundLocation,
            length_cm: lengthCm,
            width_cm: widthCm,
            depth_cm: depthCm,
            drainage_amount: drainageAmount,
            has_mcb_coverage: hasMCB,
            icd10_codes: woundDiags.map(d => d.icd10_code),
            routing_decision: routing,
            reason,
            note_format: noteFormat,
            extraction_source: extractionSource,
            last_assessment_date: assessments[0]?.assessment_date || null,
            note_text: noteText || (notes[0]?.note_text || null),
            raw_assessment: rawAssessment,
          });

          if ((i + 1) % 5 === 0 || i === sample.length - 1) {
            addLog(`Enriched ${i + 1}/${sample.length} patients`, 'info');
          }
        } catch (err) {
          addLog(`Error on ${p.patient_id}: ${err.message}`, 'error');
        }
      }

      setPipelinePhase('complete');
      const accepted = allResults.filter(r => r.routing_decision === 'auto_accept').length;
      const review = allResults.filter(r => r.routing_decision === 'flag_for_review').length;
      const rejected = allResults.filter(r => r.routing_decision === 'reject').length;
      addLog(`Pipeline complete! ${allResults.length} patients processed`, 'success');
      addLog(`${accepted} auto_accept | ${review} flag_for_review | ${rejected} reject`, 'success');
      setResults(allResults);
    } catch (err) {
      addLog(`Pipeline error: ${err.message}`, 'error');
      setPipelinePhase('error');
    } finally {
      setLoading(false);
    }
  }, [fetchWithRetry, addLog]);

  useEffect(() => {
    if (pipelineMode === 'autonomous' && results.length === 0 && !loading) {
      runPipeline();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pipelineMode]);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', padding: '28px 32px' }}>
      {/* Header */}
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 28,
        animation: 'fadeInUp 0.6s ease-out',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ fontSize: 48, lineHeight: 1 }}>🤠</div>
          <div>
            <h1 style={{
              fontSize: 44,
              fontWeight: 800,
              letterSpacing: '-1px',
              lineHeight: 1,
              background: 'linear-gradient(90deg, var(--gold), var(--orange), var(--yellow))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundSize: '200% auto',
              animation: 'shimmer 3s linear infinite',
            }}>
              LASSO
            </h1>
            <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--gray)', marginTop: 4, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              Wound Care Billing Pipeline
            </p>
          </div>
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: 'var(--bg-card)',
          border: '3px solid #333',
          borderRadius: 'var(--radius)',
          padding: '6px 8px',
        }}>
          {['manual', 'autonomous'].map(mode => (
            <button
              key={mode}
              onClick={() => setPipelineMode(mode)}
              style={{
                padding: '12px 24px',
                border: pipelineMode === mode ? '3px solid var(--white)' : '3px solid transparent',
                borderRadius: 10,
                background: pipelineMode === mode
                  ? mode === 'manual' ? 'var(--yellow)' : 'var(--lime)'
                  : 'transparent',
                boxShadow: pipelineMode === mode ? '3px 3px 0px rgba(255,255,255,0.2)' : 'none',
                fontFamily: 'inherit',
                fontWeight: 700,
                fontSize: 18,
                cursor: 'pointer',
                color: pipelineMode === mode ? 'var(--black)' : 'var(--gray)',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                transition: 'all 0.2s',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              {mode === 'manual' ? '▶' : '⚡'} {mode}
            </button>
          ))}
        </div>
      </header>

      {/* Stats */}
      {results.length > 0 && <StatsBar results={results} />}

      {/* Main Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: results.length > 0 ? '1fr 420px' : '1fr',
        gap: 24,
        alignItems: 'start',
      }}>
        <div style={{ animation: 'fadeInLeft 0.5s ease-out' }}>
          {results.length > 0 ? (
            <PatientTable results={results} onSelectPatient={setSelectedPatient} />
          ) : (
            <div style={{
              background: 'var(--bg-card)',
              border: '3px solid #333',
              borderRadius: 'var(--radius)',
              padding: '100px 40px',
              textAlign: 'center',
              animation: 'fadeInUp 0.8s ease-out',
            }}>
              <div style={{
                fontSize: 72,
                marginBottom: 28,
                animation: 'pulse 2s ease-in-out infinite',
              }}>🤠</div>
              <h2 style={{ fontSize: 32, fontWeight: 800, marginBottom: 16, color: 'var(--gold)' }}>
                Ready to Ride
              </h2>
              <p style={{ color: 'var(--gray)', fontSize: 20, maxWidth: 500, margin: '0 auto 36px', lineHeight: 1.5 }}>
                LASSO will fetch patient data, extract wound details, and determine Medicare Part B billing eligibility.
              </p>
              <button
                onClick={runPipeline}
                disabled={loading}
                style={{
                  padding: '18px 48px',
                  background: loading ? '#333' : 'var(--cyan)',
                  border: '3px solid var(--white)',
                  borderRadius: 'var(--radius)',
                  boxShadow: loading ? 'none' : '5px 5px 0px rgba(0,212,255,0.3)',
                  fontFamily: 'inherit',
                  fontWeight: 800,
                  fontSize: 22,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  color: loading ? 'var(--gray)' : 'var(--black)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 10,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  transition: 'transform 0.1s, box-shadow 0.1s',
                }}
                onMouseDown={e => { if (!loading) { e.currentTarget.style.transform = 'translate(4px, 4px)'; e.currentTarget.style.boxShadow = '1px 1px 0px rgba(0,212,255,0.3)'; }}}
                onMouseUp={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '5px 5px 0px rgba(0,212,255,0.3)'; }}
                onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '5px 5px 0px rgba(0,212,255,0.3)'; }}
              >
                {loading ? <RotateCcw size={24} className="spin" /> : <Zap size={24} />}
                {loading ? 'Lassoing Data...' : 'Run Pipeline'}
              </button>
            </div>
          )}
        </div>

        <div style={{ animation: 'fadeInRight 0.6s ease-out' }}>
          <AIPipelinePanel
            logs={pipelineLogs}
            phase={pipelinePhase}
            mode={pipelineMode}
            loading={loading}
            onRun={runPipeline}
            resultCount={results.length}
          />
        </div>
      </div>

      {selectedPatient && (
        <PatientDetail
          patient={selectedPatient}
          onClose={() => setSelectedPatient(null)}
        />
      )}
    </div>
  );
}
