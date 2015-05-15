import pbs2slurm as p2s
import sys
import atexit
import difflib

sys.stderr = sys.stdout

html = open("testcases.html", "w")

def html_out(fh, ok, pbs, slurm, desc):
    pbss = pbs.replace(">", "&gt;").replace("<", "&lt;")
    slurms = slurm.replace(">", "&gt;").replace("<", "&lt;")
    fh.write("""
    <tr><td colspan=2>{desc}{ok}</td></tr>
    <tr><td>
            <pre class="term">{pbss}</pre>
        </td>
        <td>
            <pre class="term">{slurms}</pre>
        </td>
    </tr>
""".format(**locals()))

def html_header(fh):
    fh.write("""
<div id="test_table">
<table>
    <tr><th><b>PBS script</b></th>
        <th><b>SLURM script</b></th>
    </tr>
""")

html_header(html)


def check(input, exp, obs, desc):
    if exp != obs:
        pf = """<span class="fail">FAIL</span>"""
        html_out(html, pf, input, exp, desc)
        d = difflib.Differ()
        sys.stdout.writelines(d.compare(
            exp.splitlines(1),
            obs.splitlines(1)))
        assert False
    else:
        pf = """<span class="ok">OK</span>"""
        html_out(html, pf, input, exp, desc)
        

def test_plain_bash():
    desc = "plain bash is unchanged"
    input = """#!/bin/bash
set -e
set -o pipefail

module load fastqc
cd /data/$USER/test_data
fastqc -d /scratch -f fastq --noextract some.fastq.gz
"""
    check(input, input, p2s.convert_batch_script(input), desc)

################################################################################
# PBS environment variables
def test_pbs_o_workdir():
    desc = "change PBS_O_WORKDIR to SLURM_SUBMIT_DIR"
    input = """#!/bin/bash
set -e
set -o pipefail

cd $PBS_O_WORKDIR
echo ${PBS_O_WORKDIR}
module load fastqc
cd /data/$USER/test_data
fastqc -d /scratch -f fastq --noextract some.fastq.gz
"""
    expected = """#!/bin/bash
set -e
set -o pipefail

cd $SLURM_SUBMIT_DIR
echo ${SLURM_SUBMIT_DIR}
module load fastqc
cd /data/$USER/test_data
fastqc -d /scratch -f fastq --noextract some.fastq.gz
"""
    check(input, expected, p2s.convert_batch_script(input), desc)


def test_pbs_jobid():
    desc = "change PBS_JOBID to SLURM_JOBID"
    input = """#!/bin/bash
set -e
set -o pipefail

module load fastxtoolkit
cd /data/$USER/test_data
echo "Job $PBS_JOBID starting" > logfile
zcat some.fq.gz \\
  | tr '.' 'N' \\
  | fastx_artifacts_filter  \\
  | fastx_clipper -a AGATCGGAAGAGC  \\
  | fastq_quality_trimmer -t 20 -l 10 -z  \\
  > some.clean.fq.gz
echo "Job $PBS_JOBID done" >> logfile
"""
    expected = """#!/bin/bash
set -e
set -o pipefail

module load fastxtoolkit
cd /data/$USER/test_data
echo "Job $SLURM_JOBID starting" > logfile
zcat some.fq.gz \\
  | tr '.' 'N' \\
  | fastx_artifacts_filter  \\
  | fastx_clipper -a AGATCGGAAGAGC  \\
  | fastq_quality_trimmer -t 20 -l 10 -z  \\
  > some.clean.fq.gz
echo "Job $SLURM_JOBID done" >> logfile
"""
    check(input, expected, p2s.convert_batch_script(input), desc)


def test_pbs_arrayid():
    desc  = "change PBS_ARRAYID to SLURM_ARRAY_TASK_ID"
    input = """#! /bin/bash
set -e
set -o pipefail

module load fastqc
cd /data/$USER/test_data
module load bowtie/1.1.1 samtools/1.2
gunzip -c sample${PBS_ARRAYID}.fastq.gz \\
   | bowtie --sam --best --strata --all -m1 -n2 \\
       --threads=10 /path/to/genome/index -  \\
   | samtools view -Sb -F4 - \\
   > sample${PBS_ARRAYID}.bam
"""
    expected = """#! /bin/bash
set -e
set -o pipefail

module load fastqc
cd /data/$USER/test_data
module load bowtie/1.1.1 samtools/1.2
gunzip -c sample${SLURM_ARRAY_TASK_ID}.fastq.gz \\
   | bowtie --sam --best --strata --all -m1 -n2 \\
       --threads=10 /path/to/genome/index -  \\
   | samtools view -Sb -F4 - \\
   > sample${SLURM_ARRAY_TASK_ID}.bam
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

################################################################################
# misc
def test_missing_shebang():
    desc = "insert missing shebang line"
    input = """set -e
set -o pipefail

module load bowtie/1.1.1 samtools/1.2
cd /data/$USER/test_data
"""
    expected = """#! /bin/bash
set -e
set -o pipefail

module load bowtie/1.1.1 samtools/1.2
cd /data/$USER/test_data
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_header_identification():
    desc = "find pbs directives in headers with empty lines and comments"
    input = """#! /bin/bash
#some other comment
#PBS -N fastqc_job

#PBS -N other_name
set -e
set -o pipefail

module load fastqc
cd /data/$USER/test_data
"""
    expected = """#! /bin/bash
#some other comment
#SBATCH --job-name="fastqc_job"

#SBATCH --job-name="other_name"
set -e
set -o pipefail

module load fastqc
cd /data/$USER/test_data
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

################################################################################
# job name
def test_jobname():
    desc = "change #PBS -N to #SBATCH --job-name"
    input = """#! /bin/bash
#PBS -N fastqc_job
set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --job-name="fastqc_job"
set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_jobname_empty():
    desc = "drop #PBS -N when no job name is given"
    input = """#! /bin/bash
#PBS -N 
set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

################################################################################
# email address
def test_valid_email_address():
    desc = "Change #PBS -M directive to #SBATCH --mail-user [valid email]"
    input = """#! /bin/bash
#PBS -M student@helix.nih.gov
set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --mail-user="student@helix.nih.gov"
set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_empty_email_address():
    desc = "drop empty #PBS -M"
    input = """#! /bin/bash
#PBS -M 
set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)
def test_multiple_email_addresses():
    desc = "Change #PBS -M directive to #SBATCH --mail-user [multiple emails]"
    input = """#! /bin/bash
#PBS -M student@helix.nih.gov,teacher@helix.nih.gov
set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --mail-user="student@helix.nih.gov"
set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_multiple_email_addresses2():
    desc = "Change #PBS -M directive to #SBATCH --mail-user [multiple emails]"
    input = """#! /bin/bash
#PBS -M student,teacher@helix.nih.gov
set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --mail-user="teacher@helix.nih.gov"
set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

################################################################################
# email mode 
def test_email_modes_n():
    desc = "Change #PBS -m email modes: n; this is the slurm default"
    input = """#! /bin/bash
#PBS -m n

module load bowtie
"""
    expected = """#! /bin/bash


module load bowtie
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_email_modes_a():
    desc = "Change #PBS -m email modes: a"
    input = """#! /bin/bash
#PBS -m a

module load bowtie
"""
    expected = """#! /bin/bash
#SBATCH --mail-type=FAIL

module load bowtie
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_email_modes_b():
    desc = "Change #PBS -m email modes: b"
    input = """#! /bin/bash
#PBS -m b

module load bowtie
"""
    expected = """#! /bin/bash
#SBATCH --mail-type=BEGIN

module load bowtie
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_email_modes_e():
    desc = "Change #PBS -m email modes: e"
    input = """#! /bin/bash
#PBS -m e

module load bowtie
"""
    expected = """#! /bin/bash
#SBATCH --mail-type=END

module load bowtie
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_email_modes_be():
    desc = "Change #PBS -m email modes: be"
    input = """#! /bin/bash
#PBS -m be

module load bowtie
"""
    expected = """#! /bin/bash
#SBATCH --mail-type=BEGIN,END

module load bowtie
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_email_modes_abe():
    desc = "Change #PBS -m email modes: abe"
    input = """#! /bin/bash
#PBS -m abe

module load bowtie
"""
    expected = """#! /bin/bash
#SBATCH --mail-type=BEGIN,END,FAIL

module load bowtie
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_email_modes_aben():
    desc = "Change #PBS -m email modes: aben"
    input = """#! /bin/bash
#PBS -m aben

module load bowtie
"""
    expected = """#! /bin/bash


module load bowtie
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_email_modes_empty():
    desc = "Change #PBS -m email modes: <empty>"
    input = """#! /bin/bash
#PBS -m 

module load bowtie
"""
    expected = """#! /bin/bash


module load bowtie
"""
    check(input, expected, p2s.convert_batch_script(input), desc)
################################################################################
# stderr and stdout files
def test_keep_directive_ignored():
    desc = "Remove #PBS -k directives"
    input = """#! /bin/bash
#PBS -k oe

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash


set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)


def test_join_directive_ignored_eo():
    desc = "Remove #PBS -j directives [join is default in slurm]"
    input = """#! /bin/bash
#PBS -j eo

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash


set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_join_directive_ignored_oe():
    desc = "Remove #PBS -j directives [join is default in slurm]"
    input = """#! /bin/bash
#PBS -j oe

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash


set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_stdout_directive():
    desc = "Change #PBS -o directive to #SBATCH --output"
    input = """#! /bin/bash
#PBS -o /path/to/some/file

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --output=/path/to/some/file

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_empty_stdout_directive():
    desc = "Drop #PBS -o directive without argument"
    input = """#! /bin/bash
#PBS -o 

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash


set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)


def test_stderr_directive():
    desc = "Change #PBS -e directive to #SBATCH --error"
    input = """#! /bin/bash
#PBS -e /path/to/some/file

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --error=/path/to/some/file

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_empty_stderr_directive():
    desc = "Drop #PBS -e directive without argument"
    input = """#! /bin/bash
#PBS -e

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash


set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)
################################################################################
# restartable

def test_restartable_directive_y():
    desc = "Change #PBS -r directive to #SBATCH --[no]-requeue"
    input = """#! /bin/bash
#PBS -r y 

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --requeue

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_restartable_directive_n():
    desc = "Change #PBS -r directive to #SBATCH --[no]-requeue"
    input = """#! /bin/bash
#PBS -r n 

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --no-requeue

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_restartable_directive_bad():
    desc = "Remove malformed #PBS -r directive"
    input = """#! /bin/bash
#PBS -r fnord 

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash


set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

################################################################################
# shell

def test_drop_shell_directive():
    desc = "Drop #PBS -S directive"
    input = """#! /bin/bash
#PBS -S /bin/bash

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash


set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

################################################################################
# export environment variables

def test_export_whole_env():
    desc = "Change #PBS -V directive to #SBATCH --export=ALL; kept even \
            though this is the default for slurm. makes it explicit."
    input = """#! /bin/bash
#PBS -V

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --export=ALL

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_export_individual_variables_1():
    desc = "Change #PBS -v directive to #SBATCH --export="
    input = """#! /bin/bash
#PBS -v np=300

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --export=np=300

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_export_individual_variables_2():
    desc = "Change #PBS -v directive to #SBATCH --export=; removes spaces"
    input = """#! /bin/bash
#PBS -v np=300, fnord=1

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --export=np=300,fnord=1

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_export_individual_variables_2():
    desc = "Change #PBS -v directive to #SBATCH --export=; "
    input = """#! /bin/bash
#PBS -V
#PBS -v np=300, fnord=1
#PBS -v foo=2

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --export=ALL
#SBATCH --export=np=300,fnord=1
#SBATCH --export=foo=2

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

################################################################################
# job array

def test_fix_job_array():
    desc = "translate #PBS -J to #SBATCH --array" 
    input = """#! /bin/bash
#PBS -J 1-20

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash
#SBATCH --array=1-20

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_drop_empty_job_array():
    desc = "drops #PBS -J without argument" 
    input = """#! /bin/bash
#PBS -J  

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash


set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

################################################################################
# #PBS -l
# drop everything except walltime; most of this would have been overridden by
# the qsub wrapper script

def test_resources():
    desc = "test parsing of resource lists that occured in the wild" 
    input = """#! /bin/bash
#PBS -l jobfs=500MB
#PBS -l ncpus=1
#PBS -l nice=19
#PBS -l nodes=1
#PBS -l nodes=150:gige
#PBS -l nodes=1:htown:gige:ppn=8,walltime=60:00:00
#PBS -l nodes=1:ppn=1
#PBS -l nodes=1:ppn=2
#PBS -l nodes=1:ppn=4
#PBS -l software=amber
#PBS -l vmem=500MB
#PBS -l walltime=00:05:0
#PBS -l walltime=00:15:0
#PBS -l walltime=00:30:0
#PBS -l walltime=12:00:00,mem=1000mb
#PBS -l walltime=20:00:00
#PBS -l walltime=24:00:00
#PBS -l walltime=400:00:00,nodes=1:ppn=4,pmem=800mb

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash





#SBATCH --time=60:00:00





#SBATCH --time=00:05:00
#SBATCH --time=00:15:00
#SBATCH --time=00:30:00
#SBATCH --time=12:00:00
#SBATCH --time=20:00:00
#SBATCH --time=24:00:00
#SBATCH --time=400:00:00

set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

################################################################################
# PBS -q
# should not have worked with the qsub wrapper. the instances i found were not
# actually valid queues. drop -q lines

def test_drop_queue():
    desc = "Drop #PBS -q" 
    input = """#! /bin/bash
#PBS -q serial
#PBS -q batch
#PBS -q tracking
#PBS -q normal

set -e
set -o pipefail

module load fastqc
"""
    expected = """#! /bin/bash





set -e
set -o pipefail

module load fastqc
"""
    check(input, expected, p2s.convert_batch_script(input), desc)


################################################################################
# real world examples
def test_script1():
    desc = "real world example 1"
    input = """#!/bin/csh -v
#PBS -N germline
#PBS -m be
#PBS -k oe

cd $PBS_O_WORKDIR
germline -bits 50 -min_m 1 -err_hom 2  <<EOF
1
CEU.22.map
CEU.22.ped
generated
EOF
    """
    expected = """#!/bin/csh -v
#SBATCH --job-name="germline"
#SBATCH --mail-type=BEGIN,END


cd $SLURM_SUBMIT_DIR
germline -bits 50 -min_m 1 -err_hom 2  <<EOF
1
CEU.22.map
CEU.22.ped
generated
EOF
    """
    check(input, expected, p2s.convert_batch_script(input), desc)


def test_script2():
    desc = "real world example 2"
    input = """#! /bin/bash
#PBS -N H3K27me3
#PBS -m e
#PBS -k n
cd /data/$USER/110617/preB/tss_table

# non redundant
slopBed -i preB_H3K27me3-removed.bed -g mm9.genome \\
        -r 126 -s -l 0     \\
    | intersectBed -a stdin -b refseq110201_tss_ud1k.bed -wa -wb \\
    | awk '$2 != c {print; c = $2}'      \\
    | cut -f10     \\
    | sort -S1G    \\
    | uniq -c     \\
    | sed -r 's/^ +//;s/ /|/'     \\
    > count_data/H3K27me3.nr.ncount
    """
    expected = """#! /bin/bash
#SBATCH --job-name="H3K27me3"
#SBATCH --mail-type=END

cd /data/$USER/110617/preB/tss_table

# non redundant
slopBed -i preB_H3K27me3-removed.bed -g mm9.genome \\
        -r 126 -s -l 0     \\
    | intersectBed -a stdin -b refseq110201_tss_ud1k.bed -wa -wb \\
    | awk '$2 != c {print; c = $2}'      \\
    | cut -f10     \\
    | sort -S1G    \\
    | uniq -c     \\
    | sed -r 's/^ +//;s/ /|/'     \\
    > count_data/H3K27me3.nr.ncount
    """
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_script3():
    desc = "real world example 3"
    input = """# This is a sample PBS script. It will request 
# 1 processor on 1 node
# for 4 hours.
#PBS -l nodes=1:ppn=1
#   Request 4 hours of walltime
#PBS -l walltime=4:00:00
#PBS -l pmem=1gb
#   Request that regular output and terminal output go 
#   to the same file
#PBS -j oe
#
#   The following is the body of the script. By default,
#   PBS scripts execute in your home directory, not the
#   directory from which they were submitted. The following
#   line places you in the directory from which the job
#   was submitted.
#
cd $PBS_O_WORKDIR
#
#   Now we want to run the program "hello".  "hello" is in
#   the directory that this script is being submitted from,
#   $PBS_O_WORKDIR.
#
echo "Job started on `hostname` at `date`"
echo "Job Ended at `date`"
    """
    expected = """#! /bin/bash
# This is a sample PBS script. It will request 
# 1 processor on 1 node
# for 4 hours.

#   Request 4 hours of walltime
#SBATCH --time=4:00:00

#   Request that regular output and terminal output go 
#   to the same file

#
#   The following is the body of the script. By default,
#   PBS scripts execute in your home directory, not the
#   directory from which they were submitted. The following
#   line places you in the directory from which the job
#   was submitted.
#
cd $SLURM_SUBMIT_DIR
#
#   Now we want to run the program "hello".  "hello" is in
#   the directory that this script is being submitted from,
#   $SLURM_SUBMIT_DIR.
#
echo "Job started on `hostname` at `date`"
echo "Job Ended at `date`"
    """
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_script4():
    desc = "real world example 4"
    input = """#!/bin/bash -l
#PBS -l walltime=8:00:00,nodes=3:ppn=8,pmem=1000mb
#PBS -m abe
#PBS -M sample_email@umn.edu

cd ~/program_directory
module load intel
module load ompi/intel
mpirun -np 24 program_name < inputfile > outputfile
    """
    expected = """#!/bin/bash -l
#SBATCH --time=8:00:00
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user="sample_email@umn.edu"

cd ~/program_directory
module load intel
module load ompi/intel
mpirun -np 24 program_name < inputfile > outputfile
    """
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_script5():
    desc = "real world example 5"
    input = """# declare a name for this job to be sample_job
#PBS -N my_serial_job  
# request the queue (enter the possible names, if omitted, 
# serial is the default)
#PBS -q serial     
# request 1 node
#PBS -l nodes=1
# request 4 hours and 30 minutes of cpu time
#PBS -l cput=04:30:00        
# mail is sent to you when the job starts and when it 
# terminates or aborts
#PBS -m bea
# specify your email address
#PBS -M John.Smith@dartmouth.edu
# By default, PBS scripts execute in your home directory, not the 
# directory from which they were submitted. The following line 
# places you in the directory from which the job was submitted.  
cd $PBS_O_WORKDIR
# run the program
/path_to_executable/program_name arg1 arg2 ...
exit 0
    """
    expected = """#! /bin/bash
# declare a name for this job to be sample_job
#SBATCH --job-name="my_serial_job"
# request the queue (enter the possible names, if omitted, 
# serial is the default)

# request 1 node

# request 4 hours and 30 minutes of cpu time

# mail is sent to you when the job starts and when it 
# terminates or aborts
#SBATCH --mail-type=BEGIN,END,FAIL
# specify your email address
#SBATCH --mail-user="John.Smith@dartmouth.edu"
# By default, PBS scripts execute in your home directory, not the 
# directory from which they were submitted. The following line 
# places you in the directory from which the job was submitted.  
cd $SLURM_SUBMIT_DIR
# run the program
/path_to_executable/program_name arg1 arg2 ...
exit 0
    """
    check(input, expected, p2s.convert_batch_script(input), desc)
