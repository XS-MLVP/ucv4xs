"""Fail-closed local RTL certificate, never DUT coverage or binary equivalence.

This deliberately supports only the attributed short-protection array shape.
Every clocked array assignment, mux leaf and decoder is accounted for. The
SMT miter compares its extracted one-edge transition with independent four-
state semantic tables. Parent ownership and compiled equivalence stay open.
"""
from dataclasses import dataclass
from hashlib import sha256
from functools import cache
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
CELL=r'usefulEntries_(\d+)_(\d+)_value'


def require(value,message):
    if not value:raise ValueError(message)


def compact(value):return re.sub(r'\s+','',value)


def address(bank,row):
    require(0<=bank<4 and 0<=row<128,'unsupported protection address')
    return 4*row+bank


def block(text,opening):
    require(text[opening:opening+5]=='begin','expected explicit begin')
    depth=0
    for token in re.finditer(r'\b(begin|end)\b',text[opening:]):
        depth+=1 if token[0]=='begin' else -1
        if depth==0:return opening+token.start(),opening+token.end()
    raise ValueError('unclosed procedural block')


def split_and(value):
    depth=0;parts=[];start=0
    for i,ch in enumerate(value):
        if ch=='(':depth+=1
        elif ch==')':depth-=1
        elif ch=='&' and depth==0:parts.append(value[start:i]);start=i+1
    parts.append(value[start:])
    return parts


@dataclass(frozen=True)
class Projection:
    read_map: tuple
    decoders: tuple
    allocation: tuple
    reset: tuple
    aging_step: tuple
    spans: tuple
    source_sha256: str


def extract(source):
    text=re.sub(r'//[^\n]*','',source)
    c=compact(text)
    for name,width in (('clock',None),('reset',None),('io_train_t0_trainIndex_bits','8:0'),
            ('io_train_t1_update_valid',None),('io_train_t1_update_bits_updateTaken',None),
            ('io_train_t1_update_bits_updateCfiPosition','4:0'),
            ('io_train_t1_update_bits_usefulValid',None),('io_train_t1_update_bits_needUseful',None),
            ('io_train_t1_alloc_valid',None),('io_train_t1_alloc_bits_taken',None),
            ('io_train_t1_alloc_bits_cfiPosition','4:0'),('io_writeSuccess',None),('io_usefulReset',None)):
        port=r'\binput\s+'+(r'\['+width+r'\]\s*' if width else '')+name+r'\s*[,)]'
        require(len(re.findall(port,text))==1,'unsupported control port width: '+name)
    cells={(int(b),int(r)) for b,r in re.findall(r'reg\s+\[1:0\]\s+'+CELL+r'\s*;',text)}
    require(cells=={(b,r) for b in range(4) for r in range(128)},'complete two-bit protection array required')
    for declaration in ('reg[8:0]t1_trainIndex;',
            'wire[127:0][1:0]_GEN_137=',
            'wire[1:0]_GEN_138=',
            'wire_newUseful_T_8=',
            'wire[1:0]_newUseful_T_13=',
            'wire_GEN_139='):
        require(declaration in c,'unsupported shared protection dependency widths')
    @cache
    def definition(name):
        values=re.findall(r'(?<![A-Za-z0-9_])'+re.escape(name)+r'\s*=(?!=)\s*([^;]+);',text)
        require(len(values)==1,'ambiguous or missing dependency '+name)
        return compact(values[0])
    require(definition('_GEN_139')=='io_train_t1_alloc_valid|io_train_t1_update_valid&io_train_t1_update_bits_usefulValid',
        'unsupported protection qualification')
    require(definition('_newUseful_T_8')=='(&_GEN_138)&io_train_t1_update_bits_needUseful|_GEN_138==2\'h0&~io_train_t1_update_bits_needUseful',
        'unsupported saturation guard')
    require(definition('_newUseful_T_13')=="io_train_t1_update_bits_needUseful?2'(_GEN_138+2'h1):2'(_GEN_138-2'h1)",
        'unsupported protection arithmetic')
    # Both levels of the current-state packed-array read must be complete.
    muxes={}
    for match in re.finditer(r'wire\s+\[3:0\]\[1:0\]\s+(\w+)\s*=\s*(\{[^;]+\});',text):
        leaves=re.findall(CELL,match[2])
        require(len(leaves)==4,'incomplete protection bank mux')
        require(compact(match[2])=='{'+','.join('{'+f'usefulEntries_{b}_{r}_value'+'}' for b,r in leaves)+'}',
            'unsupported bank mux expression')
        muxes[match[1]]=tuple(address(int(b),int(r)) for b,r in reversed(leaves))
    require(len(muxes)==128,'complete current-state row muxes required')
    outer=definition('_GEN_137')
    names=re.findall(r'\{(\w+)\[t1_trainIndex\[1:0\]\]\}',outer)
    require(len(names)==128 and outer=='{'+','.join('{'+name+'[t1_trainIndex[1:0]]}' for name in names)+'}',
        'unsupported current-state outer mux')
    require(set(names)<=muxes.keys() and definition('_GEN_138')=='_GEN_137[t1_trainIndex[8:2]]',
        'protection update must read the complete current array')
    read_map=tuple(value for name in reversed(names) for value in muxes[name])
    reset_match=re.search(r'\bif\s*\(reset\)\s*(begin)',text)
    require(reset_match is not None,'explicit synchronous reset required')
    processes=list(re.finditer(r'always\s*@\(posedge\s+clock(?:\s+or\s+posedge\s+reset)?\)\s*(begin)',text))
    require(processes,'one explicit active clocked process required')
    reset_process=None
    for process in processes:
        process_end,_=block(text,process.start(1))
        if process.end(1)<=reset_match.start()<process_end:
            reset_process=process;break
    require(reset_process is not None,'reset must be inside an active clocked process')
    clocked=[reset_process]
    clocked_end,_=block(text,clocked[0].start(1))
    require(not re.search(CELL+r'\s*=(?!=)',text[clocked[0].end(1):clocked_end]),
        'blocking protection assignments are outside the certified transition')
    initial_spans=[(m.start(1),block(text,m.start(1))[0]) for m in re.finditer(r'\binitial\s+(begin)',text)]
    for m in re.finditer(CELL+r'\s*=(?!=)',text):
        require(any(a<m.start()<b for a,b in initial_spans),
            'an additional active protection writer is outside the certified transition')
    prefix=text[clocked[0].end(1):reset_match.start()]
    require(not re.search(r'\b(if|else|case|for|while|begin|end)\b',prefix),'reset must be the direct clocked root')
    reset_end,reset_after=block(text,reset_match.start(1))
    after=re.match(r'\s*else\s*(begin)',text[reset_after:])
    require(after is not None,'reset must dominate the nonreset branch')
    nonreset_start=reset_after+after.start(1);nonreset_end,_=block(text,nonreset_start)
    ages=list(re.finditer(r'\bif\s*\(io_usefulReset\)\s*(begin)',text))
    require(len(ages)==1 and nonreset_start<ages[0].start()<nonreset_end,'one nonreset aging priority required')
    age=ages[0];age_end,age_after=block(text,age.start(1))
    before_age=text[nonreset_start+5:age.start()]
    require(sum(1 if t=='begin' else -1 for t in re.findall(r'\b(begin|end)\b',before_age))==0
        and before_age.rstrip().endswith('end'),'aging must be a direct nonreset statement')
    after=re.match(r'\s*else\s*(begin)',text[age_after:])
    require(after is not None,'aging must dominate all ordinary protection writes')
    normal_start=age_after+after.start(1);normal_end,_=block(text,normal_start)
    resets={};aging={};assignments=[]
    for m in re.finditer(CELL+r'\s*<=\s*([^;]+);',text):
        b,r=int(m[1]),int(m[2]);key=address(b,r);rhs=compact(m[3]);assignments.append(m)
        if reset_match.start(1)<m.start()<reset_end:
            prefix=text[reset_match.end(1):m.start()]
            require(sum(1 if t=='begin' else -1 for t in re.findall(r'\b(begin|end)\b',prefix))==0,
                'conditional reset assignments are unsupported')
            require(not prefix[prefix.rfind(';')+1:].strip(),'guarded reset assignment is unsupported')
            k=re.fullmatch(r"2'h([0-3])",rhs);require(k is not None,'unsupported reset value');resets[key]=int(k[1])
        elif age.start(1)<m.start()<age_end:
            sig=f'usefulEntries_{b}_{r}_value'
            k=re.fullmatch(re.escape(sig)+r"==2'h0\?2'h0:2'\("+re.escape(sig)+r"-2'h([0-3])\)",rhs)
            require(k is not None,'unsupported aging expression');aging[key]=int(k[1])
        else:require(normal_start<m.start()<normal_end,'unaccounted protection assignment')
    require(len(resets)==len(aging)==512 and len(assignments)==2560,'every clocked protection assignment must be accounted for')
    age_assignments=[m for m in assignments if age.start(1)<m.start()<age_end]
    previous=age.end(1)
    for m in age_assignments:
        require(not text[previous:m.start()].strip(),'conditional aging assignment is unsupported');previous=m.end()
    require(not text[previous:age_end].strip(),'unaccounted aging control')
    pattern=(r'(?m)^ {8}if\s*\((.*?)\)\s*begin\s*'
        r'if\s*\(io_train_t1_alloc_valid\)\s*('+CELL+r")\s*<=\s*2'h([0-3]);\s*"
        r'else\s+if\s*\(_newUseful_T_8\)\s*\2\s*<=\s*_GEN_138;\s*'
        r'else\s*\2\s*<=\s*_newUseful_T_13;\s*end')
    matches=list(re.finditer(pattern,text[normal_start:normal_end],re.S))
    require(len(matches)==512,'all ordinary protection writes must have one complete supported branch')
    first=normal_start+matches[0].start();prelude=text[normal_start+5:first]
    require(not re.search(r'\b(if|else|case|for|while)\b',prelude),'unaccounted ordinary-write control')
    previous=first;decoders={};alloc={};spans={}
    def decoder(term):
        term=compact(term)
        if re.fullmatch(r'\w+',term):
            require('wire'+term+'=' in c,'unsupported decoder width')
            term=definition(term)
        m=re.fullmatch(r"t1_trainIndex\[(1:0|8:2)\]==([27])'h([0-9A-Fa-f]+)",term)
        if m:
            low=m[1]=='1:0';require(int(m[2])==(2 if low else 7),'wrong decoder width')
            return ('bank' if low else 'row',int(m[3],16))
        if term in ('(&t1_trainIndex[1:0])','(&(t1_trainIndex[1:0]))'):return 'bank',3
        if term in ('(&t1_trainIndex[8:2])','(&(t1_trainIndex[8:2]))'):return 'row',127
        raise ValueError('unsupported decoder '+term)
    for m in matches:
        start,end=normal_start+m.start(),normal_start+m.end()
        require(not text[previous:start].strip(),'unaccounted control between protection writes');previous=end
        terms=split_and(compact(m[1]));require(len(terms)==3 and terms[0]=='_GEN_139','one qualification and two decoder terms required')
        d=dict(decoder(t) for t in terms[1:]);require(set(d)=={'bank','row'},'both address components required')
        key=address(int(m[3]),int(m[4]));require(key not in decoders,'duplicate protection destination')
        decoders[key]=(d['bank'],d['row']);alloc[key]=int(m[5])
        spans[key]=(text.count('\n',0,start)+1,text.count('\n',0,end)+1)
    require(not text[previous:normal_end].strip(),'unaccounted trailing protection writes')
    require(set(decoders)==set(resets)==set(aging)==set(range(512)),'protection destination coverage incomplete')
    return Projection(read_map,tuple(decoders[k] for k in range(512)),tuple(alloc[k] for k in range(512)),
        tuple(resets[k] for k in range(512)),tuple(aging[k] for k in range(512)),tuple(spans[k] for k in range(512)),
        sha256(source.encode()).hexdigest())


def bv(value,width):return f'(_ bv{value} {width})'


def evaluate(p,*,cell,index,state,reset=False,aging=False,allocate=False,update=False,valid=False,reward=False):
    """Finite diagnostic evaluation of the extracted rule, not a DUT oracle."""
    current=state[cell]
    if reset:return p.reset[cell]
    if aging:return 0 if current==0 else (current-p.aging_step[cell])%4
    if not (allocate or update and valid) or p.decoders[cell]!=(index%4,index//4):return current
    if allocate:return p.allocation[cell]
    old=state[p.read_map[index]]
    if reward and old==3 or not reward and old==0:return old
    return (old+(1 if reward else -1))%4


def choose(variable,values,width,default):
    result=default
    for i,value in reversed(list(enumerate(values))):
        expected=default if variable=='IDX' and value==i else bv(value,width)
        if expected==default:continue
        result=f'(ite (= {variable} {bv(i,9)}) {expected} {result})'
    return result


def miter(p):
    # Canonical reduction is exact: inspect every extracted constant decoder
    # and mux leaf, retaining every exceptional destination as an explicit ITE.
    routed=choose('IDX',p.read_map,9,'IDX')
    decoded='(= IDX CELL)'
    for i,(bank,row) in reversed(list(enumerate(p.decoders))):
        if (bank,row)==(i%4,i//4):continue
        actual=f'(and (= ((_ extract 1 0) IDX) {bv(bank,2)}) (= ((_ extract 8 2) IDX) {bv(row,7)}))'
        decoded=f'(ite (= CELL {bv(i,9)}) {actual} {decoded})'
    allocations=choose('CELL',p.allocation,2,bv(1,2))
    resets=choose('CELL',p.reset,2,bv(0,2))
    aging=choose('CELL',p.aging_step,2,bv(1,2))
    # Explicit semantic tables are independent from RTL wraparound arithmetic.
    table=lambda values:'(ite (= CUR #b00) '+bv(values[0],2)+' (ite (= CUR #b01) '+bv(values[1],2)+' (ite (= CUR #b10) '+bv(values[2],2)+' '+bv(values[3],2)+')))'
    return '\n'.join([
        '(set-logic QF_AUFBV)','(set-option :produce-models true)',
        '(declare-fun IDX () (_ BitVec 9))','(declare-fun CELL () (_ BitVec 9))',
        '(declare-fun U () (Array (_ BitVec 9) (_ BitVec 2)))',
        *[f'(declare-fun {n} () Bool)' for n in ('RESET','AGE','ALLOC','UPDATE','VALID','REWARD')],
        '(define-fun CUR () (_ BitVec 2) (select U CELL))',
        f'(define-fun READ () (_ BitVec 2) (select U {routed}))',
        '(define-fun QUAL () Bool (or ALLOC (and UPDATE VALID)))',
        '(define-fun SAT () Bool (or (and (= READ #b11) REWARD) (and (= READ #b00) (not REWARD))))',
        '(define-fun LEARN () (_ BitVec 2) (ite SAT READ (ite REWARD (bvadd READ #b01) (bvsub READ #b01))))',
        f'(define-fun ACTUAL () (_ BitVec 2) (ite RESET {resets} (ite AGE (ite (= CUR #b00) #b00 (bvsub CUR {aging})) (ite (and QUAL {decoded}) (ite ALLOC {allocations} LEARN) CUR))))',
        '(define-fun EXPECTED () (_ BitVec 2) (ite RESET #b00 (ite AGE '+table((0,0,1,2))+
        ' (ite (and QUAL (= IDX CELL)) (ite ALLOC #b01 (ite REWARD '+table((1,2,3,3))+' '+table((0,0,1,2))+')) CUR))))',
        '(assert (not (= ACTUAL EXPECTED)))','(check-sat)',''])


def solve(program,solver,*,model=False):
    value=subprocess.run([str(solver),'-in','-smt2'],input=program+('(get-model)\n' if model else ''),
        text=True,capture_output=True,timeout=30)
    require(value.returncode==0 and not value.stderr,'solver error: '+value.stderr+value.stdout)
    answer=value.stdout.splitlines()[0] if value.stdout else ''
    require(answer in ('sat','unsat'),'solver did not prove or refute the local rule')
    return answer,value.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--solver',type=Path,default=shutil.which('z3'))
    args=parser.parse_args();require(args.solver is not None,'install/provide a solver explicitly; no automatic SDK changes')
    require(args.output.resolve().is_relative_to(ROOT/'results'),'analysis output must be inside repository results')
    args.output.mkdir(parents=True,exist_ok=False)
    from tools.refresh_coverage import source_epoch,write
    from tools.coverage_delta import lcov_rows
    from dataclasses import replace
    frozen=source_epoch();write(args.output/'source-epoch.json',frozen)
    native=json.loads((ROOT/'results/current/native-index.json').read_text())
    execution=ROOT/'results/joint-stream-native-20261019-v1/source-epoch.json'
    execution_epoch=json.loads(execution.read_text())
    receipts={};base=None
    for domain in ('utage','bpu'):
        path=ROOT/f'rtl/{domain}/BypassShadowBuffer.sv';p=extract(path.read_text())
        require(execution_epoch[str(path)]==p.source_sha256,'SF source differs from the latest executed snapshot')
        if base is None:base=p
        require(p==base,'two attributed short-protection bodies differ')
        lcov=ROOT/native['dut'][domain]['lcov_file']
        require(sha256(lcov.read_bytes()).hexdigest()==native['dut'][domain]['sha256'],'changed native baseline')
        missing=[line for (file,line),n in lcov_rows(lcov).items() if file==str(path) and not n]
        mapped={str(line):next((cell for cell,(a,b) in enumerate(p.spans) if a<=line<=b),None) for line in missing}
        require(all(v is not None for v in mapped.values()),'a missing protection row lies outside the proved local branches')
        receipts[domain]=dict(source=str(path.relative_to(ROOT)),sha256=p.source_sha256,missing_rows=len(missing),
            lines_to_local_cell=mapped,all_clocked_assignments_accounted_for=2560,all_cells=512,
            latest_executed_source_snapshot_matches=True,binary_equivalence_claimed=False)
    query=miter(base);proved_answer,_=solve(query,args.solver);require(proved_answer=='unsat','local protection rule mismatch')
    (args.output/'local-rule.smt2').write_text(query)
    mutants={
        'wrong-allocation':replace(base,allocation=(2,*base.allocation[1:])),
        'wrong-reset':replace(base,reset=(1,*base.reset[1:])),
        'wrong-aging-step':replace(base,aging_step=(2,*base.aging_step[1:])),
        'wrong-read-owner':replace(base,read_map=(1,*base.read_map[1:])),
        'wrong-write-owner':replace(base,decoders=((1,0),*base.decoders[1:]))}
    negative={}
    for name,projection in mutants.items():
        program=miter(projection);answer,output=solve(program,args.solver,model=True)
        require(answer=='sat','local proof is insensitive to '+name)
        (args.output/(name+'.smt2')).write_text(program);(args.output/(name+'.model.txt')).write_text(output)
        negative[name]=answer
    version=subprocess.run([str(args.solver),'-version'],text=True,capture_output=True,check=True).stdout.strip()
    result=dict(format='strict-source-local-protection-rule-certificate-not-native-credit',status='PASS',
        theorem='one arbitrary observed cell has reset/aging/qualified-owned-saturating transition',
        solver=version,solver_sha256=sha256(args.solver.resolve().read_bytes()).hexdigest(),
        miter=proved_answer,negative_mutants=negative,sources=receipts,
        missing_rows_explained=sum(v['missing_rows'] for v in receipts.values()),
        arbitrary_training_address_bits=9,arbitrary_observed_address_bits=9,arbitrary_array_state=True,
        complete_parent_ownership_proved=False,compiled_binary_equivalence_proved=False,
        hardware_credit_added=0,native_hits_added=0,denominator_rows_removed=0,feature_IDs_added=0,
        source_files=len(frozen),no_RTL_DUT_SDK_changes=True,goal_complete=False)
    require(source_epoch()==frozen,'source changed during analysis')
    write(args.output/'qualification-analysis.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='sources'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
