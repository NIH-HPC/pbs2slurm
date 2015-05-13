#! /usr/local/bin/python
# vim: set ft=python :
# Created by: Wolfgang Resch



#Notes: 
# - PBS directives in batch script use a more relaxed
#   grammar than command line switches. For example
#       '#PBS -N foo'
#       '#PBS -Nfoo'
#       '#PBS-Nfoo'
#       all work! All of these will be correctly translated.
# - to get an idea of what is in PBS job scripts i collected
#   40119 pbs directives from user scripts. Frequencies
#   of the different directives:
#       
#   24034 #PBS -N
#   14504 #PBS -m
#     458 #PBS -k
#     238 #PBS -l
#     213 #PBS -o
#     212 #PBS -j
#     159 #PBS -q
#     108 #PBS -r
#     104 #PBS -e
#      42 #PBS -S
#      26 #PBS -M
#      16 #PBS -V
#       1 #PBS 
#       1 #PBS -J
#       1 #PBS -v
#       1 #PBS -wd
#   a surprising number of -k directives:
#       1 #PBS -k o
#     457 #PBS -k oe
#   where -k oe results in out and err files in the user's home          
# - this script is not computationally efficient with all the
#   repeated string substitutions. However, efficiency doesn't 
#   really matter for this script.
# - this script does not gracefully deal with multiple occurences
#   of the same options. It generally translates them all. This 
#   could lead to some confusion for scripts that use, for example,
#   #PBS -V and #PBS -v, but those are rare (and that's kind of iffy
#   to begin with).


from __future__ import print_function
import sys
import re

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
        "PBS_ARRAYID"  : "SLURM_ARRAY_TASK_ID"}
    output = input
    for pbs, slurm in repl.items():
        output = output.replace(pbs, slurm)
    return output

def fix_jobname(pbs_directives):
    """translates #PBS -N"""
    j_re = re.compile(r'^#PBS[ \t]*-N[ \t]*(\S*)[^\n]*', re.M)
    j_ma = j_re.search(pbs_directives)
    if j_ma is not None:
        if j_ma.group(1) != "":
            return j_re.sub(r'#SBATCH --job-name="\1"',
                          pbs_directives)
        else:
            # drop directives with empty jobname
            return j_re.sub("",
                          pbs_directives)
    return pbs_directives

def fix_email_address(pbs_directives):
    """translates #PBS -M"""
    pbsm_re = re.compile(r'^#PBS[ \t]*-M[ \t]*([^\s,]*)[^\n]*', re.M)
    pbsm_match = pbsm_re.search(pbs_directives)
    if pbsm_match is None:
        return pbs_directives
    else:
        # check for valid email address
        if re.match(r'[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,4}', pbsm_match.group(1)) is None:
            warn("Invalid or missing email address: '{}'; directive ignored".format(
                pbsm_match.group(1)))
            return pbsm_re.sub('', pbs_directives)
        else:
            return pbsm_re.sub(r'#SBATCH --mail-user="\1"',
                               pbs_directives)

def fix_email_mode(pbs_directives):
    """translates #PBS -m"""
    pbsm_re = re.compile(r'^#PBS[ \t]*-m[ \t]*([aben]{0,4})[^\n]*', re.M)
    pbsm_m = pbsm_re.search(pbs_directives)
    if pbsm_m is None:
        return pbs_directives
    else:
        # n takes precedence if it's present
        pbs_events = pbsm_m.group(1)
        if "n" in pbs_events or pbs_events == "":
            return pbsm_re.sub('', pbs_directives)
        slurm_events = []
        if "a" in pbs_events:
            slurm_events.append("FAIL")
        if "b" in pbs_events:
            slurm_events.append("BEGIN")
        if "e" in pbs_events:
            slurm_events.append("END")
        slurm_events.sort()
        return pbsm_re.sub("#SBATCH --mail-type={}".format(",".join(slurm_events)),
                pbs_directives)


def fix_stdout_stderr(pbs_directives):
    """translates #PBS -o, #PBS -e, #PBS -j, and #PBS -k"""
    out_re = re.compile(r'^#PBS[ \t]*-o[ \t]*(\S*)[^\n]*', re.M)
    out_m  = out_re.search(pbs_directives)
    err_re = re.compile(r'^#PBS[ \t]*-e[ \t]*(\S*)[^\n]*', re.M)
    err_m  = err_re.search(pbs_directives)
    join_re = re.compile(r'^#PBS[ \t]*-j[ \t]*(\S{0,4})[^\n]*', re.M)
    join_m  = join_re.search(pbs_directives)
    keep_re = re.compile(r'^#PBS[ \t]*-k[ \t]*(\S{0,4})[^\n]*', re.M)
    keep_m  = keep_re.search(pbs_directives)
    # remove the -k directive
    if keep_m is not None:
        warn("#PBS -k directive removed")
        pbs_directives = keep_re.sub(r'', pbs_directives)
    # remove the -j directive
    if join_m is not None:
        warn("#PBS -j directive removed (joining is done by default in slurm)")
        pbs_directives = join_re.sub(r'', pbs_directives)
    # change the -o directive
    if out_m is not None:
        if out_m.group(1) != "":
            pbs_directives = out_re.sub(r'#SBATCH --output=\1', pbs_directives)
        else:
            warn("Dropping #PBS -o without path")
            pbs_directives = out_re.sub("", pbs_directives)
    # change the -e directive
    if err_m is not None:
        if err_m.group(1) != "":
            pbs_directives = err_re.sub(r'#SBATCH --error=\1', pbs_directives)
        else:
            warn("Dropping #PBS -e without path")
            pbs_directives = err_re.sub("", pbs_directives)
    return pbs_directives

def fix_restartable(pbs_directives):
    """translate #PBS -r; PBS default is 'y'"""
    r_re = re.compile(r'^#PBS[ \t]*-r[ \t]*(\S*)[^\n]*', re.M)
    r_ma = r_re.search(pbs_directives)
    if r_ma is not None:
        if r_ma.group(1) == "y":
            pbs_directives = r_re.sub("#SBATCH --requeue", pbs_directives)
        elif r_ma.group(1) == "n":
            pbs_directives = r_re.sub("#SBATCH --no-requeue", pbs_directives)
        else:
            pbs_directives = r_re.sub("", pbs_directives)
    return pbs_directives

def fix_shell(pbs_directives):
    """drop #PBS -S"""
    s_re = re.compile(r'^#PBS[ \t]*-S[ \t]*(\S*)[^\n]*', re.M)
    if s_re.search(pbs_directives) is not None:
        pbs_directives = s_re.sub("", pbs_directives)
        warn("Dropping #PBS -S directive; slurm scripts use shebang line")
    return pbs_directives

def fix_variable_export(pbs_directives):
    """translate #PBS -V and -v"""
    V_re = re.compile(r'^#PBS[ \t]*-V[^\n]*', re.M)
    V_ma = V_re.search(pbs_directives)
    if V_ma is not None:
        pbs_directives = V_re.sub("#SBATCH --export=ALL", pbs_directives)
    v_re = re.compile(r'^#PBS[ \t]*-v[ \t]*([ \t,=\S]*)[ \t]*', re.M)
    v_ma = v_re.search(pbs_directives)
    if v_ma is not None:
        if v_ma.group(1) == "":
            pbs_directives = v_re.sub("", pbs_directives)
            warn("Removing empty #PBS -v: '{}".format(v_ma.group()))
        else:
            def _repl(m):
                return "#SBATCH --export={}".format("".join(m.group(1).split()))
            pbs_directives = v_re.sub(_repl, pbs_directives)
    return pbs_directives

def fix_jobarray(pbs_directives):
    """drop #PBS -J"""
    j_re = re.compile(r'^#PBS[ \t]*-J[^\n]*', re.M)
    if j_re.search(pbs_directives) is not None:
        warn("Dropping #PBS -J directive")
        return j_re.sub("", pbs_directives)
    else:
        return pbs_directives

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
            if not "walltime" in resources:
                return ""
            else:
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
        pbs_directives = l_re.sub(_repl, pbs_directives)
   
    return pbs_directives


def fix_queue(pbs_directives):
    """drop all occurences of -q"""
    q_re = re.compile(r'^#PBS[ \t]*-q[^\n]*', re.M)
    if q_re.search(pbs_directives) is not None:
        warn("Dropping #PBS -q directive(s)")
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
