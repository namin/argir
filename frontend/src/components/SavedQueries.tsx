import { useState, useEffect } from 'react';

type SavedQuery = {
  hash: string;
  text: string;
  timestamp: string;
  fol_mode?: string;
  goal_id?: string;
};

export function SavedQueries() {
  const [queries, setQueries] = useState<SavedQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/saved')
      .then(res => res.json())
      .then(data => {
        setQueries(data);
        setLoading(false);
      })
      .catch(err => {
        setError('Failed to load saved queries');
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        Loading saved queries...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#f44336' }}>
        {error}
      </div>
    );
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1>Saved Queries</h1>
        <a href="/" style={{ color: '#1976d2', textDecoration: 'none' }}>
          ← Back to Analyzer
        </a>
      </div>

      {queries.length === 0 ? (
        <div style={{
          padding: '3rem',
          textAlign: 'center',
          background: '#f5f5f5',
          borderRadius: '8px'
        }}>
          <p style={{ fontSize: '1.1rem', color: '#666' }}>No saved queries yet.</p>
          <p style={{ color: '#999' }}>Queries are automatically saved when you analyze them.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '1rem' }}>
          {queries.map(query => (
            <a
              key={query.hash}
              href={`/?saved=${query.hash}`}
              style={{
                display: 'block',
                padding: '1rem',
                background: 'white',
                border: '1px solid #ddd',
                borderRadius: '8px',
                textDecoration: 'none',
                color: 'inherit',
                transition: 'all 0.2s',
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = '';
                e.currentTarget.style.transform = '';
              }}
            >
              <div style={{ marginBottom: '0.5rem' }}>
                <strong style={{ color: '#1976d2' }}>#{query.hash}</strong>
                {query.fol_mode && (
                  <span style={{
                    marginLeft: '0.5rem',
                    padding: '0.2rem 0.5rem',
                    background: '#e3f2fd',
                    borderRadius: '4px',
                    fontSize: '0.85rem'
                  }}>
                    {query.fol_mode}
                  </span>
                )}
                {query.goal_id && (
                  <span style={{
                    marginLeft: '0.5rem',
                    padding: '0.2rem 0.5rem',
                    background: '#fce4ec',
                    borderRadius: '4px',
                    fontSize: '0.85rem'
                  }}>
                    Goal: {query.goal_id}
                  </span>
                )}
              </div>
              <div style={{ color: '#666', marginBottom: '0.5rem' }}>
                {query.text}
              </div>
              <div style={{ color: '#999', fontSize: '0.85rem' }}>
                {new Date(query.timestamp).toLocaleString()}
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}