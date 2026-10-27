"""Lossless complete JSON traces; compression does not omit frames or fields."""
import gzip
import json
from pathlib import Path


def write_trace(path,value):
    encoded=(json.dumps(value)+'\n').encode('utf-8')
    with Path(path).open('xb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',compresslevel=1,mtime=0) as stream:
            stream.write(encoded)


def read_trace(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        return json.load(stream)
