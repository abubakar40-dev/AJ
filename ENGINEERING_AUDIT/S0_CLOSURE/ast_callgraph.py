#!/usr/bin/env python3
"""AST call graph helper for S0 closure (E2).
Parses aj/*.py and lists callers of target functions/methods.
Compares with grep list and reports callers grep may miss (best-effort).
Limitations stated in output/report: dynamic dispatch, getattr, runtime monkeypatch,
reflection, threading/callback indirection, cross-process, and non-ast-visible calls.
"""
from __future__ import annotations
import ast, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AJ = ROOT / 'aj'
TARGETS = {
    'tasks.transition','TaskRecord.transition','dead_letter','requeue','abandon','delegate',
    '_prepare_delegated_child_for_scheduling','_reconcile_delegation_parent','resume','retry','recover',
    'cancel_task','cancel','run_once','_dispatch_one','reconcile','import_record','save','mutate',
    'transition'  # to catch TaskRecord.transition and qualified forms
}

def dotted_name(node):
    parts=[]
    cur=node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur=cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return '.'.join(reversed(parts))
    return None

def collect_calls(path: Path):
    try:
        src = path.read_text(encoding='utf-8')
        tree = ast.parse(src)
    except Exception as e:
        return [{"file": str(path.relative_to(ROOT)), "error": f"parse_error:{e}"}]
    # map line ranges to enclosing function/method
    func_ranges=[]  # (start,end,name)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start=getattr(node,'lineno',0)
            end=getattr(node,'end_lineno',start)
            func_ranges.append((start,end,node.name))
    func_ranges.sort()
    def enclosing(lineno):
        # innermost by smallest span among those containing lineno
        best=None
        for s,e,name in func_ranges:
            if s<=lineno<=e:
                if best is None or (e-s) < (best[1]-best[0]):
                    best=(s,e,name)
        return best[2] if best else '<module>'
    results=[]
    class V(ast.NodeVisitor):
        def visit_Call(self,node):
            name=None
            fn=node.func
            if isinstance(fn, ast.Attribute):
                name=fn.attr
                full=dotted_name(fn)
            elif isinstance(fn, ast.Name):
                name=fn.id
                full=fn.id
            else:
                full=None
            # match targets: either bare name in targets or endswith .target for qualified
            matched=None
            if name in TARGETS:
                matched=name
            if full:
                for t in TARGETS:
                    if full==t or full.endswith('.'+t) or full.endswith('.tasks.'+t):
                        matched=t if t!='transition' else name
            # special handling: tasks.transition / TaskRecord.transition
            if full and (full.endswith('.tasks.transition') or full=='tasks.transition'):
                matched='tasks.transition'
            if full and full.endswith('.transition') and 'TaskRecord' in full:
                matched='TaskRecord.transition'
            # also keep explicit task store transition calls via .tasks.transition even if name==transition
            if matched:
                lineno=getattr(node,'lineno',0)
                results.append({
                    'file': str(path.relative_to(ROOT)),
                    'line': lineno,
                    'caller': enclosing(lineno),
                    'call': full or name,
                    'target': matched,
                })
            self.generic_visit(node)
    V().visit(tree)
    return results

def main():
    all_results=[]
    for py in sorted(AJ.rglob('*.py')):
        all_results.extend(collect_calls(py))
    # grep comparison for key patterns
    grep_cmds = [
        (['grep','-rn','\\.tasks\\.transition(','aj','tests'], 'grep_tasks_transition'),
        (['grep','-rn','dead_letter\\|requeue\\|abandon\\|delegate\\|run_once\\|_dispatch_one\\|import_record','aj'], 'grep_selected'),
    ]
    grep_out={}
    for cmd,label in grep_cmds:
        try:
            p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
            grep_out[label]={'exit':p.returncode,'stdout':p.stdout}
        except Exception as e:
            grep_out[label]={'error':str(e)}
    out={
        'targets': sorted(TARGETS),
        'ast_results': all_results,
        'grep': grep_out,
        'notes': [
            'AST cannot see dynamic dispatch (getattr/setattr/callables in vars), reflection, monkeypatch indirection, decorator/wrapper effects at runtime, threaded/callback/registered handler invocation paths, string-eval/exec, cross-process/CLI-subprocess behavior, or calls in non-ast-visible generated code.',
            'AST reports syntactic call sites in aj/*.py only (by design of this script run).'
        ]
    }
    out_path = ROOT/'ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph_results.json'
    out_path.write_text(json.dumps(out,indent=2))
    # human summary
    lines=[]
    for r in all_results:
        if 'error' in r:
            lines.append(f"PARSE_ERROR {r['file']}: {r['error']}")
        else:
            lines.append(f"{r['file']}:{r['line']} | caller={r['caller']} | call={r['call']} | target={r['target']}")
    (ROOT/'ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph_results.txt').write_text('\n'.join(lines))
    print('wrote', out_path)
    print('entries', len(all_results))

if __name__=='__main__':
    main()
