import React from 'react';
import './DiagnosisDisplay.css';

interface Issue {
  id: string;
  type: string;
  target_node_ids: string[];
  evidence: any;
  detector_name: string;
  notes?: string;
}

interface Repair {
  id: string;
  issue_id: string;
  kind: string;
  patch: any;
  cost: number;
  verification: any;
}

interface DiagnosisDisplayProps {
  issues: Issue[];
  repairs: Repair[];
}

export const DiagnosisDisplay: React.FC<DiagnosisDisplayProps> = ({ issues, repairs }) => {
  const getIssueTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      'unsupported_inference': 'Unsupported Inference',
      'circular_support': 'Circular Reasoning',
      'contradiction_unresolved': 'Unresolved Contradiction',
      'weak_scheme_instantiation': 'Weak Argumentation Scheme',
      'goal_unreachable': 'Goal Unreachable',
    };
    return labels[type] || type;
  };

  const getIssueIcon = (type: string) => {
    const icons: Record<string, string> = {
      'unsupported_inference': '⚠️',
      'circular_support': '🔄',
      'contradiction_unresolved': '⚡',
      'weak_scheme_instantiation': '❓',
      'goal_unreachable': '🎯',
    };
    return icons[type] || '📍';
  };

  const getRepairsForIssue = (issueId: string) => {
    return repairs.filter(r => r.issue_id === issueId);
  };

  if (issues.length === 0) {
    return (
      <div className="diagnosis-display">
        <div className="no-issues">
          <span className="check-icon">✅</span>
          <p>No logical issues detected in the argument structure.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="diagnosis-display">
      <div className="issues-header">
        <h3>Detected Issues ({issues.length})</h3>
      </div>

      {issues.map((issue) => {
        const issueRepairs = getRepairsForIssue(issue.id);

        return (
          <div key={issue.id} className="issue-card">
            <div className="issue-header">
              <span className="issue-icon">{getIssueIcon(issue.type)}</span>
              <div className="issue-title">
                <h4>{getIssueTypeLabel(issue.type)}</h4>
                <span className="issue-id">{issue.id}</span>
              </div>
            </div>

            <div className="issue-body">
              {issue.target_node_ids.length > 0 && (
                <div className="affected-nodes">
                  <strong>Affected nodes:</strong> {issue.target_node_ids.join(', ')}
                </div>
              )}

              {issue.notes && (
                <div className="issue-description">
                  <p>{issue.notes}</p>
                </div>
              )}

              {issueRepairs.length > 0 ? (
                <div className="repairs-section">
                  <h5>Proposed Repairs</h5>
                  {issueRepairs.map((repair) => (
                    <div key={repair.id} className="repair-card">
                      <div className="repair-header">
                        <span className="repair-type">{repair.kind}</span>
                        <span className="repair-cost">Cost: {repair.cost}</span>
                      </div>

                      {repair.patch && (
                        <div className="repair-actions">
                          {repair.patch.add_nodes?.length > 0 && (
                            <div className="action">
                              <strong>Add premise:</strong>
                              <ul>
                                {repair.patch.add_nodes.map((node: any, i: number) => (
                                  <li key={i}>{node.text || node.id}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {repair.patch.add_edges?.length > 0 && (
                            <div className="action">
                              <strong>Add support:</strong>
                              <ul>
                                {repair.patch.add_edges.map((edge: any, i: number) => (
                                  <li key={i}>New premise → {edge.target}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {repair.patch.del_edges?.length > 0 && (
                            <div className="action">
                              <strong>Remove edges:</strong>
                              <ul>
                                {repair.patch.del_edges.map((edge: any, i: number) => (
                                  <li key={i}>{edge.source} → {edge.target}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {repair.patch.fol_hypotheses?.length > 0 && (
                            <div className="action">
                              <strong>FOL hypotheses:</strong>
                              <ul>
                                {repair.patch.fol_hypotheses.map((hyp: string, i: number) => (
                                  <li key={i}>{hyp}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {repair.patch.af_edits?.length > 0 && (
                            <div className="action">
                              <strong>AF modifications:</strong>
                              <ul>
                                {repair.patch.af_edits.map((edit: any, i: number) => {
                                  const [action, source, target] = edit;
                                  if (action === 'add_att') {
                                    return <li key={i}>➕ Add attack: {source} ⚔️ {target}</li>;
                                  } else if (action === 'del_att') {
                                    return <li key={i}>➖ Remove attack: {source} ⚔️ {target}</li>;
                                  }
                                  return <li key={i}>{action}: {source} → {target}</li>;
                                })}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}

                      {repair.verification && (
                        <div className="verification">
                          <strong>Verification:</strong>
                          {repair.verification.fol_entailed ? (
                            <span className="verified">✅ FOL: Repair is logically valid</span>
                          ) : (
                            <span className="not-verified">❌ FOL: Repair is not valid</span>
                          )}

                          {(() => {
                            const af = repair.verification.artifacts?.af_impact;

                            // For FOL repairs that add support edges, show a simple, clear message
                            if (af && af.explanation && af.explanation.includes("Support edges")) {
                              return (
                                <>
                                  {' '}
                                  <div className="af-status" style={{ display: 'inline' }}>
                                    <span>ℹ️ AF: No change expected (adds support only)</span>
                                    {' '}
                                    <details style={{ display: 'inline', marginLeft: '4px' }}>
                                      <summary style={{ cursor: 'help', color: '#6b7280', display: 'inline' }}>[why?]</summary>
                                      <div style={{
                                        position: 'absolute',
                                        backgroundColor: '#f9fafb',
                                        border: '1px solid #e5e7eb',
                                        padding: '8px',
                                        borderRadius: '4px',
                                        marginTop: '4px',
                                        maxWidth: '400px',
                                        fontSize: '0.875rem',
                                        zIndex: 10
                                      }}>
                                        In Dung argumentation frameworks, only <strong>attack</strong> edges affect acceptance.
                                        Support edges establish logical validity but don't influence which arguments are accepted or rejected.
                                      </div>
                                    </details>
                                  </div>
                                </>
                              );
                            }

                            // For other repairs, show impact
                            if (!af) {
                              if (repair.verification.af_goal_accepted !== undefined) {
                                return (
                                  <>
                                    {' '}
                                    {repair.verification.af_goal_accepted ? (
                                      <span className="verified">✅ AF: Improves acceptance</span>
                                    ) : (
                                      <span className="af-status">ℹ️ AF: No impact</span>
                                    )}
                                  </>
                                );
                              }
                              return null;
                            }

                            // Show changes only when something actually changes
                            const targetChanged = af.target?.changed;
                            const goalChanged = af.goal?.changed && af.goal?.id !== af.target?.id;

                            if (targetChanged || goalChanged) {
                              return (
                                <>
                                  {' '}
                                  <span className="verified">
                                    ✅ AF: {targetChanged ? `${af.target.id} ${af.target.after ? 'accepted' : 'rejected'}` : ''}
                                    {targetChanged && goalChanged ? ', ' : ''}
                                    {goalChanged ? `goal ${af.goal.id} ${af.goal.after ? 'accepted' : 'rejected'}` : ''}
                                  </span>
                                </>
                              );
                            }

                            return (
                              <>
                                {' '}
                                <span className="af-status">ℹ️ AF: No change in acceptance</span>
                              </>
                            );
                          })()}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="no-repairs">
                  <strong>Status:</strong> No automated repair available
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};