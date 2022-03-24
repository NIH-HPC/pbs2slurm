#! /usr/bin/env python3
# vim: set ft=python :
"""
Translates PBS batch script to Slurm.

The PBS script is split into
- a shebang line
- a header containing #PBS directives, comments, and empty lines
- the body of the script

pbs2slurm carries out 3 transformation steps
- if no shebang line was present in the PBS script, a new one is added. By 
  default this is #! /bin/bash, but this can be changed (see below).
  pbs2slurm will never alter an existing shebang line.
- #PBS directives in the header are translated, where possible, to #SBATCH 
  directives.
- common PBS environment variables in the body are translated to their SLURM 
  equivalents

Please be sure to manually go over translated scripts to ensure their 
correctness.

If no input file is specified, pbs2slurm reads from stdin. The translated script 
is written to stdout or to a new file

Examples:
    pbs2slurm < pbs_script > slurm_script
    pbs2slurm pbs_script > slurm_script
    pbs2slurm pbs_script slurm_script
    pbs2slurm -s /bin/zsh pbs_script > slurm_script

See also https://hpc.cit.nih.gov/docs/pbs2slurm_tool.html.

Contact staff@helix.nih.gov with questions and bug reports.
"""

from __future__ import print_function
import sys
import re

__version__ = 0.2
__author__ = "Wolfgang Resch"

def info(s):
    print("INFO:    {}".format(s), file=sys.stderr)
def warn(s):
    print("WARNING: {}".format(s), file=sys.stderr)
def error(s):
    print("ERROR:   {}".format(s), file=sys.stderr)

def split_script(input):
    """splits script into shebang, pbs directives, and rest"""
    lines = input.split("\n")
    nlines = len(lines)
    i = 0    
    if lines[0].startswith("#!"):
        shebang = lines[0]
        i = 1
    else:
        shebang = None
    header = []
    while True:
        if i == nlines:
            error("reached end of the file without finding any commands")
            sys.exit(1)
        if lines[i].startswith("#") or lines[i].strip() == "":
            header.append(lines[i])
            i += 1
        else:
            break
    if not header:
        return shebang, "", "\n".join(lines[i:])
    else:
        has_pbs = False
        if len([x for x in header if x.startswith("#PBS")]) > 0: 
            return shebang, "\n".join(header), "\n".join(lines[i:])
        else:
            return shebang, "", "\n".join(header + lines[i:])

def fix_env_vars(input):
    """replace PBS environment variables with their SLURM equivalent"""
    repl = {
        "PBS_O_WORKDIR": "SLURM_SUBMIT_DIR",
        "PBS_JOBID"    : "SLURM_JOBID",
        "PBS_ARRAY_INDEX"  : "SLURM_ARRAY_TASK_ID"}
    output = input
    for pbs, slurm in repl.items():
        output = output.replace(pbs, slurm)
    return output

def fix_jobname(pbs_directives):
    """translates #PBS -N"""
    j_re = re.compile(r'^#PBS[ \t]*-N[ \t]*(\S*)[^\n]*', re.M)
    def _repl(m):
        if m.group(1) == "":
            warn("#PBS -N without argument -> dropped")
        else:
            return '#SBATCH --job-name="{}"'.format(m.group(1))
    return j_re.sub(_repl, pbs_directives)


def fix_email_address(pbs_directives):
    """translates #PBS -M"""
    pbsm_re = re.compile(r'^#PBS[ \t]*-M[ \t]*\b(.*)\b[^\n]*', re.M)
    pbsm_match = pbsm_re.search(pbs_directives)
    def _repl(m):
        if m.group(1) == "":
            warn("#PBS -M without argument -> dropped".format(pbsm_match.group()))
            return ""
        all_adr = [x.strip() for x in m.group(1).split(",")]
        valid_adr = []
        for adr in all_adr:
            if re.match(r'[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,4}', adr) is not None:
                valid_adr.append(adr)
        if len(valid_adr) == 0:
            warn("email address may be invalid: '{}'".format(all_adr[0]))
            use_adr = all_adr[0]
        else:
            use_adr = valid_adr[0]
        return '#SBATCH --mail-user="{}"'.format(use_adr)
    return pbsm_re.sub(_repl, pbs_directives)

def fix_email_mode(pbs_directives):
    """translates #PBS -m"""
    pbsm_re = re.compile(r'^#PBS[ \t]*-m[ \t]*([aben]{0,4})[^\n]*', re.M)
    def _repl(m):
        # n takes precedence if it's present
        pbs_events = m.group(1)
        if "n" in pbs_events or pbs_events == "":
            info("#PBS -m n is the default in slurm -> dropped")
            return ""
        slurm_events = []
        if "a" in pbs_events:
            slurm_events.append("FAIL")
        if "b" in pbs_events:
            slurm_events.append("BEGIN")
        if "e" in pbs_events:
            slurm_events.append("END")
        slurm_events.sort()
        return "#SBATCH --mail-type={}".format(",".join(slurm_events))
    return pbsm_re.sub(_repl, pbs_directives)


def fix_stdout_stderr(pbs_directives):
    """translates #PBS -o, #PBS -e, #PBS -j, and #PBS -k"""
    out_re = re.compile(r'^#PBS[ \t]*-o[ \t]*(\S*)[^\n]*', re.M)
    err_re = re.compile(r'^#PBS[ \t]*-e[ \t]*(\S*)[^\n]*', re.M)
    join_re = re.compile(r'^#PBS[ \t]*-j[ \t]*(\S{0,4})[^\n]*', re.M)
    keep_re = re.compile(r'^#PBS[ \t]*-k[ \t]*(\S{0,4})[^\n]*', re.M)
    # remove the -k directive
    def _repl(m):
        info("#PBS -k is not needed in slurm -> dropped")
        return ""
    pbs_directives = keep_re.sub(_repl, pbs_directives)
    # remove the -j directive
    def _repl(m):
        info("#PBS -j is the default in slurm -> dropped")
        return ""
    pbs_directives = join_re.sub(_repl, pbs_directives)
    # change the -o directive
    def _repl(m):
        if m.group(1) == "":
            warn("#PBS -o without argument -> dropped")
            return ""
        else:
            return "#SBATCH --output={}".format(m.group(1))
    pbs_directives = out_re.sub(_repl, pbs_directives)
    # change the -e directive
    def _repl(m):
        if m.group(1) == "":
            warn("#PBS -e without argument -> dropped")
            return ""
        else:
            return "#SBATCH --error={}".format(m.group(1))
    pbs_directives = err_re.sub(_repl, pbs_directives)
    return pbs_directives

def fix_restartable(pbs_directives):
    """translate #PBS -r; PBS default is 'y'"""
    r_re = re.compile(r'^#PBS[ \t]*-r[ \t]*(\S*)[^\n]*', re.M)
    def _repl(m):
        if m.group(1) == "":
            warn("#PBS -r without argument -> dropped")
            return ""
        elif "y" == m.group(1):
            return "#SBATCH --requeue"
        elif "n" == m.group(1):
            return "#SBATCH --no-requeue"
        else:
            return ""
    return r_re.sub(_repl, pbs_directives)

def fix_shell(pbs_directives):
    """drop #PBS -S"""
    s_re = re.compile(r'^#PBS[ \t]*-S[ \t]*(\S*)[^\n]*', re.M)
    def _repl(m):
        info("#PBS -S: slurm uses #! to determine shell -> dropped")
        return ""
    return s_re.sub(_repl, pbs_directives)

def fix_variable_export(pbs_directives):
    """translate #PBS -V and -v"""
    V_re = re.compile(r'^#PBS[ \t]*-V[^\n]*', re.M)
    pbs_directives = V_re.sub("#SBATCH --export=ALL", pbs_directives)
    v_re = re.compile(r'^#PBS[ \t]*-v[ \t]*([ \t,=\S]*)[ \t]*', re.M)
    def _repl(m):
        if m.group(1) == "":
            warn("#PBS -v withouot arguments -> dropped")
            return ""
        else:
            return "#SBATCH --export={}".format("".join(m.group(1).split()))
    return v_re.sub(_repl, pbs_directives)

def fix_jobarray(pbs_directives):
    """translate #PBS -J"""
    j_re = re.compile(r'^#PBS[ \t]*-J[ \t]*([-0-9]*)[^\n]*', re.M)
    def _repl(m):
        if m.group(1) == "":
            warn("#PBS -J without argument -> dropped")
            return ""
        else:
            return "#SBATCH --array={}".format(m.group(1))
    return j_re.sub(_repl, pbs_directives)

def fix_resource_list(pbs_directives):
    """resource lists were very complicated in the qsub wrapper, which would
    have overridden the resource lists specified in pbs directives. This
    function only looks for walltime and prints a warning"""
    l_re = re.compile(r'^#PBS[ \t]*-l[ \t]*\b([\S:=, \t]*)\b[^\n]*', re.M)
    l_m  = l_re.search(pbs_directives)
    wt_re = re.compile(r'walltime=(\d+):(\d+):(\d+)')
    if l_m is not None:
        def _repl(m):
            resources = m.group(1)
            if "walltime" in resources:
                wt_m = wt_re.search(resources)
                if wt_m is None:
                    return ""
                h = wt_m.group(1)
                m = wt_m.group(2)
                if len(m) == 1:
                    m += "0"
                elif len(m) > 2:
                    return ""
                s = wt_m.group(3)
                if len(s) == 1:
                    s += "0"
                elif len(s) > 2:
                    return ""
                return "#SBATCH --time={}:{}:{}".format(h, m, s)
            elif "nodes" in resources:
                mydir = ''
                rlist = resources.split(':')
                for rx in rlist:
                   cx = rx.split(',')
                   for nx in cx:
                       mx = nx.split('=')
                       if mx[0] == 'nodes':
                           mydir = "#SBATCH --ntasks={}".format(mx[1].strip())
                       elif mx[0] == 'ppn':
                           mydir = mydir + "\n#SBATCH --cpus-per-task={}".format(mx[1].strip())
                       elif mx[0] == 'pmem': 
                           mydir = mydir + "\n#SBATCH --mem-per-cpu={}".format(mx[1].strip())

                return mydir
            else: 
                return ""
        pbs_directives = l_re.sub(_repl, pbs_directives)
    wt_re = re.compile(r'nodes=')
        
    return pbs_directives


def fix_queue(pbs_directives):
    """drop all occurences of -q"""
    q_re = re.compile(r'^#PBS[ \t]*-q[^\n]*', re.M)
    if q_re.search(pbs_directives) is not None:
        info("dropping #PBS -q directive(s)")
        return q_re.sub("", pbs_directives)
    else:
        return pbs_directives




################################################################################
# main conversion function
################################################################################

def convert_batch_script(pbs, interpreter = "/bin/bash"):
    shebang, pbs_directives, commands = split_script(pbs)
    if shebang is None:
        shebang = "#! {}".format(interpreter)
    commands = fix_env_vars(commands)
    if pbs_directives != "":
        pbs_directives = fix_jobname(pbs_directives)
        pbs_directives = fix_email_address(pbs_directives)
        pbs_directives = fix_email_mode(pbs_directives)
        pbs_directives = fix_stdout_stderr(pbs_directives)
        pbs_directives = fix_restartable(pbs_directives)
        pbs_directives = fix_shell(pbs_directives)
        pbs_directives = fix_variable_export(pbs_directives)
        pbs_directives = fix_jobarray(pbs_directives)
        pbs_directives = fix_resource_list(pbs_directives)
        pbs_directives = fix_queue(pbs_directives)
        return "{}\n{}\n{}".format(shebang, pbs_directives, commands)
    else:
        return "{}\n{}".format(shebang, commands)


################################################################################
# command line interface
################################################################################

if __name__ == "__main__":
    import argparse
    cmdline = argparse.ArgumentParser(description = __doc__,
            formatter_class = argparse.RawDescriptionHelpFormatter)
    cmdline.add_argument("--shell", "-s", default = "/bin/bash",
            help = """Shell to insert if shebang line (#! ...) is missing.
                      Defaults to '/bin/bash'""")
    cmdline.add_argument("--version", "-v", action = "store_true",
            default = False)
    cmdline.add_argument("pbs_script", type=argparse.FileType('r'), nargs = "?",
            default = sys.stdin)
    cmdline.add_argument("slurm_script", type=argparse.FileType('w'), nargs = "?",
            default = sys.stdout)
    args = cmdline.parse_args()
    if args.version:
        print("pbs2slurm V{}".format(__version__))
        sys.exit(0)
    if args.pbs_script.isatty():
        print("Please provide a pbs batch script either on stdin or as an argument",
                file = sys.stderr)
        sys.exit(1)
    slurm_out = convert_batch_script(args.pbs_script.read(), args.shell)
    if args.slurm_script:
        args.slurm_script.write(slurm_out)
    else:
        print(slurm_out)
