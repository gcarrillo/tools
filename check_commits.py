#!/usr/bin/env python

import optparse
import os
import subprocess
import sys
import re
import tempfile
import shutil
import errno

# TODO: add option for Meson builds

def get_commit_list(start_ref, end_ref):
    cmd = ['git', 'log', '--pretty=format:%H %s', start_ref + '..' + end_ref]
    fnull = open('/dev/null', 'w')
    try:
        out = subprocess.check_output(cmd, stderr=fnull)
    except subprocess.CalledProcessError as e:
        sys.stderr.write("Error: failed to get list of commits between \"" +
                         start + "\" and \"" + end + "\".\n")
        sys.exit(1)

    # This returns a list of tuples whose members correspond to the matching
    # groups.
    matches = re.findall(r'^(?P<hash>\S+)\s(?P<sub>.*)$', out, re.MULTILINE)
    matches.reverse()

    return matches

def check_git_log():
    cmd = ['devtools/check-git-log.sh', '-1']
    sys.stdout.write("Running: \"" + ' '.join(cmd) + "\"... ")
    fnull = open('/dev/null', 'w')
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        sys.stdout.write("Fail.\n")
        sys.stderr.write("Output:" + e.output + "\n")
        if opts.exit_on_err:
            sys.exit(1)
    except OSError as e:
        sys.stdout.write("\n")
        sys.stderr.write("Error: Couldn't run check-git-log.sh. Are you in "
                         "the root dir of the repo?\n")
        sys.exit(1)
    else:
        sys.stdout.write("Passed.\n")

def check_builds(compilers, build_type, num_jobs, exit_on_err):
    for compiler in compilers:
        arch_str = 'x86_64-native-linuxapp-' + compiler

        run_test_build(build_type, arch_str, num_jobs)
        run_test_build(build_type, arch_str + "+shared", num_jobs)

def run_test_build(build_type, arch_str, num_jobs):
    cmd = ['devtools/test-build.sh', '-j' + num_jobs]
    if build_type == 'short':
        cmd += ['-s']
    cmd += [arch_str]
    sys.stdout.write("Running: \"" + ' '.join(cmd) + "\"... ")
    sys.stdout.flush()
    try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        sys.stdout.write("Failed.\n")
        sys.stderr.write("Output:\n" + e.output + "\n")
        if opts.exit_on_err:
            sys.exit(1)
    else:
        sys.stdout.write("Passed.\n")

def checkout_commit_with_hash(h):
    cmd = ['git', 'checkout', h]
    fnull = open('/dev/null', 'w')
    try:
        subprocess.check_call(cmd, stdout=fnull, stderr=fnull)
    except subprocess.CalledProcessError as e:
        sys.stderr.write("Error: could not checkout commit with hash " + h +
                         ": " + e.strerror)
        sys.exit(1)

def check_patch():
    temp_dir = tempfile.mkdtemp()  
    format_patch_cmd = ['git', 'format-patch', '-o', temp_dir, '-1']
    child_env = os.environ.copy()
    if not 'DPDK_CHECKPATCH_PATH' in child_env:
        child_env["DPDK_CHECKPATCH_PATH"] = \
                "/home/egcarril/src/checkpatch/checkpatch.pl"
    try:
        out = subprocess.check_output(format_patch_cmd,
                                      stderr=subprocess.STDOUT)
        temp_file = out.rstrip()
        check_patch_cmd = ['devtools/checkpatches.sh', temp_file]
        sys.stdout.write("Running: \"" + ' '.join(check_patch_cmd) + "\"... ")
        out = subprocess.check_output(check_patch_cmd, env=child_env,
                                      stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        sys.stdout.write("Failed.\n")
        sys.stderr.write("Output:\n" + e.output + "\n")
        if opts.exit_on_err:
            sys.exit(1)
    else:
        sys.stdout.write("Passed.\n")
    finally:
        try:
            shutil.rmtree(temp_dir)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

def main():
    global opts

    usage_str = """
$ export DPDK_CHECKPATCH_PATH=<path to checkpatch script>
$ %prog [options] <start_ref_not_inclusive> <end_ref_inclusive>

This program runs through a series of checks required by the DPDK upstream
patch submission process.  If DPDK_CHECKPATCH_PATH is not set, a default
location will be used.
"""
    parser = optparse.OptionParser(usage_str)
    parser.add_option('-C', '--repo-dir', action='store', dest='repo_dir',
                      help='Git repository directory')
    parser.add_option('-j', '--num-jobs', action='store', dest='num_jobs',
                      help='Number of concurrent build jobs')
    parser.add_option('-e', '--exit-on-err', action='store_true',
                      dest='exit_on_err',
                      help='Quit if error encountered')
    parser.add_option('--build-type', action='store', type='choice',
                      dest='build_type', choices=['full', 'short', 'skip'],
                     help="""
Choices:
"full" - Build static and shared configs, tests, examples and docs (default) ||
"short" - Skip tests, examples and docs when building ||
"skip" - Don't run the builds at all
                     """)
    parser.add_option('--use-gcc', action='store', type='choice',
                      dest='use_gcc', choices=['yes', 'no'],
                      help="""
Choices:
"yes" - build with GCC (default) ||
"no" - don't built with GCC                      
                      """)
    parser.add_option('--use-clang', action='store', type='choice',
                      dest='use_clang', choices=['yes', 'no'],
                      help="""
Choices:
"yes" - build with clang ||
"no" - don't built with clang (default)                      
                      """)
    parser.add_option('--run-checkgitlog', action='store', type='choice',
                      dest='run_checkgitlog', choices=['yes', 'no'],
                      help="""
Choices: "yes" (default) || "no"
                      """)                      
    parser.add_option('--run-checkpatch', action='store', type='choice',
                      dest='run_checkpatch', choices=['yes', 'no'],
                      help="""
Choices: "yes" (default) || "no"
                      """)                      
    parser.set_defaults(repo_dir=os.getcwd(),
                        num_jobs=1,
                        exit_on_err=False,
                        skip_builds=False,
                        build_type='full',
                        use_gcc='yes',
                        use_clang='no',
                        run_checkgitlog='yes',
                        run_checkpatch='yes')
    (opts, args) = parser.parse_args()

    if len(args) < 2:
        parser.print_usage()
        sys.exit(1)

    start_ref = args[0]
    end_ref = args[1]

    if opts.repo_dir:
        try:
            os.chdir(opts.repo_dir)
        except OSError as e:
            sys.stderr.write("Error: Could not change to repo directory: " +
                             e.strerror + ": " + opts.repo_dir + "\n")
            sys.exit(1)

    compilers = []
    if opts.use_gcc == 'yes':
        compilers.append('gcc')
    if opts.use_clang == 'yes':
        compilers.append('clang')

    commit_tuples = get_commit_list(start_ref, end_ref)

    for i, c in enumerate(commit_tuples):
        if i > 0:
            sys.stdout.write("\n==========================================\n\n")
        sys.stdout.write("Commit: " + c[1] + "\n")

        checkout_commit_with_hash(c[0])

        if opts.run_checkgitlog == 'yes':
            check_git_log()

        if opts.build_type != 'skip':
            check_builds(compilers, opts.build_type, opts.num_jobs,
                         opts.exit_on_err)

        if opts.run_checkpatch == 'yes':
            check_patch()

if __name__ == "__main__":
    main() 
