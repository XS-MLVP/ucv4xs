"""Bounded run summaries by default; per-cycle JSON is explicit debug only."""
from hashlib import sha256
import json


class Journal:
    def __init__(self,path,*,nodeid,trace=False,max_bytes=16*1024*1024):
        self.path,self.nodeid=path,nodeid
        self.name=str(path)
        self.stream=path.open("x") if trace else None
        self.limit=max_bytes
        self.digest=sha256()
        self.bytes=self.records=self.saved=0
        self.truncated=False
        self.last=""
        self.closed=False

    def write(self,value):
        if self.closed:raise ValueError("write to closed journal")
        data=value.encode()
        self.digest.update(data)
        self.bytes+=len(data)
        self.records+=value.count("\n")
        if value.strip():self.last=value[-262144:]
        if self.stream is not None and not self.truncated:
            if self.saved+len(data)<=self.limit:
                self.stream.write(value);self.saved+=len(data)
            else:self.truncated=True
        return len(value)

    def flush(self):
        if self.stream is not None:self.stream.flush()

    def close(self):
        if self.closed:return
        if self.stream is not None:self.stream.close()
        terminal={}
        try:
            row=json.loads(self.last)
            if isinstance(row,dict):
                for key in("pre_tick","post_tick","tick","checked","error","event","scope"):
                    if key in row:terminal[key]=str(row[key])[:4096] if key=="error" else row[key]
        except (ValueError,TypeError):pass
        summary=dict(format="lsq-journal-summary-v1",nodeid=self.nodeid,records=self.records,serialized_bytes=self.bytes,
                     streamed_SHA256=self.digest.hexdigest(),trace_enabled=self.stream is not None,
                     saved_trace_bytes=self.saved,trace_truncated=self.truncated,terminal=terminal,
                     scope="All runtime checks still execute. Digest is of checked stream, NOT a retained per-cycle trace or independent offline semantic audit.")
        with self.path.with_suffix(".summary.json").open("x") as f:f.write(json.dumps(summary,indent=2)+"\n")
        self.closed=True
        self.last=""

    def __enter__(self):return self
    def __exit__(self,*exception):self.close()
