"""Measured Option 2 M2 workflow. Run with python -m dd2m2."""
from collections import Counter,defaultdict
from pathlib import Path
import csv
import gzip
import json
import re
import sys

from dd2 import aig, boolfn as bf, designs, envcheck, liberty, mapping, paths, provenance, redundancy, tools
from .cost import implementation,fit_model,predict_area,stage_forms
from .library import write_library
from . import cones,evaluate,tutorials


def write_csv(path,rows,fields=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(rows[0]) if rows else (fields or [])
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()})


def check(out,strict=False):
    versions=tools.versions();problems=[];notes=[]
    needed=[paths.given()/p for p in ['hd_reduced.lib','hd_usable.lib','scripts/map.sh']]
    needed += [paths.given()/'designs'/f'{d.name}.v' for d in designs.required()]
    full=paths.full_hd_lib();needed.append(full)
    for p in needed:
        if not p.is_file():problems.append(f'missing {paths.rel(p)}; run make setup')
    if sys.version_info<(3,11):problems.append('Python >=3.11 required')
    for key in ['yosys','yosys-abc','iverilog','sta']:
        if not versions.get(key):problems.append(f'{key} missing')
    imports={}
    if versions.get('yosys'):
        for name,count in [('hd_reduced.lib',189),('hd_usable.lib',307)]:
            p=paths.given()/name
            if p.is_file():
                imports[name]=envcheck.liberty_import_count(p,paths.build('check',name+'.log'))
                if imports[name]!=count:problems.append(f'{name}: expected {count} cells, got {imports[name]}')
    def version_tuple(text):
        m=re.search(r'(\d+)\.(\d+)',text or '')
        return tuple(map(int,m.groups())) if m else (0,0)
    overview={'python_3_11_or_newer':sys.version_info>=(3,11),
              'yosys_0_34_or_newer':version_tuple(versions.get('yosys'))>=(0,34),
              'iverilog_13_or_newer':version_tuple(versions.get('iverilog'))>=(13,0),
              'opensta_recent':bool(versions.get('sta'))}
    if not overview['yosys_0_34_or_newer']:
        notes.append('Yosys 0.33 is the Option 2 Table 1 reference version; overview lists >=0.34. Keep a separate reference executable.')
    if not overview['iverilog_13_or_newer']:notes.append('Overview lists Icarus >=13; install before checkpoint validation.')
    if strict and not all(overview.values()):problems.append('overview minimum tool versions not all satisfied')
    data={'status':'fail' if problems else 'pass','tools':versions,'overview_versions':overview,
          'liberty_import':imports,'problems':problems,'notes':notes,
          'inputs':provenance.hash_inputs([p for p in needed if p.is_file()]),'checked':provenance.now(),
          'scope':'Option 2 native CLI; no Option 1 GDS/SPICE checks are claimed'}
    provenance.write_json(out,data)
    for p in problems:print('FAIL',p)
    for p in notes:print('NOTE',p)
    print('Option 2 environment:',data['status'],flush=True)
    return not problems


def calibrate(out):
    full=paths.full_hd_lib();cells=liberty.read_cells(full)
    reduced=liberty.cell_names(paths.given()/'hd_reduced.lib');rows=[];excluded=[]
    for c in cells:
        if c.name not in reduced or not c.name.endswith('_1'):continue
        if len(c.inputs)>4:
            excluded.append({'name':c.name,'reason':'more than four inputs: outside candidate implementation domain'});continue
        # The HD calibration cells are actual existing cells: NAND4/NOR4
        # legitimately have four-stack native implementations. The candidate
        # three-stack constraint must not artificially inflate their features.
        cost=implementation(c.tt,len(c.inputs),max_series=4)
        rows.append(dict(name=c.name,function=c.function,arity=len(c.inputs),area_um2=c.area,
                         transistors=cost['transistors'],stages=cost['stages'],inverters=cost['inverters'],
                         realization=cost['expression'],method=cost['method']))
    model,records=fit_model(rows)
    model['source_liberty']=provenance.hash_inputs([full]);model['excluded']=excluded
    model['stack_limits']={'hd_calibration':4,'new_candidates':3}
    if not model['single_stage_cells'] or not model['multi_stage_cells']:
        raise ValueError('area model must cover both single and multi-stage HD cells')
    provenance.write_json(out/'area_model.json',model)
    write_csv(out/'area_model_fit.csv',records)
    write_csv(out/'area_model_excluded.csv',excluded,['name','reason'])
    print('Area model:',len(rows),'HD x1 cells; LOO MAPE',round(model['loo_mean_absolute_percent_error'],2),'%',flush=True)
    return cells,model


def baseline(names,out):
    rows=[]
    for name in names:
        d,src=tutorials.resolve(name)
        for script in mapping.SCRIPTS:
            dest=out/'mapping'/name/'baseline'/script
            r=evaluate.map_design(d,src,paths.given()/'hd_reduced.lib',script,dest)
            eq=evaluate.verify_mapping(d,paths.given()/'hd_reduced.lib',dest)
            rows.append(r|{'equivalence':eq['status']})
            print('Baseline',name,script,r['area_um2'],'equivalence',eq['status'],flush=True)
    provenance.write_json(out/'baseline_mappings.json',rows)
    return rows


def candidates(names,out,cells,model):
    counts=defaultdict(Counter)
    # Original M1 discovery counts are retained separately for each AIG variant.
    for name in names:
        for variant in ['synth','restructured']:
            p=(out/'tutorial_discovery'/name/'cuts'/(variant+'.summary.json') if name in tutorials.SPECS
               else paths.results('m1','cuts',name,variant+'.summary.json'))
            if p.is_file():
                hist=json.loads(p.read_text()).get('p_histogram',{})
                for key,count in hist.items():
                    arity,tt=key.split(':');n=int(arity)
                    if 2<=n<=4:counts[(n,int(tt,16))][variant]+=count
    occurrences=defaultdict(list);idx=redundancy.HdIndex(cells)
    for name in names:
        for script in mapping.SCRIPTS:
            p=out/'mapping'/name/'baseline'/script/'mapped.json'
            print('Mapped-cone costs:',name,script,flush=True)
            for r in cones.mapped_cuts(json.loads(p.read_text()),tutorials.resolve(name)[0].top,cells):
                key=(r['arity'],r['tt']);counts[key]['mapped']+=1
                occurrences[key].append(r|{'design':name,'script':script})
    cell_by_name={c.name:c for c in cells}
    invs=[c.area for c in cells if len(c.inputs)==1 and c.tt==1]
    inv_area=min(invs)
    baselines=json.loads((out/'baseline_mappings.json').read_text())
    base={(r['design'],r['script']):r['area_um2'] for r in baselines}
    results=[]
    occurrence_path=out/'candidate_occurrences.jsonl.gz'
    with gzip.open(occurrence_path,'wt') as f:
        for (n,tt),hist in sorted(counts.items()):
            cls=redundancy.classify(tt,n,idx);cost=implementation(tt,n)
            area=predict_area(model,cost);witness=cls['witness'];threshold=None
            if witness:
                threshold=cell_by_name[witness['cell']].area+(inv_area if cls['class']==redundancy.INVERTER else 0)
            keep=cls['class']==redundancy.NEW or (cls['class']!=redundancy.EXISTS and area<(threshold or 0))
            savings=defaultdict(float);used=defaultdict(set);accepted=0;replace=0.
            for occ in sorted(occurrences[(n,tt)],key=lambda r:(-r['replaced_area_um2'],r['design'],r['script'],r['root'])):
                f.write(json.dumps({'class_key':f'{n}:{bf.to_hex(tt,n)}'}|occ)+'\n')
                k=(occ['design'],occ['script']);removed=set(occ['removed_cells'])
                benefit=occ['replaced_area_um2']-area
                if benefit>0 and not removed&used[k]:
                    used[k]|=removed;savings[k]+=benefit;accepted+=1;replace+=occ['replaced_area_um2']
            objective_names=[name for name in names if name in {d.name for d in designs.required()}]
            predicted=sum(min(base[(name,s)] for s in mapping.SCRIPTS)-
                          min(base[(name,s)]-savings[(name,s)] for s in mapping.SCRIPTS) for name in objective_names)
            r=dict(key=f'{n}:{bf.to_hex(tt,n)}',arity=n,truth_table=bf.to_hex(tt,n),
                   pn_class=bf.to_hex(bf.canon_pn(tt,n),n),npn_class=bf.to_hex(bf.canon_npn(tt,n),n),
                   expression=cost['expression'],redundancy_class=cls['class'],witness=witness,
                   transistors=cost['transistors'],stages=cost['stages'],inverters=cost['inverters'],
                   max_series=cost['max_series'],estimated_area_um2=area,
                   existing_implementation_threshold_um2=threshold,eligible=keep,
                   aig_synth_occurrences=hist['synth'],aig_restructured_occurrences=hist['restructured'],
                   mapped_occurrences=len(occurrences[(n,tt)]),nonoverlapping_profitable_occurrences=accepted,
                   replaced_area_for_selected_occurrences_um2=replace,
                   estimated_best_of_both_saving_um2=predicted,cost=cost)
            results.append(r)
    results.sort(key=lambda r:(not r['eligible'],-r['estimated_best_of_both_saving_um2'],-r['mapped_occurrences'],r['key']))
    for i,r in enumerate(results,1):r['rank']=i
    provenance.write_json(out/'candidates.json',results)
    fields=['rank','key','arity','truth_table','expression','redundancy_class','witness','eligible',
            'transistors','stages','inverters','max_series','estimated_area_um2',
            'existing_implementation_threshold_um2','aig_synth_occurrences','aig_restructured_occurrences',
            'mapped_occurrences','nonoverlapping_profitable_occurrences','replaced_area_for_selected_occurrences_um2',
            'estimated_best_of_both_saving_um2']
    write_csv(out/'ranked_candidates.csv',results,fields)
    write_csv(out/'redundancy_report.csv',results,['key','expression','redundancy_class','witness','eligible',
                                                'estimated_area_um2','existing_implementation_threshold_um2'])
    provenance.write_json(out/'candidate_ranking_method.json',{
        'source':'actual cells of the reduced-library A/B mappings; primary-input/FF boundaries',
        'shared_logic':'only cells with no outside consumers except the cut root are reclaimable',
        'overlap':'greedy non-overlapping occurrences per candidate, design and script; classes can still overlap',
        'estimate':'predicted best-of-both aggregate; final areas are measured by remapping',
        'objective_designs':[n for n in names if n in {d.name for d in designs.required()}],
        'aig_frequency':'synth/restructured counts are separate descriptions of the same designs, not added as physical instances'})
    return results


def requests(out,group,limit,candidates):
    eligible=[r for r in candidates if r['eligible']]
    chosen=eligible[:limit];reqs=[]
    for i,c in enumerate(chosen,1):
        name=f'dd2_g{group}__n{c["arity"]}_{c["truth_table"][2:].lower()}_1'
        r={'request_id':f'M2-{i:03d}','name':name,'inputs':list('ABCD'[:c['arity']]),'output':'Y',
           'expression':c['expression'],'truth_table':c['truth_table'],'sizing':'hd',
           'estimated_area_um2':c['estimated_area_um2']}
        provenance.write_json(out/'requests'/f'{name}.json',r);reqs.append(r)
    provenance.write_json(out/'requests.json',reqs)
    group_name_path=paths.ROOT/'config/group_name.txt'
    group_name=group_name_path.read_text().strip() if group_name_path.is_file() else f'Group {group}'
    provenance.write_json(out/'selection.json',{'group':group,'group_name':group_name,'selected_keys':[r['key'] for r in chosen],
        'rule':f'first {limit} eligible ranked candidates; M2 exploratory set, not final greedy selection',
        'note':'zero predicted or actual saving is retained as an experimental result, never forced positive'})
    return reqs


def measure(names,out,lib,reqs):
    rows=[];base=json.loads((out/'baseline_mappings.json').read_text());lookup={(r['design'],r['script']):r for r in base}
    new_names={r['name'] for r in reqs}
    for name in names:
        d,src=tutorials.resolve(name)
        for script in mapping.SCRIPTS:
            dest=out/'mapping'/name/'extended'/script
            r=evaluate.map_design(d,src,lib,script,dest);eq=evaluate.verify_mapping(d,lib,dest)
            timing=evaluate.timing(d,lib,dest)
            b=lookup[(name,script)];base_dir=out/'mapping'/name/'baseline'/script
            bt=evaluate.timing(d,paths.given()/'hd_reduced.lib',base_dir)
            instances=sum(v for k,v in r['cell_counts'].items() if k.lstrip('\\') in new_names)
            rows.append(dict(design=name,script=script,baseline_um2=b['area_um2'],extended_um2=r['area_um2'],
                reduction_pct=100*(b['area_um2']-r['area_um2'])/b['area_um2'],new_cell_instances=instances,
                baseline_equivalence=b['equivalence'],extended_equivalence=eq['status'],
                baseline_delay_ns=bt['worst_arrival_ns'],extended_delay_ns=timing['worst_arrival_ns'],
                baseline_timing_status=bt['status'],extended_timing_status=timing['status'],
                effect_note=('library-induced remapping; no new cell instantiated' if instances==0 and abs(b['area_um2']-r['area_um2'])>1e-6
                             else 'new cell instantiated' if instances else 'no new cell instantiated')))
            print('Extended',name,script,'area',r['area_um2'],'new instances',instances,'CEC',eq['status'],flush=True)
    write_csv(out/'table5_estimated.csv',rows)
    best=[]
    for name in names:
        ds=[r for r in rows if r['design']==name];b=min(r['baseline_um2'] for r in ds);e=min(r['extended_um2'] for r in ds)
        best.append(dict(design=name,baseline_best_um2=b,extended_best_um2=e,saving_um2=b-e,reduction_pct=100*(b-e)/b))
    required_names={d.name for d in designs.required()}
    b=sum(r['baseline_best_um2'] for r in best if r['design'] in required_names)
    e=sum(r['extended_best_um2'] for r in best if r['design'] in required_names)
    best.append(dict(design='TOTAL',baseline_best_um2=b,extended_best_um2=e,saving_um2=b-e,reduction_pct=100*(b-e)/b))
    write_csv(out/'best_of_both_estimated.csv',best)
    return rows,best


def witness_report(out):
    p=paths.results('m1','redundancy','self_test.json')
    if not p.exists():return {'status':'missing M1 self-test'}
    st=json.loads(p.read_text());rows=st.get('table4',[]);openrows=[r for r in rows if r.get('status')!='match']
    witnesses=[]
    for row in openrows:
        for w in row.get('witnesses',[]):
            t=int(w['tt'],16);f=stage_forms(4).get(t^bf.mask(4))
            if not f:continue
            key,expr=f;y='!('+expr+')'
            witnesses.append({'truth_table':w['tt'],'expression':y,'literals':key[0],
                              'transistors':2*key[0],'n_series':key[2],'p_series':key[3],
                              'truth_table_verified':bf.eval_expr(y,list('ABCD'))==t})
    write_csv(out/'reference_count_witnesses.csv',witnesses,
              ['truth_table','expression','literals','transistors','n_series','p_series','truth_table_verified'])
    data={'status':'unresolved reference disagreement' if openrows else 'match',
          'rows':openrows,'witnesses':witnesses,'note':'Original checks and reference numbers preserved. No TA acceptance is inferred.'}
    provenance.write_json(out/'reference_count_review.json',data)
    question=['# Table 4 clarification for GB4','',
              'The checker reproduces the Exists, Exists-with-inverter, Contained and New counts,',
              'and the nine one-stage and eight read-once classes. The limited one-stage row',
              'gives six classes where the handout gives five. The reference number remains unchanged.','',
              '| Truth table | Expression | Transistors | NMOS series | PMOS series |',
              '|---|---|---:|---:|---:|']
    for w in witnesses:
        expr=w['expression'].replace('|',r'\|')
        question.append(f'| {w["truth_table"]} | `{expr}` | {w["transistors"]} | {w["n_series"]} | {w["p_series"]} |')
    question += ['', 'Each row has a verified 16-row truth table and uses six literal occurrences,',
                 'giving six NMOS plus six PMOS transistors in complementary series/parallel networks.',
                 'Input A is the least significant truth-table variable.', '',
                 'Question for the TA: which of these six realizations is excluded by the reference,',
                 'and what additional restriction excludes it? Or should the reference count be six?',
                 'No correction or acceptance is assumed by the tool.']
    (out/'reference_count_question.md').write_text('\n'.join(question)+'\n')
    return data


def plots(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with (out/'area_model_fit.csv').open() as f:fit=list(csv.DictReader(f))
    fig,ax=plt.subplots(figsize=(6,5));x=[float(r['area_um2']) for r in fit];y=[float(r['loo_predicted_um2']) for r in fit]
    for label in ['single stage','multiple stages']:
        rows=[i for i,r in enumerate(fit) if (int(r['stages'])==1)==(label=='single stage')]
        ax.scatter([x[i] for i in rows],[y[i] for i in rows],label=label,alpha=.75)
    hi=max(x+y);ax.plot([0,hi],[0,hi],color='black',linestyle='--',linewidth=1)
    ax.set(xlabel='HD area (um²)',ylabel='Held-out predicted area (um²)',title='Area model: leave-one-out validation');ax.legend();fig.tight_layout()
    fig.savefig(out/'area_model_validation.png',dpi=180);plt.close(fig)
    with (out/'best_of_both_estimated.csv').open() as f:rows=[r for r in csv.DictReader(f) if r['design']!='TOTAL']
    fig,ax=plt.subplots(figsize=(8,4));ax.bar([r['design'] for r in rows],[float(r['reduction_pct']) for r in rows],color='#236b8e')
    ax.axhline(0,color='black',linewidth=.8);ax.set(ylabel='Area reduction (%)',title='Measured best-of-both savings: estimated cells');fig.tight_layout()
    fig.savefig(out/'area_reduction_estimated.png',dpi=180);plt.close(fig)
    cs=json.loads((out/'candidates.json').read_text());cs=[r for r in cs if r['eligible']][:10]
    if cs:
        fig,ax=plt.subplots(figsize=(8,5));ax.barh([r['key'] for r in cs][::-1],[r['estimated_best_of_both_saving_um2'] for r in cs][::-1])
        ax.set(xlabel='Estimated aggregate saving (um²)',title='Candidate ranking heuristic; overlap may change savings');fig.tight_layout()
        fig.savefig(out/'candidate_ranking.png',dpi=180);plt.close(fig)


def summary(out,names,rows,best,reference,env,tutorial_results=None):
    valid=all(r['baseline_equivalence']=='pass' and r['extended_equivalence']=='pass' for r in rows)
    timing_ok=all(r['baseline_timing_status']=='pass' and r['extended_timing_status']=='pass' for r in rows)
    checks={'mapping_equivalence':valid,'timing_runs':timing_ok,'reference_table4_agrees':reference['status']=='match',
            'overview_tool_versions':all(env['overview_versions'].values()),
            'all_six_required_designs':set(names)>={d.name for d in designs.required()}}
    tutorial_status={n:(tutorial_results or {}).get(n,{'rtl_supplied':tutorials.supplied(n),
                        'mapping_and_gate_simulation_verified':False}) for n in tutorials.SPECS}
    checks['tutorial_designs_mapped_and_simulated']=all(
        r['mapping_and_gate_simulation_verified'] for r in tutorial_status.values())
    if not checks['tutorial_designs_mapped_and_simulated']:valid=False
    remaining=[]
    if not checks['mapping_equivalence']:remaining.append('Every baseline and extended mapping must pass CEC.')
    if not checks['timing_runs']:remaining.append('Every OpenSTA run must pass without tool errors.')
    if not checks['all_six_required_designs']:remaining.append('All six required benchmark designs must be measured.')
    if not checks['tutorial_designs_mapped_and_simulated']:
        remaining.append('Original tutorial RTL and all four A/B baseline/extended gate simulations must pass.')
    if not checks['overview_tool_versions']:remaining.append('Overview minimum tool versions must be satisfied.')
    if not checks['reference_table4_agrees']:remaining.append('Table 4: six verified witnesses versus five in the handout remains unresolved; obtain clarification from the TA.')
    data={'experimental_flow_status':'pass' if valid and timing_ok else 'fail',
          'checkpoint_ready':all(checks.values()),'checks':checks,'tutorial_inputs':tutorial_status,
          'remaining':remaining,
          'final_only':['real-cell generator results','final greedy selection','30-percent experiment','final reports'],
          'written':provenance.now()}
    provenance.write_json(out/'readiness.json',data)
    lines=['# Option 2 M2 measured evidence','',f'Experimental flow: **{data["experimental_flow_status"]}**.',
           f'Checkpoint ready: **{data["checkpoint_ready"]}**. See `readiness.json` for blockers.','',
           'Area values below use estimated cells; their timing/capacitances are placeholders.','',
           '| Design | Baseline best (um²) | Extended best (um²) | Reduction |', '|---|---:|---:|---:|']
    lines += [f'| {r["design"]} | {r["baseline_best_um2"]:.4f} | {r["extended_best_um2"]:.4f} | {r["reduction_pct"]:.3f}% |' for r in best]
    lines += ['', '## Evidence', '', '- `ranked_candidates.csv`, `redundancy_report.csv`, `candidate_occurrences.jsonl.gz`',
              '- `area_model.json`, `area_model_fit.csv`, `area_model_validation.png`',
              '- `requests/`, `requests.json`, `selection.json`, `extended_library.json`',
              '- `table5_estimated.csv`, `best_of_both_estimated.csv`, `area_reduction_estimated.png`',
              '- `mapping/`: scripts, netlists, hashes, mapping/CEC/sequential-equivalence/timing logs',
              '- `reference_count_review.json`, `reference_count_witnesses.csv`', '', '## Limitations','',
              '- Ranking is a heuristic; the remapped area, not occurrence frequency, is the measured result.',
              '- Cost features describe explicit Boolean realizations, not transistor extraction from installed HD cells.',
              '- The six-versus-five reference discrepancy remains explicit until resolved with the TA.',
              '- Tutorial sources/testbenches are unchanged earlier submissions, installed outside git. GLS is functional, with no SDF or timing-check claim.',
              '- TOTAL and the ranking objective cover the six required benchmark designs; tutorial rows are shown separately.',
              '- Final reports, real-cell results and sensitivity/greedy experiments are not M2 outputs.']
    (out/'summary.md').write_text('\n'.join(lines)+'\n')
    return data


def run(group,limit,names,out):
    out=Path(out).absolute();out.mkdir(parents=True,exist_ok=True)
    names=list(dict.fromkeys(list(names)+[n for n in tutorials.SPECS if tutorials.supplied(n)]))
    if not check(out/'environment.json'):return 1
    env=json.loads((out/'environment.json').read_text())
    import subprocess
    p=subprocess.run([sys.executable,'-m','pip','freeze'],capture_output=True,text=True)
    (out/'python_packages.txt').write_text(p.stdout)
    cells,model=calibrate(out)
    discovery=tutorials.discovery(names,out)
    if discovery:write_csv(out/'tutorial_aig_cuts.csv',discovery)
    baseline(names,out)
    cs=candidates(names,out,cells,model)
    reqs=requests(out,group,limit,cs)
    lib=out/'hd_extended_estimated.lib';write_library(paths.given()/'hd_reduced.lib',lib,reqs)
    if out==paths.results('m2'):
        import shutil
        (paths.ROOT/'libs').mkdir(exist_ok=True)
        shutil.copy2(lib,paths.ROOT/'libs/hd_extended_estimated.lib')
    imported=envcheck.liberty_import_count(lib,out/'liberty_import.log');want=189+len(reqs)
    provenance.write_json(out/'extended_library.json',{'path':paths.rel(lib),'sha256':provenance.sha256(lib),
        'imported_cells':imported,'expected_cells':want,'status':'pass' if imported==want else 'fail'})
    if imported!=want:raise RuntimeError(f'extended library imported {imported}, expected {want}')
    rows,best=measure(names,out,lib,reqs)
    ref=witness_report(out);plots(out)
    tutorial_results=tutorials.verify(names,out,lib)
    data=summary(out,names,rows,best,ref,env,tutorial_results)
    if out==paths.results('m2'):showcase(out)
    print('M2 experimental flow:',data['experimental_flow_status'],flush=True)
    print('Checkpoint ready:',data['checkpoint_ready'],'(see readiness.json; no tag is created)',flush=True)
    return 0 if data['experimental_flow_status']=='pass' else 1


def showcase(out):
    """Small TA-facing copies of existing evidence; never recompute measurements."""
    import shutil
    out=Path(out);dest=paths.ROOT/'TA_M2'
    copies={
        'figures/01_area_model_validation.png':out/'area_model_validation.png',
        'figures/02_candidate_ranking.png':out/'candidate_ranking.png',
        'figures/03_measured_area_reduction.png':out/'area_reduction_estimated.png',
        'tables/01_m1_reference_table.csv':paths.results('m1','table1.csv'),
        'tables/02_ranked_candidates.csv':out/'ranked_candidates.csv',
        'tables/03_area_model_fit.csv':out/'area_model_fit.csv',
        'tables/04_table5_estimated.csv':out/'table5_estimated.csv',
        'tables/05_best_of_both.csv':out/'best_of_both_estimated.csv',
        'tables/06_tutorial_aigs_and_cuts.csv':out/'tutorial_aig_cuts.csv',
        'TABLE4_CLARIFICATION.md':out/'reference_count_question.md',
        'table4_witnesses.csv':out/'reference_count_witnesses.csv',
        'readiness.json':out/'readiness.json',
    }
    for name in ['tests.log','tool_versions.log']:
        p=paths.results('validation',name)
        if p.is_file():copies['validation/'+name]=p
    missing=[str(src) for src in copies.values() if not src.is_file()]
    if missing:raise ValueError('Cannot prepare complete TA folder; missing: '+', '.join(missing))
    model=json.loads((out/'area_model.json').read_text())
    ready=json.loads((out/'readiness.json').read_text())
    library=json.loads((out/'extended_library.json').read_text())
    with (out/'best_of_both_estimated.csv').open() as f:best=list(csv.DictReader(f))
    with paths.results('m1','cuts/summary.csv').open() as f:cuts=list(csv.DictReader(f))
    checks={}
    for label,pattern in [('CEC','mapping/**/equivalence.json'),('OpenSTA','mapping/**/timing.json'),
                          ('Tutorial simulations','tutorial_simulations/**/simulation.json')]:
        records=[json.loads(p.read_text()) for p in out.glob(pattern)]
        checks[label]=f'{sum(r.get("status")=="pass" for r in records)}/{len(records)} pass'
    manifest=[]
    for rel,src in copies.items():
        p=dest/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,p)
        manifest.append({'copy':rel,'source':paths.rel(src),'sha256':provenance.sha256(src)})
    provenance.write_json(dest/'evidence_sources.json',manifest)
    lines=['# GB4 — Option 2, Milestone 2','',
           '**Start here for the TA meeting.** Figures and tables are copies of the saved run; full evidence is in [results/m2](../results/m2/).','',
           f'Experimental flow: **{ready["experimental_flow_status"]}**. Full checkpoint ready: **{ready["checkpoint_ready"]}**.',
           'Table 4 remains unresolved: six verified qualifying classes versus five in the handout. No TA acceptance is assumed.',
           'See [the clarification and six examples](TABLE4_CLARIFICATION.md).','',
           '## What was verified','',
           f'- M1 cuts independently checked: {sum(int(r["checked"]) for r in cuts):,}.',
           f'- Extended Liberty import: {library["imported_cells"]}/{library["expected_cells"]} cells.',
           f'- Area model: {model["training_cells"]} HD x1 cells; leave-one-out mean absolute percentage error {model["loo_mean_absolute_percent_error"]:.2f}%.']
    lines += [f'- {label}: {status}.' for label,status in checks.items()]
    testlog=paths.results('validation','tests.log')
    if testlog.is_file():
        summaries=[line.strip() for line in testlog.read_text().splitlines() if re.search(r'\b\d+ passed\b',line)]
        if summaries:lines.append('- Tests: '+summaries[-1]+'. See [saved test log](validation/tests.log).')
    lines += ['', '## Measured best-of-both area','',
              '| Design | Baseline (µm²) | Extended (µm²) | Area reduction |',
              '|---|---:|---:|---:|']
    for r in best:
        lines.append(f'| {r["design"]} | {float(r["baseline_best_um2"]):.4f} | {float(r["extended_best_um2"]):.4f} | {float(r["reduction_pct"]):.4f}% |')
    lines += ['', 'TOTAL covers the six required benchmarks. Tutorial rows are separate. A negative reduction means area increased.',
              'M1 reproduces the Yosys 0.33 reference table; M2 uses the newer recorded toolchain with identical A/B commands on each side.',
              'These areas use estimated cells. New-cell timing/capacitance values are placeholders; OpenSTA results are pre-layout comparisons.',
              '', '## Figures','',
              '### 1. Area-model validation','',
              'Held-out predictions against the HD cell areas; the dashed line represents exact predictions.','',
              '![Area-model validation](figures/01_area_model_validation.png)','',
              '### 2. Candidate ranking','',
              'Heuristic predicted savings used for ranking. Overlapping cuts and actual remapping can change the outcome.','',
              '![Candidate ranking](figures/02_candidate_ranking.png)','',
              '### 3. Measured area reduction','',
              'Measured from the baseline and extended mappings, taking the smaller A/B area on each side.','',
              '![Measured area reduction](figures/03_measured_area_reduction.png)','',
              '## Tables','']
    lines += [f'- [{Path(rel).name}]({rel})' for rel in copies if rel.startswith('tables/')]
    lines += ['', '## Still open','',*['- '+s for s in ready['remaining']],
              '', 'Final milestone: real generator cells, final greedy selection, real-area reruns, cell-by-cell curve, 30% experiment, final reports and full unseen-design demo.',
              '', 'Copies are refreshed by `make ta` and after `make m2`. `evidence_sources.json` records their source hashes.']
    (dest/'README.md').write_text('\n'.join(lines)+'\n')
    print('TA meeting folder: TA_M2/README.md',flush=True)
    return dest


def m1_summary():
    m1=paths.results('m1');checks=[]
    def load(name):return json.loads((m1/name).read_text())
    with (m1/'table1.csv').open() as f:table=list(csv.DictReader(f))
    with (m1/'cuts/summary.csv').open() as f:cuts=list(csv.DictReader(f))
    st=load('redundancy/self_test.json');hd=load('hd_classes.json')
    checks=[('Table 1',len(table)==12 and all(r['matches_handout']=='yes' for r in table)),
            ('AIG manifest',load('aigs/manifest.json')['status']=='pass'),
            ('Cuts checked',len(cuts)==12 and all(r['status']=='pass' and int(r['failures'])==0 and int(r['cuts'])==int(r['checked']) for r in cuts)),
            ('HD class table',hd['run']['status']=='pass'),
            ('HD cells recognized',st['hd_cells_exists']==st['hd_cells_total']),
            ('All Table 4 counts match',all(r['status']=='match' for r in st['table4']))]
    text=['# Option 2 M1 evidence','', '| Requirement | Status |','|---|---|']
    text += [f'| {n} | {"pass" if ok else "OPEN / FAIL"} |' for n,ok in checks]
    text += ['',f'Checked cuts: {sum(int(r["checked"]) for r in cuts)}.',
             'The original six-versus-five discrepancy remains visible; no checkpoint acceptance is inferred.']
    (m1/'summary.md').write_text('\n'.join(text)+'\n');print('\n'.join(text))
    return 0 if all(ok for name,ok in checks if name!='All Table 4 counts match') else 1
