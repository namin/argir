import React from 'react';

interface ResultDisplayProps {
  type: 'report' | 'json' | 'fol' | 'findings';
  data: any;
}

export const ResultDisplay: React.FC<ResultDisplayProps> = ({ type, data }) => {
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
          {data.map((finding: any, index: number) => {
            // Map kind to severity level for display
            const severityMap: Record<string, string> = {
              'derivability_gap': 'warning',
              'circular_support': 'error',
              'edge_mismatch': 'warning',
              'attack_support_mismatch': 'warning'
            };
            const severity = severityMap[finding.kind] || 'info';

            return (
              <div
                key={index}
                className={`finding finding-${severity}`}
                style={{
                  marginBottom: '1rem',
                  padding: '1rem',
                  background: 'white',
                  borderRadius: '6px',
                  borderLeft: `4px solid ${
                    severity === 'error' ? '#dc2626' :
                    severity === 'warning' ? '#f59e0b' : '#3b82f6'
                  }`
                }}
              >
                <strong>{finding.kind?.replace(/_/g, ' ').toUpperCase()}:</strong> {finding.message}
                {finding.node && (
                  <div style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>
                    Node: {finding.node}
                  </div>
                )}
                {finding.cycle && (
                  <div style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>
                    Cycle: {finding.cycle.join(' → ')}
                  </div>
                )}
                {finding.edge && (
                  <div style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>
                    Edge: {finding.edge.join(' → ')}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );

    default:
      return <div>Unknown display type</div>;
  }
};