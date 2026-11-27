#!/usr/bin/env python3
"""Plot E5 CSV; missing counters are gaps, never zero-filled."""
import argparse
import csv
from pathlib import Path
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv', type=Path, nargs='?', default=Path('results/e5/e5.csv'))
    ap.add_argument('--out', type=Path, default=Path('report/figures'))
    args = ap.parse_args()
    with args.csv.open(newline='') as f:
        rows = list(csv.DictReader(f))
    args.out.mkdir(parents=True, exist_ok=True)
    fs = [r for r in rows if r['workload']=='false_sharing']
    gemm = [r for r in rows if r['workload']=='gemm']
    def value(r,key):
        return float(r[key]) if r[key] else math.nan
    def draw(data, key, title, ylabel, filename, variant, log=False):
        if not data:
            return
        cores=sorted({int(r['cores']) for r in data})
        fig,ax=plt.subplots(figsize=(8,4.8),layout='constrained')
        for protocol in ('MESI','MOESI'):
            for label, field, style in variant:
                subset={int(r['cores']):value(r,key) for r in data if r['protocol']==protocol and r[field]==label}
                if subset:
                    ax.plot(cores,[subset.get(n,math.nan) for n in cores],marker='o',linestyle=style,label=f'{protocol} / {label}')
        ax.set(title=title,xlabel='Núcleos',ylabel=ylabel,xticks=cores)
        if log:
            ax.set_yscale('symlog',linthresh=1)
        ax.grid(True,alpha=.3); ax.legend()
        fig.savefig(args.out/filename,dpi=180);plt.close(fig)
    modes=[('nopad','mode','-'),('pad','mode','--')]
    draw(fs,'time_us','E5 – Tiempo de ejecución: falso compartido','Tiempo ROI (µs)','e5_execution_time.png',modes)
    draw(fs,'l1_inv_events','E5 – Eventos explícitos Inv en L1','Eventos Inv (no incluye Fwd_GETX)','e5_invalidations.png',modes)
    draw(fs,'l1_fwd_getx_events','E5 – Solicitudes de exclusividad reenviadas','Eventos Fwd_GETX','e5_fwd_getx.png',modes,True)
    draw(fs,'network_messages','E5 – Tráfico de la red Ruby','Mensajes contabilizados en red','e5_coherence_messages.png',modes,True)
    draw(fs,'miss_latency_ruby_cycles','E5 – Latencia de fallo del secuenciador','Ciclos Ruby por fallo','e5_miss_latency.png',modes)
    draw(fs,'sequencer_miss_samples','E5 – Fallos registrados por el secuenciador','Muestras de fallo','e5_miss_samples.png',modes,True)
    sizes=[(n,'N',style) for n,style in zip(sorted({r['N'] for r in gemm},key=int),['-','--',':'])]
    draw(gemm,'time_us','E5 – GEMM paralelo con Ruby','Tiempo ROI (µs)','e5_gemm_comparison.png',sizes)
    # Paired speedup based on identical per-thread work.
    paired=[]
    for r in fs:
        if r['mode']!='nopad': continue
        for q in fs:
            if q['mode']=='pad' and all(q[k]==r[k] for k in ('protocol','cores','iterations_per_thread')):
                paired.append({'protocol':r['protocol'],'cores':r['cores'],'mode':'padding','speedup':value(r,'time_us')/value(q,'time_us')})
    draw(paired,'speedup','E5 – Aceleración al aplicar padding','Speedup (×)','e5_padding_speedup.png',[('padding','mode','-')])
    print(f'[E5] Gráficas guardadas en {args.out}')

if __name__=='__main__': main()
