#!/usr/bin/env python3
"""Extract first complete ROI from actual gem5 Ruby stats (MESI/MOESI)."""
import argparse
import configparser
import csv
import re
from pathlib import Path

PREFIX = 'system.ruby.'
EVENT = PREFIX + 'L1Cache_Controller.'


def read_roi(path):
    blocks, current = [], None
    for line in path.read_text().splitlines():
        if 'Begin Simulation Statistics' in line:
            if current is not None:
                raise ValueError(f'{path}: nested stats block')
            current = {}
        elif 'End Simulation Statistics' in line:
            if current is None:
                raise ValueError(f'{path}: unexpected end')
            blocks.append(current)
            current = None
        elif current is not None:
            parts = line.split()
            if len(parts) >= 2:
                current[parts[0]] = parts[1]
    if current is not None or len(blocks) != 2:
        raise ValueError(f'{path}: expected two complete stats blocks, got {len(blocks)}')
    return blocks[0]


def extract(path, validation_iterations):
    s = read_roi(path)
    d = path.parent.name
    cfg = configparser.ConfigParser(interpolation=None, strict=False)
    if not cfg.read(path.with_name('config.ini')):
        raise ValueError(f'{d}: missing config.ini')
    cores = len([k for k in cfg.sections() if re.fullmatch(r'system\.ruby\.l1_cntrl\d+', k)])
    protocol_type = cfg['system.ruby.l1_cntrl0']['type']
    protocol = 'MESI' if protocol_type.startswith('MESI_Two_Level_') else 'MOESI' if protocol_type.startswith('MOESI_CMP_directory_') else None
    if not protocol:
        raise ValueError(f'{d}: unknown protocol {protocol_type}')
    match = re.fullmatch(r'(mesi|moesi)_n(\d+)_(nopad|pad|gemm_N(\d+))', d)
    if match:
        if match[1].upper() != protocol or int(match[2]) != cores:
            raise ValueError(f'{d}: configuration mismatch')
        workload = 'gemm' if match[4] else 'false_sharing'
        mode = '' if match[4] else match[3]
        n = int(match[4]) if match[4] else ''
        iterations = '' if match[4] else int(path.with_name('iterations.txt').read_text().strip())
        log = path.with_name('run.log').read_text()
        expected = (f'GEMM OpenMP N={n} hilos={cores}: OK' if workload == 'gemm' else
                    f'False sharing hilos={cores} modo={mode} iteraciones={iterations}: OK')
        if expected not in log or 'm5_exit instruction encountered' not in log:
            raise ValueError(f'{d}: missing verified completion in run.log')
    else:
        match = re.fullmatch(r'validacion_(mesi|moesi)_(nopad|pad)_v2', d)
        if not match or match[1].upper() != protocol:
            raise ValueError(f'{d}: unknown run name')
        workload, mode, n, iterations = 'false_sharing', match[2], '', validation_iterations
    def integer(key):
        return int(s[key])
    # Sparse SLICC event stats may be absent. Keep blank rather than invent zero.
    def event(key):
        return int(s[key]) if key in s else None
    counts = {k: int(v) for k, v in s.items() if k.startswith(PREFIX+'network.msg_count.')}
    bytecounts = {k: int(v) for k, v in s.items() if k.startswith(PREFIX+'network.msg_byte.')}
    if not counts or not bytecounts:
        raise ValueError(f'{d}: missing network stats')
    freq = integer('simFreq')
    ticks = integer('simTicks')
    clock = int(cfg[cfg['system.ruby']['clk_domain']]['clock'])
    samples = integer(PREFIX+'m_missLatencyHistSeqr::samples') if PREFIX+'m_missLatencyHistSeqr::samples' in s else None
    lat = float(s[PREFIX+'m_missLatencyHistSeqr::mean']) if PREFIX+'m_missLatencyHistSeqr::mean' in s and samples else None
    row = dict(config=d, protocol=protocol, workload=workload, cores=cores, mode=mode, N=n,
               iterations_per_thread=iterations, simTicks=ticks, time_us=ticks/freq*1e6,
               simInsts=integer('simInsts'), ruby_clock_ticks=clock,
               l1_inv_events=event(EVENT+'Inv::total'),
               l1_fwd_getx_events=event(EVENT+'Fwd_GETX::total'),
               l1_fwd_gets_events=event(EVENT+'Fwd_GETS::total'),
               network_messages=sum(counts.values()), network_bytes=sum(bytecounts.values()),
               network_invalidate_control=event(PREFIX+'network.msg_count.Invalidate_Control'),
               sequencer_miss_samples=samples, miss_latency_ruby_cycles=lat,
               miss_latency_ns=lat*clock/freq*1e9 if lat is not None else None)
    # Record state/event transitions separately without double counting ::total and per-state totals.
    detail = {k.removeprefix(EVENT).removesuffix('::total'): int(v) for k,v in s.items()
              if re.fullmatch(re.escape(EVENT)+r'[^.]+\.(?:Inv|Fwd_GETX|Fwd_GETS)::total',k)}
    return row, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', type=Path)
    ap.add_argument('-o', '--output', type=Path)
    ap.add_argument('--validation-iterations', type=int, default=10000)
    ap.add_argument('--expect', type=int, help='require this number of runs')
    args = ap.parse_args()
    out = args.output or args.root/'e5.csv'
    paths = sorted(args.root.glob('*/stats.txt'))
    if not paths or (args.expect is not None and len(paths)!=args.expect):
        ap.error(f'found {len(paths)} runs; expected {args.expect or "at least one"}')
    rows, details = [], []
    for p in paths:
        row, detail = extract(p,args.validation_iterations)
        rows.append(row)
        for name,count in sorted(detail.items()):
            state,event = name.split('.')
            details.append(dict(config=row['config'],protocol=row['protocol'],state=state,event=event,count=count))
    out.parent.mkdir(parents=True,exist_ok=True)
    for name, data, fields in [(out,rows,list(rows[0])),(out.with_name(out.stem+'_states.csv'),details,['config','protocol','state','event','count'])]:
        with name.open('w', newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
    print(f'[E5] {len(rows)} corridas -> {out}')

if __name__ == '__main__':
    main()
