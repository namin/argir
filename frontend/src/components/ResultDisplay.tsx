import React from 'react';
import { FindingCard } from './FindingCard';
import './FindingCard.css';

interface ResultDisplayProps {
  type: 'report' | 'json' | 'fol' | 'findings' | 'eprover';
  data: any;
  argirData?: any; // Full ARGIR data for node lookups
}

export const ResultDisplay: React.FC<ResultDisplayProps> = ({ type, data, argirData }) => {
  if (!data) {
    return <div className="muted">No data available</div>;
  }

  switch (type) {
    case 'report':
      return (
        <div className="report-display">
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {data}
          </pre>
        </div>
      );

    case 'json':
      return (
        <div className="json-display">
          <pre>
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      );

    case 'fol':
      return (
        <div className="fol-display">
          <pre>
            {Array.isArray(data) ? data.join('\n') : data}
          </pre>
        </div>
      );

    case 'findings':
      if (!Array.isArray(data) || data.length === 0) {
        return <div className="muted">No findings</div>;
      }
      return (
        <div className="findings-display">
          {data.map((finding: any, index: number) => (
            <FindingCard
              key={index}
              finding={finding}
              argirData={argirData}
            />
          ))}
        </div>
      );

    case 'eprover':
      if (!data || typeof data !== 'object') {
        return <div className="muted">No E-Prover results available</div>;
      }

      const getStatusColor = () => {
        if (data.theorem) return '#10b981'; // green for theorem proved
        if (data.unsat) return '#10b981'; // green for unsatisfiable
        if (data.sat) return '#f59e0b'; // amber for satisfiable
        return '#6b7280'; // gray for unknown
      };

      const getStatusText = () => {
        if (data.theorem) return '✓ Theorem Proved';
        if (data.unsat) return '✓ Unsatisfiable';
        if (data.sat) return '⚠ Satisfiable';
        if (data.note === 'timeout') return '⏱ Timeout';
        if (!data.available) return '✗ E-Prover not available';
        return '? Unknown';
      };

      return (
        <div className="eprover-display">
          <div style={{
            marginBottom: '1.5rem',
            padding: '1rem',
            background: 'white',
            borderRadius: '6px',
            borderLeft: `4px solid ${getStatusColor()}`
          }}>
            <h4 style={{ margin: '0 0 0.5rem 0', color: getStatusColor() }}>
              {getStatusText()}
            </h4>
            {data.note && data.note !== 'timeout' && (
              <p style={{ margin: '0.5rem 0', color: '#6b7280' }}>{data.note}</p>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.5rem', fontSize: '0.9rem' }}>
              <span style={{ color: '#6b7280' }}>Tool:</span>
              <span>{data.tool || 'eprover'}</span>
              <span style={{ color: '#6b7280' }}>Available:</span>
              <span>{data.available ? 'Yes' : 'No'}</span>
              <span style={{ color: '#6b7280' }}>Unsatisfiable:</span>
              <span>{data.unsat ? 'Yes' : 'No'}</span>
              <span style={{ color: '#6b7280' }}>Satisfiable:</span>
              <span>{data.sat ? 'Yes' : 'No'}</span>
              {data.theorem !== undefined && (
                <>
                  <span style={{ color: '#6b7280' }}>Theorem:</span>
                  <span>{data.theorem ? 'Proved' : 'Not proved'}</span>
                </>
              )}
            </div>
          </div>

          {data.raw && (
            <details>
              <summary style={{
                cursor: 'pointer',
                fontWeight: 500,
                padding: '0.75rem',
                background: '#f3f4f6',
                borderRadius: '6px',
                marginBottom: '1rem'
              }}>
                Raw E-Prover Output
              </summary>
              <pre style={{
                fontSize: '0.85rem',
                padding: '1rem',
                background: '#1e293b',
                color: '#e2e8f0',
                borderRadius: '6px',
                overflow: 'auto'
              }}>
                {data.raw}
              </pre>
            </details>
          )}
        </div>
      );

    default:
      return <div>Unknown display type</div>;
  }
};