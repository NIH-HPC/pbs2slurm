pbs2slurm notes
================================================================================

- PBS directives in batch script use a more relaxed
  grammar than command line switches. For example
      '#PBS -N foo'
      '#PBS -Nfoo'
      '#PBS-Nfoo'
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
  #PBS -V and #PBS -v, but those are rare (and that's kind of iffy
  to begin with).
