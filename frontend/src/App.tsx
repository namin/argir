import React, { useState, useEffect } from 'react';
import './App.css';
import { TabContainer } from './components/TabContainer';
import { ResultDisplay } from './components/ResultDisplay';
import { ArgumentGraph } from './components/ArgumentGraph';

type ArgirResult = {
  success: boolean;
  result: {
    report_md: string;
    argir: any;
    fof?: string[];
    semantics?: any;
    findings?: Array<{
      level: string;
      message: string;
      details?: string;
    }>;
    fol_summary?: any;
    validation_issues?: any[];
  };
  validation?: {
    errors?: Array<{
      code: string;
      path: string;
      message: string;
    }>;
    warnings?: Array<{
      code: string;
      path: string;
      message: string;
    } | {
      node: string;
      message: string;
    }>;
  };
};

function App() {
  const [text, setText] = useState('');
  const [folMode, setFolMode] = useState<'classical' | 'defeasible'>('classical');
  const [goalId, setGoalId] = useState('');
  const [useSoft, setUseSoft] = useState(true);
  const [kSamples, setKSamples] = useState(1);
  const [apiKey, setApiKey] = useState('');

  const [result, setResult] = useState<ArgirResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load saved values from localStorage
  useEffect(() => {
    const savedText = localStorage.getItem('argir:text');
    if (savedText) setText(savedText);

    const savedApiKey = localStorage.getItem('argir:apikey');
    if (savedApiKey) setApiKey(savedApiKey);
  }, []);

  // Save text and API key to localStorage
  useEffect(() => {
    localStorage.setItem('argir:text', text);
  }, [text]);

  useEffect(() => {
    localStorage.setItem('argir:apikey', apiKey);
  }, [apiKey]);

  const analyze = async () => {
    setLoading(true);
    setError(null);
    setResult(null);  // Clear previous results

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (apiKey.trim()) {
        headers['X-API-Key'] = apiKey.trim();
      }

      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          text,
          fol_mode: folMode,
          goal_id: goalId || null,
          use_soft: useSoft,
          k_samples: kSamples,
          api_key: apiKey.trim() || null,
        }),
      });

      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}`;

        if (response.status === 400) {
          try {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorMessage;
          } catch {
            // Use default error message
          }

          if (!apiKey.trim() && useSoft) {
            errorMessage += ' — Soft pipeline may require a Gemini API key.';
          }
        }

        throw new Error(errorMessage);
      }

      const data = await response.json();
      setResult(data);
    } catch (e: any) {
      setError(e?.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  // Extract node IDs from result for goal dropdown
  const nodeIds: string[] = result?.result?.argir?.nodes?.map((n: any) => n.id) || [];

  return (
    <div className="app">
      <header className="appbar">
        <div className="brand">
          <h1>ARGIR</h1>
          <span className="subtitle">Argument Graph Intermediate Representation</span>
        </div>
        <div className="spacer" />
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="Gemini API Key (optional)"
          className="api-key-input"
        />
        <a
          href="https://github.com/namin/argir"
          target="_blank"
          rel="noreferrer"
          style={{ marginLeft: '1rem', display: 'flex', alignItems: 'center' }}
        >
          <img
            src="/github-mark.png"
            alt="GitHub"
            style={{ width: 24, height: 24 }}
          />
        </a>
      </header>

      <main className="main">
        <div className="container">
          <div className="input-section">
            <div className="card">
              <h2>Analyze Natural Language Arguments</h2>
              <p className="description">
                Enter your natural language text below and ARGIR will analyze the arguments,
                generate an argument graph, and produce formal logic representations.
              </p>

              <div className="form-group">
                <label htmlFor="text">Natural Language Text:</label>
                <textarea
                  id="text"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Enter your argument text here. For example: 'If it rains, the streets get wet. It is raining. So, the streets will get wet.'"
                  required
                />
              </div>

              <div className="options-row">
                <div className="form-group">
                  <label htmlFor="fol-mode">FOL Mode:</label>
                  <select
                    id="fol-mode"
                    value={folMode}
                    onChange={(e) => setFolMode(e.target.value as 'classical' | 'defeasible')}
                  >
                    <option value="classical">Classical</option>
                    <option value="defeasible">Defeasible (exceptions become negated conditions)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="goal-id">Goal Node ID:</label>
                  <select
                    id="goal-id"
                    value={goalId}
                    onChange={(e) => setGoalId(e.target.value)}
                  >
                    <option value="">(auto-select)</option>
                    {nodeIds.map(id => (
                      <option key={id} value={id}>{id}</option>
                    ))}
                  </select>
                  <small>Leave empty for auto-selection</small>
                </div>
              </div>

              <div className="checkbox-row">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={useSoft}
                    onChange={(e) => setUseSoft(e.target.checked)}
                  />
                  <span>Use Soft Pipeline (more robust extraction)</span>
                </label>
                <small>Two-stage extraction: soft IR → canonicalization → strict ARGIR</small>
              </div>

              {useSoft && (
                <div className="form-group soft-options">
                  <label htmlFor="k-samples">Number of samples:</label>
                  <input
                    id="k-samples"
                    type="number"
                    value={kSamples}
                    onChange={(e) => setKSamples(parseInt(e.target.value) || 1)}
                    min="1"
                    max="10"
                  />
                  <small>Try multiple extractions and pick the best (1-10)</small>
                </div>
              )}

              <div className="button-row">
                <button
                  onClick={analyze}
                  disabled={loading || !text.trim()}
                  className="analyze-button"
                >
                  {loading ? 'Analyzing...' : 'Analyze Arguments'}
                </button>
              </div>

              {error && (
                <div className="error">
                  {error}
                </div>
              )}

              {result?.validation && (
                <>
                  {result.validation.errors && result.validation.errors.length > 0 && (
                    <div className="error">
                      <strong>Validation Errors:</strong>
                      <ul>
                        {result.validation.errors.map((err, i) => (
                          <li key={i}>[{err.code}] {err.path}: {err.message}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {result.validation.warnings && result.validation.warnings.length > 0 && (
                    <div className="warning">
                      <strong>Validation Warnings:</strong>
                      <ul>
                        {result.validation.warnings.map((warn: any, i: number) => (
                          <li key={i}>
                            {warn.code ? `[${warn.code}] ${warn.path}: ${warn.message}` :
                             `Node '${warn.node}': ${warn.message}`}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="card">
              <h3>Example Inputs</h3>
              <div className="example">
                <strong>Simple Modus Ponens:</strong>
                <p>"If it rains, the streets get wet. It is raining. So, the streets will get wet."</p>
              </div>
              <div className="example">
                <strong>With Exception:</strong>
                <p>"If it rains, the streets get wet. It is raining. So, the streets will get wet. However, sometimes drains prevent wet streets."</p>
              </div>
              <div className="example">
                <strong>Multiple Arguments:</strong>
                <p>"All birds can fly. Penguins are birds. But penguins cannot fly because they are flightless birds. Therefore, not all birds can fly."</p>
              </div>
            </div>
          </div>

          {result && (
            <div className="results-section">
              <TabContainer
                defaultTab="report"
                tabs={[
                  {
                    id: 'report',
                    label: 'Report',
                    content: <ResultDisplay type="report" data={result.result.report_md} />
                  },
                  {
                    id: 'graph-visual',
                    label: 'Graph View',
                    content: <ArgumentGraph data={result.result.argir?.graph} />
                  },
                  {
                    id: 'graph-json',
                    label: 'Graph JSON',
                    content: <ResultDisplay type="json" data={result.result.argir} />
                  },
                  {
                    id: 'fol',
                    label: 'First-Order Logic',
                    content: <ResultDisplay type="fol" data={result.result.fof} />,
                    disabled: !result.result.fof
                  },
                  {
                    id: 'semantics',
                    label: 'AF Semantics',
                    content: <ResultDisplay type="json" data={result.result.semantics} />,
                    disabled: !result.result.semantics
                  },
                  {
                    id: 'eprover',
                    label: 'E-Prover Results',
                    content: <ResultDisplay type="eprover" data={result.result.fol_summary} />,
                    disabled: !result.result.fol_summary
                  },
                  {
                    id: 'findings',
                    label: 'Findings',
                    content: <ResultDisplay type="findings" data={result.result.findings} />,
                    disabled: !result.result.findings || result.result.findings.length === 0
                  }
                ]}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;