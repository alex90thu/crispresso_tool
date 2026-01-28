#!/usr/bin/env python3
"""
CRISPResso Analysis Wrapper (Async Backend).
Features:
1. Accepts modern CRISPResso2 args (--plot_window_size, --needleman_wunsch_gap_open).
2. Clean argument parsing.
3. Subprocess portal update.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import os
import time
from pathlib import Path
from typing import List

# ==========================================
# 全局配置
# ==========================================
DEFAULT_OUTPUT_BASE = Path("/data/lulab_commonspace/guozehua/crispresso_out")

# DNA 反向互补的高效翻译表
TRANS_TABLE = str.maketrans("ATCGNabcde", "TAGCNtagcn")

def get_reverse_complement(seq: str) -> str:
    """Returns the reverse complement of a DNA sequence using str.translate."""
    return seq.translate(TRANS_TABLE)[::-1]

def stitch_paired_end_reads_stream(
    r1_path: Path, r2_path: Path, output_path: Path, n_padding: int
) -> None:
    """
    Stitches R1 and R2 reads using system gzip piping.
    Format: R1 + (N * n_padding) + RC(R2)
    """
    print(f"[Process] Stitching reads...")
    print(f"         Source R1: {r1_path}")
    print(f"         Source R2: {r2_path}")
    print(f"         Target:    {output_path}")
    
    pad_seq = "N" * n_padding
    pad_qual = "!" * n_padding 
    
    if shutil.which("pigz"):
        decompress_cmd = ["pigz", "-dc"]
        compress_cmd = ["pigz", "-c"]
    else:
        decompress_cmd = ["gunzip", "-c"]
        compress_cmd = ["gzip", "-c"]

    cmd_r1 = decompress_cmd + [str(r1_path)]
    cmd_r2 = decompress_cmd + [str(r2_path)]
    
    try:
        with subprocess.Popen(cmd_r1, stdout=subprocess.PIPE, text=True, bufsize=1024*1024) as p1, \
             subprocess.Popen(cmd_r2, stdout=subprocess.PIPE, text=True, bufsize=1024*1024) as p2, \
             open(output_path, "wb") as f_out_raw:
             
            with subprocess.Popen(compress_cmd, stdin=subprocess.PIPE, stdout=f_out_raw, text=True, bufsize=1024*1024) as p_out:
                f1_stream, f2_stream, fout_stream = p1.stdout, p2.stdout, p_out.stdin
                count = 0
                while True:
                    r1_id = f1_stream.readline()
                    r2_id = f2_stream.readline()
                    if not r1_id: break 
                    
                    r1_seq = f1_stream.readline().strip()
                    r2_seq = f2_stream.readline().strip()
                    
                    f1_stream.readline() 
                    f2_stream.readline()
                    
                    r1_qual = f1_stream.readline().strip()
                    r2_qual = f2_stream.readline().strip()
                    
                    r2_seq_rc = r2_seq.translate(TRANS_TABLE)[::-1]
                    r2_qual_rev = r2_qual[::-1]
                    
                    merged_seq = r1_seq + pad_seq + r2_seq_rc
                    merged_qual = r1_qual + pad_qual + r2_qual_rev
                    
                    fout_stream.write(f"{r1_id.strip()}\n{merged_seq}\n+\n{merged_qual}\n")
                    count += 1
                    if count % 100000 == 0:
                        print(f"         Processed {count} reads...", end='\r')

        print(f"\n[Success] Stitched {count} reads total.")

    except Exception as e:
        print(f"\n[Error] Stitching failed: {e}")
        if output_path.exists():
            output_path.unlink()
        raise e

def build_command(
    executable: str,
    fastq_r1: Path,
    amplicon_seq: str,
    guide_seq: str,
    output_dir: Path,
    *,
    fastq_r2: Path | None = None,
    sample_name: str | None = None,
    min_read_length: int | None = None,
    min_base_quality: int | None = None,
    n_processes: int | None = None,
    n_padding: int = 0,
    # New arguments
    plot_window_size: int | None = None,
    gap_open: int | None = None,
) -> List[str]:
    """Assemble the CRISPResso command."""
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    final_r1 = fastq_r1
    
    # === Stitching Logic ===
    if n_padding > 0 and fastq_r2:
        stitch_dir = output_dir / "stitched_reads"
        stitch_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = time.strftime("%H%M%S")
        safe_name = sample_name if sample_name else "sample"
        safe_name = "".join([c for c in safe_name if c.isalnum() or c in ('-', '_')])
        
        stitched_filename = f"{safe_name}_stitched_pad{n_padding}_{timestamp}.fastq.gz"
        stitched_file = stitch_dir / stitched_filename
        
        stitch_paired_end_reads_stream(fastq_r1, fastq_r2, stitched_file, n_padding)
        final_r1 = stitched_file
        fastq_r2 = None 
        
    cmd = [
        executable,
        "-r1", str(final_r1),
        "-a", amplicon_seq,
        "-g", guide_seq,
        "-o", str(output_dir),
    ]

    if fastq_r2:
        cmd += ["-r2", str(fastq_r2)]
    if sample_name:
        cmd += ["-n", sample_name]
    
    # Warning for min_read_length
    if min_read_length and min_read_length > 0:
        print(f"[Warning] Argument --min_read_length {min_read_length} ignored (Not supported by CRISPResso CLI directly).")
        
    # Map min_base_quality to -q
    if min_base_quality and min_base_quality > 0:
        cmd += ["-q", str(min_base_quality)]
        
    if n_processes:
        cmd += ["-p", str(n_processes)]
        
    # === New Parameters Added ===
    if plot_window_size is not None:
        cmd += ["--plot_window_size", str(plot_window_size)]
        
    if gap_open is not None:
        cmd += ["--needleman_wunsch_gap_open", str(gap_open)]

    return cmd


def run_crispresso(args: argparse.Namespace) -> None:
    executable = args.executable
    if shutil.which(executable) is None:
        print(f"[Warning] Executable '{executable}' not found in PATH.")

    fastq_r1 = Path(args.fastq_r1).resolve()
    fastq_r2 = Path(args.fastq_r2).resolve() if args.fastq_r2 else None
    
    user_out = Path(args.output)
    if user_out.is_absolute():
        output_dir = user_out
    else:
        output_dir = DEFAULT_OUTPUT_BASE / user_out
    
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        cmd = build_command(
            executable=executable,
            fastq_r1=fastq_r1,
            fastq_r2=fastq_r2,
            amplicon_seq=args.amplicon,
            guide_seq=args.guide,
            output_dir=output_dir,
            sample_name=args.name,
            min_read_length=args.min_read_length,
            min_base_quality=args.min_base_quality,
            n_processes=args.n_processes,
            n_padding=args.n_padding,
            # Pass new args
            plot_window_size=args.plot_window_size,
            gap_open=args.needleman_wunsch_gap_open,
        )

        print(f"[Exec] Running command:\n{' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        print("\n[Status] Job Completed Successfully")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[Error] Job Failed with return code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n[Error] Unexpected error: {e}")
        sys.exit(1)
    finally:
        # Update portal via subprocess
        try:
            current_dir = Path(__file__).parent.resolve()
            portal_script = current_dir / "portal_gen.py"
            if portal_script.exists():
                subprocess.run([sys.executable, str(portal_script)], check=False)
        except Exception as e:
            print(f"[Warning] Failed to update portal: {e}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fastq_r1", required=True)
    parser.add_argument("--fastq_r2")
    parser.add_argument("--amplicon", required=True)
    parser.add_argument("--guide", required=True)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_BASE))
    parser.add_argument("--name")
    parser.add_argument("--executable", default="CRISPResso")
    
    # Standard optional args
    parser.add_argument("--min_read_length", type=int)
    parser.add_argument("--min_base_quality", type=int)
    parser.add_argument("--n_processes", type=int)
    parser.add_argument("--n_padding", type=int, default=0)
    
    # === Added support for the required args ===
    parser.add_argument("--plot_window_size", type=int)
    parser.add_argument("--needleman_wunsch_gap_open", type=int)
    
    return parser.parse_args()


if __name__ == "__main__":
    run_crispresso(parse_args())