Translating batch scripts with `#PBS` directives into Slurm scripts with `#SBATCH` directives
=============================================================================================
`pbs2slurm.py` translates PBS type batch scripts to Slurm. It translates directives
and a limited subset of environment variables.

`pbs2slurm_tests.py` serves two purposes: It takes a number of test cases and
checks for correct translation and outputs the results as an html table in
`testcases.html`.

### Usage

```
usage: pbs2slurm [-h] [--shell SHELL] [--version] [pbs_script]

Translates PBS batch script to Slurm.

The PBS script is split into
- a shebang line
- a header containing #PBS directives, comments, and empty lines
- the body of the script

pbs2slurm carries out 3 transformation steps
- if no shebang line was present in the PBS script, a new one is added. By 
  default this is #! /bin/bash, but this can be changed (see below)
- #PBS directives in the header are translated, where possible, to #SBATCH 
  directives.
- common PBS environment variables in the body are translated to their SLURM 
  equivalents

Please be sure to manually go over translated scripts to esure their 
correctness.

If no input file is specified, pbs2slurm reads from stdin. The translated script 
is written to stdout.

Examples:
    pbs2slurm < pbs_script > slurm_script
    pbs2slurm pbs_script > slurm_script
    pbs2slurm -s /bin/zsh pbs_script > slurm_script

See also https://hpc.cit.nih.gov/docs/pbs2slurm.html.

positional arguments:
  pbs_script

optional arguments:
  -h, --help            show this help message and exit
  --shell SHELL, -s SHELL
                        Shell to insert if shebang line (#! ...) is missing.
                        Defaults to '/bin/bash'
  --version, -v
```

### pbs2slurm notes

- PBS directives in batch script use a more relaxed
  grammar than command line switches. For example
    -  `#PBS -N foo`
    -  `#PBS -Nfoo`
    -  `#PBS-Nfoo`
  all work! All of these will be correctly translated.

- to get an idea of what is in PBS job scripts i collected
  40119 pbs directives from existing scripts. Frequencies
  of the different directives:
    ```
      24034 #PBS -N
      14504 #PBS -m
        458 #PBS -k
        238 #PBS -l
        213 #PBS -o
        212 #PBS -j
        159 #PBS -q
        108 #PBS -r
        104 #PBS -e
         42 #PBS -S
         26 #PBS -M
         16 #PBS -V
          1 #PBS 
          1 #PBS -J
          1 #PBS -v
          1 #PBS -wd
    ```
  a surprising number of -k directives:
    ```
      1 #PBS -k o
    457 #PBS -k oe
    ```
  where -k oe results in out and err files in the user's home

- this script is not computationally efficient with all the
  repeated string substitutions. However, efficiency doesn't 
  really matter for this script.

- this script does not gracefully deal with multiple occurences
  of the same options. It generally translates them all. This 
  could lead to some confusion for scripts that use, for example,
  `#PBS -V` and `#PBS -v`, but those are rare (and that's kind of iffy
  to begin with).
