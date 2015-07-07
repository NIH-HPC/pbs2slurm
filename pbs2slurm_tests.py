import pbs2slurm as p2s
import sys
import atexit
import difflib

sys.stderr = sys.stdout

html = open("testcases.html", "w")

def html_out(fh, pbs, slurm, desc):
    pbss = pbs.replace(">", "&gt;").replace("<", "&lt;")
    slurms = slurm.replace(">", "&gt;").replace("<", "&lt;")
    fh.write("""
    <tr><td colspan=2>{desc}</td></tr>
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
<table id="test_output">
    <tr><th><b>PBS script</b></th>
        <th><b>SLURM script</b></th>
    </tr>
""")

html_header(html)


def check(input, exp, obs, desc):
    if exp != obs:
        d = difflib.Differ()
        sys.stdout.writelines(d.compare(
            exp.splitlines(1),
            obs.splitlines(1)))
        assert False
    else:
        # only output testcases that pass
        html_out(html, input, exp, desc)
        

def test_plain_bash():
    desc = "Plain bash scripts remain unchanged"
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
    desc = "Change <tt>PBS_O_WORKDIR</tt> to <tt>SLURM_SUBMIT_DIR</tt>"
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
    desc = "Change <tt>PBS_JOBID</tt> to <tt>SLURM_JOBID</tt>"
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
    desc  = "Change <tt>PBS_ARRAY_INDEX</tt> to <tt>SLURM_ARRAY_TASK_ID</tt>"
    input = """#! /bin/bash
set -e
set -o pipefail

module load fastqc
cd /data/$USER/test_data
module load bowtie/1.1.1 samtools/1.2
gunzip -c sample${PBS_ARRAY_INDEX}.fastq.gz \\
   | bowtie --sam --best --strata --all -m1 -n2 \\
       --threads=10 /path/to/genome/index -  \\
   | samtools view -Sb -F4 - \\
   > sample${PBS_ARRAY_INDEX}.bam
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
    desc = "If there is not shebang line, insert one (bash by default, can be changed)"
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
    desc = """PBS directives in the header are identified and transformed. PBS directives
    in the body are left unchanged"""
    input = """#! /bin/bash
#some other comment
#PBS -N fastqc_job

#PBS -N other_name
set -e
set -o pipefail

#PBS -N other
module load fastqc
cd /data/$USER/test_data
"""
    expected = """#! /bin/bash
#some other comment
#SBATCH --job-name="fastqc_job"

#SBATCH --job-name="other_name"
set -e
set -o pipefail

#PBS -N other
module load fastqc
cd /data/$USER/test_data
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

################################################################################
# job name
def test_jobname():
    desc = "Change <tt>#PBS -N</tt> to <tt>#SBATCH --job-name</tt>"
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
    desc = "<tt>#PBS -N</tt> is dropped if job name is missing"
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
    desc = "Change </tt>#PBS -M</tt> to <tt>#SBATCH --mail-user</tt>"
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
    desc = "<tt>#PBS -M</tt> is dropped if email address is missing"
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
    desc = "If <tt>#PBS -M</tt> has a list of valid email addresses, pick first one"
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
    desc = "If <tt>#PBS -M</tt> has a list of email addresses, pick first valid one"
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
    desc = "Drop <tt>#PBS -m n</tt> email modes since this is the default behaviour for Slurm"
    input = """#! /bin/bash
#PBS -m n

module load bowtie
"""
    expected = """#! /bin/bash


module load bowtie
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_email_modes_a():
    desc = "Change <tt>#PBS -m a</tt> to <tt>#SBATCH --mail-type=FAIL</tt>"
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
    desc = "Change <tt>#PBS -m b</tt> to <tt>#SBATCH --mail-type=BEGIN</tt>"
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
    desc = "Change <tt>#PBS -m e</tt> to <tt>#SBATCH --mail-type=END</tt>"
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
    desc = "Change <tt>#PBS -m be|eb</tt> to <tt>#SBATCH --mail-type=BEGIN,END</tt>"
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
    desc = "Change <tt>#PBS -m abe|aeb|...</tt> to <tt>#SBATCH --mail-type=BEGIN,END,FAIL</tt>"
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
    desc = "If <tt>#PBS -m</tt> contains n in addition to other options, n has precedence since it's Slurm's default"
    input = """#! /bin/bash
#PBS -m aben

module load bowtie
"""
    expected = """#! /bin/bash


module load bowtie
"""
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_email_modes_empty():
    desc = "<tt>#PBS -m</tt> is dropped if email mode is missing"
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
    desc = "<tt>#PBS -k</tt> is dropped since it is not necessary for Slurm"
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
    desc = "<tt>#PBS -j</tt> is dropped since joining stdout and stderr is the default in Slurm"
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

def test_stdout_directive():
    desc = "Change <tt>#PBS -o</tt> to <tt>#SBATCH --output</tt>"
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
    desc = "<tt>#PBS -o</tt> is dropped if output path is missing"
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
    desc = "Change <tt>#PBS -e</tt> to <tt>#SBATCH --error</tt>"
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
    desc = "<tt>#PBS -e</tt> is dropped if error path is missing"
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
    desc = "Change <tt>#PBS -r y</tt> to <tt>#SBATCH --requeue</tt>"
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
    desc = "Change <tt>#PBS -r n</tt> to <tt>#SBATCH --no-requeue</tt>"
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
    desc = "<tt>#PBS -r</tt> is dropped if any other argument is detected or the argument is missing"
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
    desc = "<tt>#PBS -S</tt> is dropped since Slurm uses shebang lines to determine the interpreter"
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
    desc = "Change <tt>#PBS -V</tt> to <tt>#SBATCH --export=ALL</tt> (even though this is the Slurm default"
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
    desc = "Change <tt>#PBS -v</tt> to <tt>#SBATCH --export=</tt>"
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
    desc = "Change <tt>#PBS -v</tt> to <tt>#SBATCH --export=</tt>; remove spaces"
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
    desc = "Change <tt>#PBS -v</tt> to <tt>#SBATCH --export=</tt>; remove spaces"
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
    desc = "Change <tt>#PBS -J</tt> to <tt>#SBATCH --array</tt>" 
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
    desc = "<tt>#PBS -J</tt> is dropped if argument is missing"
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
    desc = "The only thing parsed out of <tt>PBS -l</tt> resource lists is walltime"
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
    desc = "Drop <tt>#PBS -q</tt> since there is not reliable, straight forward translation. Please provide partition on the command line" 
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
# complete examples
def test_script1():
    desc = "Complete example 1"
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
    desc = "Complete example 2"
    input = """#! /bin/bash
#PBS -N H3K27me3
#PBS -m e
#PBS -k n
cd ${PBS_O_WORKDIR}

# non redundant
slopBed -i K27me3.bed -g mm9.genome -r 126 -s -l 0  \\
    | intersectBed -a stdin -b refseqTss.bed -wa -wb\\
    | awk '$2 != c {print; c = $2}'      \\
    | cut -f10     \\
    | sort -S1G    \\
    | uniq -c     \\
    | sed -r 's/^ +//;s/ /|/'     \\
    > count_data/K27me3.nr.ncount
    """
    expected = """#! /bin/bash
#SBATCH --job-name="H3K27me3"
#SBATCH --mail-type=END

cd ${SLURM_SUBMIT_DIR}

# non redundant
slopBed -i K27me3.bed -g mm9.genome -r 126 -s -l 0  \\
    | intersectBed -a stdin -b refseqTss.bed -wa -wb\\
    | awk '$2 != c {print; c = $2}'      \\
    | cut -f10     \\
    | sort -S1G    \\
    | uniq -c     \\
    | sed -r 's/^ +//;s/ /|/'     \\
    > count_data/K27me3.nr.ncount
    """
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_script3():
    desc = "Complete example 3"
    input = """# This is a sample PBS script. It will 
# request 1 processor on 1 node
# for 4 hours.
#PBS -l nodes=1:ppn=1
#   Request 4 hours of walltime
#PBS -l walltime=4:00:00
#PBS -l pmem=1gb
#   Request that stdout and stderr go
#   to the same file
#PBS -j oe
#
# ======== BODY ========
cd $PBS_O_WORKDIR
echo "Job started on `hostname` at `date`"
./hello
echo "Job Ended at `date`"
    """
    expected = """#! /bin/bash
# This is a sample PBS script. It will 
# request 1 processor on 1 node
# for 4 hours.

#   Request 4 hours of walltime
#SBATCH --time=4:00:00

#   Request that stdout and stderr go
#   to the same file

#
# ======== BODY ========
cd $SLURM_SUBMIT_DIR
echo "Job started on `hostname` at `date`"
./hello
echo "Job Ended at `date`"
    """
    check(input, expected, p2s.convert_batch_script(input), desc)

def test_script4():
    desc = "Complete example 4"
    input = """#!/bin/bash -l
#PBS -l walltime=8:00:00,nodes=3:ppn=8,pmem=1000mb
#PBS -m abe
#PBS -M sample_email@floyd.edu

cd ~/program_directory
module load intel
module load ompi/intel
mpirun -np 24 program_name < inputfile > outputfile
    """
    expected = """#!/bin/bash -l
#SBATCH --time=8:00:00
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user="sample_email@floyd.edu"

cd ~/program_directory
module load intel
module load ompi/intel
mpirun -np 24 program_name < inputfile > outputfile
    """
    check(input, expected, p2s.convert_batch_script(input), desc)

