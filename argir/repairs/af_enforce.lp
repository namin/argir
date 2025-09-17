% AF Enforcement skeleton (no semantics here)
% Input facts expected from Python:
%   arg0(A).             % original arguments
%   att0(A,B).           % original attacks
%   cand_del(A,B).       % deletable attacks
%   cand_add(A,B).       % addable attacks
%   attacks_goal(X).     % nodes currently attacking the goal
%   goal(G).             % goal to accept

% Arguments (original + optional abstract defender)
arg(A) :- arg0(A).
{ use_defender }.
arg(def) :- use_defender.

% Attacks with edit choices
att(A,B) :- att0(A,B), not del_att(A,B).
att(A,B) :- add_att(A,B).

% Edit choices
{ del_att(X,Y) : att0(X,Y), cand_del(X,Y) }.
{ add_att(X,Y) : arg0(X), arg0(Y), X != Y, cand_add(X,Y) }.
{ add_att(def, X) : arg0(X), attacks_goal(X) } :- use_defender.

% --- Semantics are appended by Python (must define in/1 over arg/1, att/2) ---
% e.g., admissible / grounded / stable (see af_clingo.ENCODING)

% Enforce credulous acceptance of the goal
:- goal(G), not in(G).

% Optimization: 1) minimize edit cost (lexicographically), 2) maximize extension size
#minimize { 1@1,X,Y : del_att(X,Y); 1@1,X,Y : add_att(X,Y); 2@2 : use_defender }.
#maximize { 1@0,X : in(X), arg(X) }.

% Output edits (semantics may also #show in/1)
#show del_att/2.
#show add_att/2.
#show use_defender/0.
#show in/1.