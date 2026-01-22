[![Chinese](https://img.shields.io/badge/Language-中文-blue)](./README_zh.md)

# CRISPResso Async UI

A small toolkit to submit CRISPResso2 analyses asynchronously via a Streamlit UI and browse results from a lightweight static portal.

## What this repo contains
- `run.sh`: starts the Streamlit UI and a static HTTP server for result browsing in the background.
- `streamlit_app.py`: the front-end to submit jobs; it launches `analyze_crispresso.py` via `nohup` and triggers portal refreshes.
- `analyze_crispresso.py`: CLI wrapper that stitches PE reads (optional N-padding), calls CRISPResso2, and updates the portal on completion.
- `portal_gen.py`: scans the output root and rebuilds a simple `index.html` dashboard.
- `environment.yml` / `requirements.txt`: dependencies (conda/pip). Default conda env name: `crispresso-env`.

## Setup
1) Install conda (or mamba) and ensure `conda` is on PATH in non-interactive shells.
2) Create the environment:
   ```bash
   conda env create -f environment.yml
   # or, if the env already exists: conda env update -f environment.yml --prune
   ```
3) (Optional) Activate manually when running tools directly:
   ```bash
   conda activate crispresso-env
   ```

## Run the services
The helper script will activate `crispresso-env`, start a static file server for the output root, and launch Streamlit with `nohup` so both continue in the background.
```bash
bash run.sh --port 8504 --address 0.0.0.0
```
- Streamlit: http://<server>:8504 (logs: `streamlit_app.log`)
- Portal:    http://<server>:8505 (logs: `portal_server.log`)

### Paths to adjust
Results root is hard-coded in three places. Change it to your storage path if needed:
- `DATA_DIR` in `run.sh`
- `DEFAULT_OUTPUT_BASE` in `analyze_crispresso.py`
- `ROOT_DIR` in `portal_gen.py`

Keep these values consistent; the portal and UI assume the same location.

## Using the Streamlit UI
1) Open the Streamlit URL.
2) Fill in required fields: R1 FASTQ, amplicon sequence, guide sequence, sample name. Optional: R2 FASTQ, N-padding for stitching non-overlapping reads, min read length/quality, CPU cores, CRISPResso binary path.
3) Submit. Each job creates a `Job_<timestamp>_<sample>` directory under the output root, writes `CRISPResso_RUNNING_LOG.txt`, and runs CRISPResso2 in the background via `nohup`.
4) Check progress in the portal (auto-refreshes every 60s) or open the job log.

## Direct CLI usage
You can run the backend without Streamlit:
```bash
python analyze_crispresso.py \
  --fastq_r1 /path/to/R1.fastq.gz \
  --amplicon ACTG... \
  --guide GGG... \
  --output /path/to/output_dir \
  --name Sample01 \
  --executable /path/to/CRISPResso \
  --n_padding 10 \
  --fastq_r2 /path/to/R2.fastq.gz \
  --min_read_length 0 \
  --min_base_quality 0 \
  --n_processes 4
```
Notes:
- `--n_padding > 0` triggers R1/R2 stitching (R2 reverse-complemented, padded with Ns), then runs single-end mode on the stitched file.
- If `--output` is relative, it is resolved under `DEFAULT_OUTPUT_BASE`.

## Portal generator
`portal_gen.py` builds `index.html` under the output root, listing jobs, status heuristics (running/done/error), log links, and report links. It is invoked automatically after each submission and after each CRISPResso run; you can also run it manually:
```bash
python portal_gen.py
```

## Troubleshooting
- Ensure `conda` is available to non-interactive shells; otherwise `run.sh` will exit early.
- Confirm the output root exists and is writable; `run.sh` will create it if missing.
- CRISPResso binary path: set in the UI or pass `--executable` when calling the CLI.
- If ports are occupied, adjust `--port` / `PORTAL_PORT` in `run.sh`.
