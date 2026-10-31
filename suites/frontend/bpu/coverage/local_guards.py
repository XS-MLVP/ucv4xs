"""Bounded source-guard checks and exact native producer/span association.

Diagnostic only: never excludes a native row or produces functional PASS.
This deliberately supports generated begin/end blocks and single-line guard
definitions, not arbitrary SystemVerilog or whole-design formal reasoning.
"""
from suites.frontend.bpu import ROOT as _SUITE_ROOT
from hashlib import sha256
from pathlib import Path
import re

from suites.frontend.bpu.coverage.rtl import POINT, _covered_lines, _metadata


ROOT = _SUITE_ROOT


class Source:
    def __init__(self,path):
        self.path = path
        self.text = (ROOT/path).read_text()
        self.lines = [line.split('//',1)[0].strip() for line in self.text.splitlines()]
        self.sha256 = sha256(self.text.encode()).hexdigest()

    def expect(self,line,text):
        assert self.lines[line-1]==text,(self.path,line,text,self.lines[line-1])

    def definition(self,name,expression):
        # firtool can emit a wire initializer on one or several lines.
        # Match the unique assignment and its complete RHS, not a substring.
        text = '\n'.join(self.lines)
        pattern = r'(?<![\w])'+re.escape(name)+r'\s*=(?!=)\s*([^;]*);'
        matches = list(re.finditer(pattern,text))
        assert len(matches)==1,(self.path,name,'ambiguous definition',len(matches))
        match, = matches
        assert re.sub(r'\s+','',match[1])==re.sub(r'\s+','',expression), (self.path,name,expression,match[1])
        return text[:match.start()].count('\n')+1

    def unique(self,text):
        matches = [n for n,line in enumerate(self.lines,1) if line==text]
        assert len(matches)==1,(self.path,text,matches)
        return matches[0]

    def closing(self,line):
        assert self.lines[line-1].endswith('begin'),(self.path,line,'not a supported begin block')
        depth = 0
        for number in range(line,len(self.lines)+1):
            code = re.sub(r'"(?:\\.|[^"\\])*"','""',self.lines[number-1])
            for token in re.findall(r'\b(?:begin|end)\b',code):
                depth += 1 if token=='begin' else -1
                if depth==0:
                    return number
        raise AssertionError((self.path,line,'unclosed begin block'))

    def encloses(self,outer,first,last):
        assert outer < first <= last < self.closing(outer),(self.path,outer,first,last,'guard does not enclose body')


def claim(file,first,last,guard,arm,kind):
    return dict(file=file,first=first,last=last,guard=guard,arm=arm,kind=kind)


def native_points(path):
    points = []
    with Path(path).open() as stream:
        for record in stream:
            match = POINT.match(record.rstrip('\n'))
            if match is None:
                continue
            fields = _metadata(match[1])
            if fields.get('page','').partition('/')[0] in ('v_line','v_branch'):
                points.append((fields,int(match[2])))
    return points


def match_native(claims,report,dut,points):
    """Every producer of every claimed DA key must match a proven arm.

    A zero count alone is not proof. Nor is the text of a DA line its guard:
    the anchor plus S spans and all overlapping producers are checked here.
    """
    rows = report['dut'][dut]['uncovered_rtl_source_lines']
    raw = {(row['file'],row['line']) for row in rows}
    totals = report['dut'][dut]['source_lines']
    assert len(raw)==len(rows) and totals['total']-totals['hit']==len(raw),('invalid native source denominator',dut)
    assertions = {}
    for item in claims:
        for line in range(item['first'],item['last']+1):
            key = item['file'],line
            assert key not in assertions,('overlapping source claims',key)
            assertions[key] = item
    assert assertions.keys() <= raw,('claim is not a current zero-count DA key',sorted(assertions.keys()-raw))
    by_file = {}
    for file,line in assertions:
        by_file.setdefault(str((ROOT/file).resolve()),{})[line] = file,line
    resolved = {}
    seen,producers = set(),[]
    for fields,count in points:
        filename = fields['f']
        if filename not in resolved:
            resolved[filename] = str(Path(filename).resolve())
        source = resolved[filename]
        keys = by_file.get(source)
        if keys is None:
            continue
        relevant = {keys[line] for line in _covered_lines(fields) & keys.keys()}
        if not relevant:
            continue
        for key in relevant:
            item = assertions[key]
            assert (int(fields['l']),fields.get('o'))==(item['guard'],item['arm']),(
                'native DA producer is not the proven arm',key,fields,item)
        assert count==0,('contradictory guard producer has nonzero count; investigate compiler/evidence',fields,count)
        seen.update(relevant)
        producers.append(dict(file=keys[next(iter(_covered_lines(fields) & keys.keys()))][0],page=fields['page'],line=int(fields['l']),
            arm=fields.get('o'),span=fields.get('S',''),context=fields.get('h',''),count=count))
    assert seen==assertions.keys(),('missing native producers; never assume zero',sorted(assertions.keys()-seen))
    return dict(native_source_lines=report['dut'][dut]['source_lines'],raw_missing=len(raw),
        locally_classified=len(assertions),unclassified=sorted(raw-assertions.keys()),
        native_denominator_unchanged=True,functional_pass_credit=False,
        whole_design_formal_claim=False,native_points=producers,claims=claims)
