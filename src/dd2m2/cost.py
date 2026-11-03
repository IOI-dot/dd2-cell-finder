"""Costs of explicit static-CMOS realizations, not physical-cell characterization.

Try factored one-stage forms with shared input/output inversions; otherwise
construct NAND2/3 and dual NOR2/3 networks from exact minimum-literal covers. Every
returned realization is evaluated against the requested complete truth table.
The area regression is fitted to the same implementation-cost features of HD
x1 cells, with leave-one-out errors and whole-site width quantization. Existing
HD calibration cells may use four-stack native stages; new candidates remain
limited to at most three transistors in series per stage.
"""
from functools import lru_cache
from itertools import combinations, product
import math

from dd2 import boolfn as bf

SITE_AREA = 2.72 * 0.46


@lru_cache(None)
def stage_forms(n, max_literals=6, max_series=3):
    sizes = {1: {(bf.var_tt(k,n),1,1): 'ABCD'[k] for k in range(n)}}
    best = {}
    for size in range(1,max_literals+1):
        if size > 1:
            forms = {}
            for a in range(1,size//2+1):
                for (ta,na,pa),ea in sizes[a].items():
                    for (tb,nb,pb),eb in sizes[size-a].items():
                        for t,ns,ps,op in [(ta&tb,na+nb,max(pa,pb),'&'),
                                           (ta|tb,max(na,nb),pa+pb,'|')]:
                            if ns<=max_series and ps<=max_series:
                                forms.setdefault((t,ns,ps),f'({ea}{op}{eb})')
            sizes[size] = forms
        for (t,ns,ps),expr in sizes[size].items():
            key = (size,max(ns,ps),ns,ps,expr)
            if t not in best or key < best[t][0]:
                best[t] = (key,expr)
    return best


@lru_cache(None)
def sop_cover(tt,n):
    if not tt: return ()
    implicants=[]
    for pattern in product((-1,0,1),repeat=n):
        cover=sum(1<<r for r in range(1<<n)
                  if all(v<0 or ((r>>k)&1)==v for k,v in enumerate(pattern)))
        if cover and cover&tt==cover:
            implicants.append((cover,pattern,sum(v>=0 for v in pattern)))
    primes=[p for p in implicants if not any(p[0]!=q[0] and p[0]&q[0]==p[0]
                                           for q in implicants)]
    @lru_cache(None)
    def solve(left):
        if not left: return (0,0,())
        bit=left&-left
        opts=[]
        for i,(cover,pattern,lits) in enumerate(primes):
            if cover&bit:
                c=solve(left&~cover)
                opts.append((lits+c[0],1+c[1],(i,)+c[2]))
        return min(opts)
    return tuple(primes[i][1] for i in solve(tt)[2])


def _nand_implementation(tt,n):
    names=list('ABCD'[:n]); gates=[]; values={x:bf.var_tt(i,n) for i,x in enumerate(names)}
    depth={x:0 for x in names}; values.update({'0':0,'1':bf.mask(n)});depth.update({'0':0,'1':0})
    cache={};byname={}
    def gate(op,args):
        args=tuple(sorted(args));key=op,args
        if key not in cache:
            name=f'n{len(gates)}';cache[key]=name
            val=bf.mask(n)
            for a in args: val&=values[a]
            values[name]=val^bf.mask(n);depth[name]=1+max(depth[a] for a in args)
            g=dict(name=name,op=op,args=list(args),transistors=2 if op=='INV' else 2*len(args))
            gates.append(g);byname[name]=g
        return cache[key]
    def inv(a):
        if a=='0':return '1'
        if a=='1':return '0'
        if a in byname and byname[a]['op']=='INV':return byname[a]['args'][0]
        return gate('INV',[a])
    def nand(args):
        if '0' in args:return '1'
        args=list(dict.fromkeys(a for a in args if a!='1'))
        if not args:return '0'
        if len(args)==1:return inv(args[0])
        while len(args)>3:
            chunk=args[:3];args=[inv(gate('NAND',chunk))]+args[3:]
        return gate('NAND',args)
    products=[]; exprs=[]
    for p in sop_cover(tt,n):
        args=[names[k] if v==1 else inv(names[k]) for k,v in enumerate(p) if v>=0]
        products.append(nand(args))
        exprs.append('('+'&'.join(names[k] if v else '!'+names[k]
                                for k,v in enumerate(p) if v>=0)+')' if args else '1')
    output=nand(products) if products else '0'
    assert values[output]==tt
    # Inversion cancellation can leave construction nodes unused. Cost only
    # gates reachable from the final output, not temporary construction work.
    reachable=set()
    def visit(a):
        if a not in byname or a in reachable:return
        reachable.add(a)
        for b in byname[a]['args']:visit(b)
    visit(output);gates=[g for g in gates if g['name'] in reachable]
    return dict(expression='|'.join(exprs) or '0',transistors=sum(g['transistors'] for g in gates),
                stages=depth[output],inverters=sum(g['op']=='INV' for g in gates),
                max_series=max((len(g['args']) for g in gates),default=0),
                method='minimum-literal SOP, NAND2/3 network',gates=gates,output=output)


def _nor_implementation(tt,n):
    dual=tt
    for k in range(n):dual=bf.flip_input(dual,n,k)
    dual=bf.negate(dual,n)
    out=_nand_implementation(dual,n)
    swap=lambda a:'1' if a=='0' else '0' if a=='1' else a
    gates=[g|{'op':'NOR' if g['op']=='NAND' else g['op'],
              'args':[swap(a) for a in g['args']]} for g in out['gates']]
    expr=out['expression'].translate(str.maketrans({'&':'|','|':'&','0':'1','1':'0'}))
    assert bf.eval_expr(expr,list('ABCD'[:n]))==tt
    return out|{'expression':expr,'gates':gates,'output':swap(out['output']),
                'method':'minimum-literal POS, NOR2/3 network'}


@lru_cache(None)
def implementation(tt,n,max_series=3):
    if n>4 or tt<0 or tt>bf.mask(n):raise ValueError('cost supports at most four inputs')
    if max_series not in (3,4):raise ValueError('supported stack limits are three for candidates or four for HD calibration')
    options=[_nand_implementation(tt,n),_nor_implementation(tt,n)]
    forms=stage_forms(n,max_series=max_series) if n else {}
    for flip in range(1<<n):
        t=tt
        for k in range(n):
            if flip>>k&1:t=bf.flip_input(t,n,k)
        for output_inv in (0,1):
            target=t^(bf.mask(n) if output_inv else 0)
            form=forms.get(target^bf.mask(n))
            if not form:continue
            key,positive=form;literals,_,ns,ps,_=key
            import re
            expr=re.sub(r'\b[A-D]\b',lambda m:'(!'+m[0]+')' if flip>>('ABCD'.index(m[0]))&1 else m[0],positive)
            expr='!('+expr+')'
            if output_inv:expr='!('+expr+')'
            pre=flip.bit_count()
            options.append(dict(expression=expr,transistors=2*(literals+pre+output_inv),
                                stages=1+bool(pre)+output_inv,
                                inverters=pre+output_inv+(literals==1),
                                max_series=max(ns,ps),method='factored static CMOS',
                                stage_formula=positive,n_series=ns,p_series=ps,
                                input_inversions=flip,output_inversion=output_inv))
    out=min(options,key=lambda x:(x['transistors'],x['stages'],x['inverters'],x['expression']))
    assert bf.eval_expr(out['expression'],list('ABCD'[:n]))==tt
    return out|{'verified_truth_table':bf.to_hex(tt,n)}


def features(row):return [1.,float(row['transistors']),max(0.,float(row['stages'])-1),float(row['inverters'])]


def _fit(rows):
    import numpy as np
    X=np.array([features(r) for r in rows]);y=np.array([r['area_um2']/SITE_AREA for r in rows])
    best=None
    # Small nonnegative least squares by enumerating active coefficient subsets.
    for size in range(1,5):
        for active in combinations(range(4),size):
            w=np.linalg.lstsq(X[:,active],y,rcond=None)[0]
            if min(w)<-1e-9:continue
            coef=np.zeros(4);coef[list(active)]=np.maximum(w,0)
            err=float(sum((X@coef-y)**2))
            if best is None or err<best[0]:best=err,coef.tolist()
    if best is None:raise ValueError('could not fit area model')
    return best[1]


def predict_area(model,cost):
    sites=max(1,math.ceil(sum(a*b for a,b in zip(model['coefficients_sites'],features(cost)))-1e-10))
    return round(sites*SITE_AREA,7)


def fit_model(rows):
    if len(rows)<5:raise ValueError('need at least five HD calibration cells')
    model={'coefficients_sites':_fit(rows),'feature_order':['intercept','transistors','extra_stages','inverters'],
           'site_area_um2':SITE_AREA,'height_um':2.72,'site_width_um':0.46,
           'method':'nonnegative least squares; predicted widths rounded up to whole sites',
           'cost_basis':'explicit realizations; not transistor counts extracted from HD layouts'}
    records=[]
    for i,r in enumerate(rows):
        pred=predict_area(model,r)
        held=predict_area({'coefficients_sites':_fit(rows[:i]+rows[i+1:])},r)
        records.append(r|{'predicted_um2':pred,'error_pct':100*(pred-r['area_um2'])/r['area_um2'],
                          'loo_predicted_um2':held,'loo_error_pct':100*(held-r['area_um2'])/r['area_um2']})
    import numpy as np
    errs=[abs(r['loo_error_pct']) for r in records]
    model.update(training_cells=len(rows),loo_mean_absolute_percent_error=float(np.mean(errs)),
                 loo_median_absolute_percent_error=float(np.median(errs)),
                 loo_max_absolute_percent_error=float(max(errs)),
                 single_stage_cells=sum(r['stages']==1 for r in rows),
                 multi_stage_cells=sum(r['stages']>1 for r in rows))
    return model,records
