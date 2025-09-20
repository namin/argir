import { useState, useEffect, useCallback } from 'react';
import './App.css';
import { TabContainer } from './components/TabContainer';
import { ResultDisplay } from './components/ResultDisplay';
import { ArgumentGraph } from './components/ArgumentGraph';
import { DiagnosisDisplay } from './components/DiagnosisDisplay';

type ArgirResult = {
  success: boolean;
  saved_hash?: string;
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
  issues?: Array<{
    id: string;
    type: string;
    target_node_ids: string[];
    evidence: any;
    detector_name: string;
    notes?: string;
  }>;
  repairs?: Array<{
    id: string;
    issue_id: string;
    kind: string;
    patch: any;
    cost: number;
    verification: any;
  }>;
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
  const [goalHint, setGoalHint] = useState('');
  const [useSoft, setUseSoft] = useState(true);
  const [kSamples, setKSamples] = useState(1);
  const [apiKey, setApiKey] = useState('');
  const [enableDiagnosis, setEnableDiagnosis] = useState(true);
  const [enableRepair, setEnableRepair] = useState(true);

  const [result, setResult] = useState<ArgirResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shouldAutoAnalyze, setShouldAutoAnalyze] = useState(false);

  // Load saved values from localStorage or URL parameter
  useEffect(() => {
    // Check for saved query in URL
    const urlParams = new URLSearchParams(window.location.search);
    const savedHash = urlParams.get('saved');

    if (savedHash) {
      // Load saved query from server
      fetch(`/api/saved/${savedHash}`)
        .then(res => res.json())
        .then(data => {
          setText(data.text || '');
          setFolMode(data.fol_mode || 'classical');
          setGoalId(data.goal_id || '');
          setGoalHint(data.goal_hint || '');
          setUseSoft(data.use_soft ?? true);
          setKSamples(data.k_samples || 1);
          setEnableDiagnosis(data.enable_diagnosis ?? true);
          setEnableRepair(data.enable_repair ?? true);
          
          // Trigger auto-analysis if text is present
          if (data.text?.trim()) {
            setShouldAutoAnalyze(true);
          }
        })
        .catch(err => {
          console.error('Failed to load saved query:', err);
        });
    } else {
      // Load from localStorage as fallback
      const savedText = localStorage.getItem('argir:text');
      if (savedText) setText(savedText);
    }

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

  const analyze = useCallback(async () => {
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
          goal_hint: goalHint || null,
          use_soft: useSoft,
          k_samples: kSamples,
          api_key: apiKey.trim() || null,
          enable_diagnosis: enableDiagnosis,
          enable_repair: enableRepair,
          semantics: 'grounded',
          max_af_edits: 2,
          max_abduce: 2,
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
  }, [text, folMode, goalId, goalHint, useSoft, kSamples, apiKey, enableDiagnosis, enableRepair]);

  // Auto-analyze when shouldAutoAnalyze is set and all state is ready
  useEffect(() => {
    if (shouldAutoAnalyze && text.trim()) {
      setShouldAutoAnalyze(false);
      analyze();
    }
  }, [shouldAutoAnalyze, text, analyze]);

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
        <a
          href="/saved"
          style={{ marginRight: '1rem', color: '#1976d2', textDecoration: 'none' }}
        >
          📚 Saved Queries
        </a>
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
                  <label htmlFor="goal-hint">Goal Hint (optional):</label>
                  <input
                    id="goal-hint"
                    type="text"
                    value={goalHint}
                    onChange={(e) => setGoalHint(e.target.value)}
                    placeholder="e.g., a sentence from the text"
                    style={{ width: '100%' }}
                  />
                  <small>Text snippet to use as goal</small>
                </div>

                <div className="form-group">
                  <label htmlFor="goal-id">Goal Node ID (optional):</label>
                  <input
                    id="goal-id"
                    type="text"
                    value={goalId}
                    onChange={(e) => setGoalId(e.target.value)}
                    placeholder="auto-detect"
                    list="node-ids"
                  />
                  <datalist id="node-ids">
                    {nodeIds.map(id => (
                      <option key={id} value={id} />
                    ))}
                  </datalist>
                  <small>Node ID (e.g. C1) or leave empty</small>
                </div>

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
                <div className="form-group soft-options" style={{ marginLeft: '2rem', marginTop: '0.5rem', marginBottom: '1rem' }}>
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

              <div className="checkbox-row">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={enableDiagnosis}
                    onChange={(e) => {
                      setEnableDiagnosis(e.target.checked);
                      if (!e.target.checked) setEnableRepair(false);
                    }}
                  />
                  <span>Enable Diagnosis (detect logical issues)</span>
                </label>
                <small>Identifies circular reasoning, unsupported inferences, contradictions</small>
              </div>

              {enableDiagnosis && (
                <div className="checkbox-row" style={{ marginLeft: '2rem' }}>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={enableRepair}
                      onChange={(e) => setEnableRepair(e.target.checked)}
                    />
                    <span>Generate Repairs</span>
                  </label>
                  <small>Propose minimal fixes for detected issues</small>
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

              {result && result.result?.argir?.metadata?.goal_id && (
                <div className="info" style={{
                  background: '#e3f2fd',
                  border: '1px solid #2196f3',
                  borderRadius: '4px',
                  padding: '8px 12px',
                  marginTop: '12px',
                  fontSize: '14px'
                }}>
                  ℹ️ Analysis used goal node: <strong>{result.result.argir.metadata.goal_id}</strong>
                </div>
              )}

              {result?.saved_hash && (
                <div className="info" style={{
                  background: '#e8f5e9',
                  border: '1px solid #4caf50',
                  borderRadius: '4px',
                  padding: '8px 12px',
                  marginTop: '12px',
                  fontSize: '14px'
                }}>
                  ✅ Query saved! Share this link: <a href={`?saved=${result.saved_hash}`} style={{ fontWeight: 'bold' }}>
                    {window.location.origin}/?saved={result.saved_hash}
                  </a>
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
                    content: <ResultDisplay type="findings" data={result.result.findings} argirData={result.result.argir} />,
                    disabled: !result.result.findings || result.result.findings.length === 0
                  },
                  {
                    id: 'diagnosis',
                    label: `Diagnosis${result.issues && result.issues.length > 0 ? ` (${result.issues.length})` : ''}`,
                    content: <DiagnosisDisplay issues={result.issues || []} repairs={result.repairs || []} argirData={result.result.argir} />,
                    disabled: !enableDiagnosis
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