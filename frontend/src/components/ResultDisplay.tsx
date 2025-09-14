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
          {data.map((finding: any, index: number) => (
            <div
              key={index}
              className={`finding finding-${finding.level}`}
              style={{
                marginBottom: '1rem',
                padding: '1rem',
                background: 'white',
                borderRadius: '6px',
                borderLeft: `4px solid ${
                  finding.level === 'error' ? '#dc2626' :
                  finding.level === 'warning' ? '#f59e0b' : '#3b82f6'
                }`
              }}
            >
              <strong>{finding.level.toUpperCase()}:</strong> {finding.message}
              {finding.details && (
                <div style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>
                  {finding.details}
                </div>
              )}
            </div>
          ))}
        </div>
      );

    default:
      return <div>Unknown display type</div>;
  }
};