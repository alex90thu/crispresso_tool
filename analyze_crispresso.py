#!/usr/bin/env python3
"""
CRISPResso Analysis Wrapper (Async Backend).
Features:
1. Stream-based fast PE stitching (gzip pipe).
2. Integration with Portal Generator (updates index.html).
3. Status logging for async monitoring.
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

# 尝试导入门户生成器，以便在任务结束时刷新页面
try:
    import portal_gen
except ImportError:
    portal_gen = None

# ==========================================
# 全局配置
# ==========================================
# 默认数据根目录 (当传入相对路径时使用)
DEFAULT_OUTPUT_BASE = Path("/data/lulab_commonspace/guozehua/crispresso_out")

# DNA 反向互补的高效翻译表 (Global for performance)
TRANS_TABLE = str.maketrans("ATCGNabcde", "TAGCNtagcn")

def get_reverse_complement(seq: str) -> str:
    """
    Returns the reverse complement of a DNA sequence using str.translate (Fast C implementation).
    """
    return seq.translate(TRANS_TABLE)[::-1]

def stitch_paired_end_reads_stream(
    r1_path: Path, r2_path: Path, output_path: Path, n_padding: int
) -> None:
    """
    Stitches R1 and R2 reads using system gzip piping (High Performance).
    Format: R1 + (N * n_padding) + RC(R2)
    
    Why: Avoids decompressing huge FASTQ files to disk/memory.
    """
    print(f"[Process] Stitching reads...")
    print(f"         Source R1: {r1_path}")
    print(f"         Source R2: {r2_path}")
    print(f"         Target:    {output_path}")
    
    pad_seq = "N" * n_padding
    pad_qual = "!" * n_padding 
    
    # 检测解压命令：优先用 pigz (并行gzip)，没有则用 gunzip
    if shutil.which("pigz"):
        decompress_cmd = ["pigz", "-dc"]
        compress_cmd = ["pigz", "-c"]
    else:
        decompress_cmd = ["gunzip", "-c"]
        compress_cmd = ["gzip", "-c"]

    cmd_r1 = decompress_cmd + [str(r1_path)]
    cmd_r2 = decompress_cmd + [str(r2_path)]
    
    # 建立管道
    try:
        with subprocess.Popen(cmd_r1, stdout=subprocess.PIPE, text=True, bufsize=1024*1024) as p1, \
             subprocess.Popen(cmd_r2, stdout=subprocess.PIPE, text=True, bufsize=1024*1024) as p2, \
             open(output_path, "wb") as f_out_raw:
             
            # 压缩输出流
            with subprocess.Popen(compress_cmd, stdin=subprocess.PIPE, stdout=f_out_raw, text=True, bufsize=1024*1024) as p_out:
                
                f1_stream, f2_stream, fout_stream = p1.stdout, p2.stdout, p_out.stdin
                
                count = 0
                while True:
                    # 1. ID Line
                    r1_id = f1_stream.readline()
                    r2_id = f2_stream.readline()
                    if not r1_id: break 
                    
                    # 2. Sequence Line
                    r1_seq = f1_stream.readline().strip()
                    r2_seq = f2_stream.readline().strip()
                    
                    # 3. Plus Line
                    f1_stream.readline() 
                    f2_stream.readline()
                    
                    # 4. Quality Line
                    r1_qual = f1_stream.readline().strip()
                    r2_qual = f2_stream.readline().strip()
                    
                    # --- Logic Stitching ---
                    r2_seq_rc = r2_seq.translate(TRANS_TABLE)[::-1]
                    r2_qual_rev = r2_qual[::-1]
                    
                    merged_seq = r1_seq + pad_seq + r2_seq_rc
                    merged_qual = r1_qual + pad_qual + r2_qual_rev
                    
                    # Write
                    fout_stream.write(f"{r1_id.strip()}\n{merged_seq}\n+\n{merged_qual}\n")
                    
                    count += 1
                    if count % 100000 == 0:
                        print(f"         Processed {count} reads...", end='\r')

        print(f"\n[Success] Stitched {count} reads total.")

    except Exception as e:
        print(f"\n[Error] Stitching failed: {e}")
        # 如果生成失败，删除不完整文件，避免后续误用
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
) -> List[str]:
    """Assemble the CRISPResso command."""
    
    # 确保输出目录存在
    if not output_dir.exists():
        print(f"[Setup] Creating directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)

    final_r1 = fastq_r1
    
    # === 拼接逻辑 (Stitching) ===
    if n_padding > 0 and fastq_r2:
        # 在当前任务目录下创建一个子文件夹存放拼接文件，保持整洁
        stitch_dir = output_dir / "stitched_reads"
        stitch_dir.mkdir(parents=True, exist_ok=True)
        
        # 加上时间戳防止混淆（虽然在Job文件夹模式下不太可能重名，但保险起见）
        timestamp = time.strftime("%H%M%S")
        safe_name = sample_name if sample_name else "sample"
        # 移除非法字符
        safe_name = "".join([c for c in safe_name if c.isalnum() or c in ('-', '_')])
        
        stitched_filename = f"{safe_name}_stitched_pad{n_padding}_{timestamp}.fastq.gz"
        stitched_file = stitch_dir / stitched_filename
        
        # 执行拼接
        stitch_paired_end_reads_stream(fastq_r1, fastq_r2, stitched_file, n_padding)
        
        # 修正后续参数：使用拼接后的文件作为R1
        final_r1 = stitched_file
        fastq_r2 = None 
        
    cmd = [
        executable,
        "-r1",
        str(final_r1),
        "-a",
        amplicon_seq,
        "-g",
        guide_seq,
        "-o",
        str(output_dir),
    ]

    # 只有在非拼接模式下才传入 R2
    if fastq_r2:
        cmd += ["-r2", str(fastq_r2)]
        
    if sample_name:
        cmd += ["-n", sample_name]
    if min_read_length:
        cmd += ["--min_read_length", str(min_read_length)]
    if min_base_quality:
        cmd += ["--min_average_read_quality", str(min_base_quality)]
    if n_processes:
        cmd += ["-p", str(n_processes)]

    return cmd


def run_crispresso(args: argparse.Namespace) -> None:
    """Validate inputs and invoke CRISPResso."""
    executable = args.executable
    if shutil.which(executable) is None:
        print(f"[Warning] Executable '{executable}' not found in PATH.")
        print("          Ensure you provided the absolute path or activated the correct conda environment.")

    fastq_r1 = Path(args.fastq_r1).resolve()
    fastq_r2 = Path(args.fastq_r2).resolve() if args.fastq_r2 else None
    
    # 处理输出路径
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
        )

        print(f"[Exec] Running command:\n{' '.join(cmd)}")
        
        # 执行 CRISPResso
        subprocess.run(cmd, check=True)
        
        # === 成功标记 (供 Portal 识别) ===
        print("\n[Status] Job Completed Successfully")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[Error] Job Failed with return code {e.returncode}")
        # 不直接 exit，让 finally 块有机会运行
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n[Error] Unexpected error: {e}")
        sys.exit(1)
    finally:
        # === 更新 Portal ===
        # 无论成功还是失败，都尝试更新 index.html
        if portal_gen:
            try:
                print("[Info] Triggering Portal update...")
                portal_gen.generate_portal()
            except Exception as e:
                print(f"[Warning] Failed to update portal: {e}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run CRISPResso with optional 'Stitch with N' mode.",
    )
    parser.add_argument("--fastq_r1", required=True, help="Path to R1 FASTQ.gz")
    parser.add_argument("--fastq_r2", help="Path to R2 FASTQ.gz")
    parser.add_argument("--amplicon", required=True, help="Amplicon sequence (5'->3')")
    parser.add_argument("--guide", required=True, help="gRNA sequence")
    parser.add_argument(
        "--output", 
        default=str(DEFAULT_OUTPUT_BASE),
        help=f"Output directory (Default: {DEFAULT_OUTPUT_BASE})"
    )
    parser.add_argument("--name", help="Sample name")
    parser.add_argument("--executable", default="CRISPResso", help="CRISPResso CLI name or path")
    parser.add_argument("--min_read_length", type=int)
    parser.add_argument("--min_base_quality", type=int)
    parser.add_argument("--n_processes", type=int)
    parser.add_argument(
        "--n_padding", 
        type=int, 
        default=0,
        help="If > 0, stitches R1 and R2 with this many Ns in between."
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_crispresso(parse_args())