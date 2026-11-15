# Perlmutter operations

The project uses `/global/homes/y/yunao/projects/legacy-tno` for staged code and job logs. The private workspace `/pscratch/sd/y/yunao/legacy-tno` holds exposure catalogs, originals referenced by path, the isolated Python 3.11 environment, external orbit inputs, and field runs. The retained result copies live in the local repository. Scratch is subject to NERSC purge.

From the local repository, confirm the current SSH credential and stage a committed snapshot:

```bash
ssh -o BatchMode=yes yunao@perlmutter.nersc.gov true
scripts/stage-code.sh yunao@perlmutter.nersc.gov "$(git rev-parse HEAD)"
```

Refresh the existing NERSC SSH credential with `sshproxy -u yunao` if the batch-mode probe reports an expired credential. The username and account were checked on the live cluster. CPU jobs used the `desi` account and debug QOS during the pilot because the original shared job remained queued. Submit subsequent runs using the site resource policy.

After logging into NERSC, resume a field with its existing inputs:

```bash
cd /global/homes/y/yunao/projects/legacy-tno
project="$PWD"
tno_work=/pscratch/sd/y/yunao/legacy-tno
sbatch --account=desi --constraint=cpu --qos=debug \
  --output="$project/logs/pilot-validation-%j.log" \
  slurm/pilot.sbatch "$project" "$tno_work" --field validation \
  --commit e56fee4 --resume
```

Use the full validated source revision when copying a different version. The configuration, selected field, Python source files and metadata inputs contribute to the run signature. A changed signature produces a new run directory. Avoid submitting two simultaneous reruns for the same signature. Each CCD cache uses an atomic rename. Inspect `sacct`, the log and the manifest before considering a pilot processed. Extraction or classification failures are counted as excluded CCDs.

The preliminary inventories and their audited caches live in `$tno_work/smoke`. The input directory contains the published DES FITS catalog, JPL kernel and frozen field selection. Explicit synchronization lists and size-checks regular result files from one run directory. The results path printed at job start supplies the exact directory to use.

## Reproduce the bounded non-DES run

From the local repository, `scripts/stage-revision.sh yunao@perlmutter.nersc.gov d92781a` stages the exact source revision into its own directory. The revision directory is already present on NERSC. After logging into Perlmutter, submit the same compact field and inspect its state and logs:

```bash
base=/global/homes/y/yunao/projects/legacy-tno
tno_work=/pscratch/sd/y/yunao/legacy-tno
rev=d92781a1e259b3c58430ea629b5d3a3b9a606672
project="$base/revisions/$rev"
job=$(sbatch --parsable --account=desi --constraint=cpu --qos=debug \
  --output="$base/logs/compact-exploration-%j.log" \
  "$project/slurm/compact-exploration.sbatch" "$project" "$tno_work" "$rev")
sacct -j "$job" -P -o JobID,State,ExitCode,Elapsed,MaxRSS
```

The compact job also reapplies the audited DES identity check to the two existing validation runs if their blind outputs are present. This identity stage reads finalized memberships and retains the original identity tables under `identity-v1/`.

For the four-night OF201 stress test, the successful SEP catalog retry used `slurm/sep-retry.sbatch` with a larger SEP active-pixel buffer while keeping the source thresholds. The parallel replay used the archived `0cd453a` revision and passed the existing catalog manifest, the same four-night field, and `of201` as its postprocessing mode. The JPL state is read after the anonymous fit. The precise job IDs, run paths and code revisions appear in the result manifest.

## Recover the inventory after the first attempt

The initial profile wrote `$tno_work/smoke/inventory.npy`, its CP sample catalogs, and the survey-CCD header audit before opening the compressed annotated metadata. Job 61346054 completed the annotated audit using streamed decompression to a temporary FITS file, then removed the temporary file. The Slurm recovery command used the earlier profile log to recover the 14 CP exposure audits:

```bash
cd /global/homes/y/yunao/projects/legacy-tno
tno_work=/pscratch/sd/y/yunao/legacy-tno
sbatch --account=desi --constraint=cpu --qos=debug \
  --output="$PWD/logs/inventory-%j.log" slurm/finish-inventory.sbatch \
  "$PWD" "$tno_work" "$PWD/logs/smoke-61345772.log"
```
