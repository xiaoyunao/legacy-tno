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
