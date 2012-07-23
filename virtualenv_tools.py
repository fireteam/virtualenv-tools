#!/usr/bin/env python
"""
    move-virtualenv
    ~~~~~~~~~~~~~~~

    A helper script that moves virtualenvs to a new location.

    It only supports POSIX based virtualenvs and Python 2 at the moment.

    :copyright: (c) 2012 by Fireteam Ltd.
    :license: BSD, see LICENSE for more details.
"""
import os
import re
import sys
import marshal
import optparse
import subprocess
from types import CodeType


ACTIVATION_SCRIPTS = [
    'activate',
    'activate.csh',
    'activate.fish'
]
_pybin_match = re.compile(r'^python\d+\.\d+$')
_activation_path_re = re.compile(r'^(?:set -gx |setenv |)VIRTUAL_ENV[ =]"(.*?)"\s*$')


def update_activation_script(script_filename, new_path):
    """Updates the paths for the activate shell scripts."""
    with open(script_filename) as f:
        lines = list(f)

    def _handle_sub(match):
        text = match.group()
        start, end = match.span()
        g_start, g_end = match.span(1)
        return text[:(g_start - start)] + new_path + text[(g_end - end):]

    changed = False
    for idx, line in enumerate(lines):
        new_line = _activation_path_re.sub(_handle_sub, line)
        if line != new_line:
            lines[idx] = new_line
            changed = True

    if changed:
        print 'A %s' % script_filename
        with open(script_filename, 'w') as f:
            f.writelines(lines)


def update_script(script_filename, new_path):
    """Updates shebang lines for actual scripts."""
    with open(script_filename) as f:
        lines = list(f)
    if not lines:
        return

    if not lines[0].startswith('#!'):
        return
    args = lines[0][2:].strip().split()
    if not args:
        return

    if not args[0].endswith('/bin/python') or \
       '/usr/bin/env python' in args[0]:
        return

    new_bin = os.path.join(new_path, 'bin', 'python')
    if new_bin == args[0]:
        return

    args[0] = new_bin
    lines[0] = '#!%s\n' % ' '.join(args)
    print 'S %s' % script_filename
    with open(script_filename, 'w') as f:
        f.writelines(lines)


def update_scripts(bin_dir, new_path):
    """Updates all scripts in the bin folder."""
    for fn in os.listdir(bin_dir):
        if fn in ACTIVATION_SCRIPTS:
            update_activation_script(os.path.join(bin_dir, fn), new_path)
        else:
            update_script(os.path.join(bin_dir, fn), new_path)


def update_pyc(filename, new_path):
    """Updates the filenames stored in pyc files."""
    with open(filename, 'rb') as f:
        magic = f.read(8)
        code = marshal.load(f)

    def _make_code(code, filename, consts):
        return CodeType(code.co_argcount, code.co_nlocals, code.co_stacksize,
                        code.co_flags, code.co_code, tuple(consts),
                        code.co_names, code.co_varnames, filename,
                        code.co_name, code.co_firstlineno, code.co_lnotab,
                        code.co_freevars, code.co_cellvars)

    def _process(code):
        new_filename = new_path
        consts = []
        for const in code.co_consts:
            if type(const) is CodeType:
                const = _process(const)
            consts.append(const)
        if new_path != code.co_filename or consts != list(code.co_consts):
            code = _make_code(code, new_path, consts)
        return code

    new_code = _process(code)

    if new_code is not code:
        print 'B %s' % filename
        with open(filename, 'wb') as f:
            f.write(magic)
            marshal.dump(new_code, f)


def update_pycs(lib_dir, new_path, lib_name):
    """Walks over all pyc files and updates their paths."""
    files = []

    def get_new_path(filename):
        filename = os.path.normpath(filename)
        if filename.startswith(lib_dir.rstrip('/') + '/'):
            return os.path.join(new_path, filename[len(lib_dir) + 1:])

    for dirname, dirnames, filenames in os.walk(lib_dir):
        for filename in filenames:
            if filename.endswith(('.pyc', '.pyo')):
                filename = os.path.join(dirname, filename)
                local_path = get_new_path(filename)
                if local_path is not None:
                    update_pyc(filename, local_path)


def update_local(base, new_path):
    """On some systems virtualenv seems to have something like a local
    directory with symlinks.  It appears to happen on debian systems and
    it causes havok if not updated.  So do that.
    """
    local_dir = os.path.join(base, 'local')
    if not os.path.isdir(local_dir):
        return

    for folder in 'bin', 'lib', 'include':
        filename = os.path.join(local_dir, folder)
        target = '../%s' % folder
        if os.path.islink(filename) and os.readlink(filename) != target:
            os.remove(filename)
            os.symlink('../%s' % folder, filename)
            print 'L %s' % filename


def update_paths(base, new_path):
    """Updates all paths in a virtualenv to a new one."""
    if new_path == 'auto':
        new_path = os.path.abspath(base)
    if not os.path.isabs(new_path):
        print 'error: %s is not an absolute path' % new_path
        return False

    bin_dir = os.path.join(base, 'bin')
    base_lib_dir = os.path.join(base, 'lib')
    lib_dir = None
    lib_name = None

    if os.path.isdir(base_lib_dir):
        for folder in os.listdir(base_lib_dir):
            if _pybin_match.match(folder):
                lib_name = folder
                lib_dir = os.path.join(base_lib_dir, folder)
                break

    if lib_dir is None or not os.path.isdir(bin_dir) \
       or not os.path.isfile(os.path.join(bin_dir, 'python')):
        print 'error: %s does not refer to a python installation' % base
        return False

    update_scripts(bin_dir, new_path)
    update_pycs(lib_dir, new_path, lib_name)
    update_local(base, new_path)

    return True


def reinitialize_virtualenv(path):
    """Re-initializes a virtualenv."""
    lib_dir = os.path.join(path, 'lib')
    if not os.path.isdir(lib_dir):
        print 'error: %s is not a virtualenv bin folder' % path
        return False

    py_ver = None
    for filename in os.listdir(lib_dir):
        if _pybin_match.match(filename):
            py_ver = filename
            break

    if py_ver is None:
        print 'error: could not detect python version of virtualenv %s' % path
        return False

    sys_py_executable = subprocess.Popen(['which', py_ver],
        stdout=subprocess.PIPE).communicate()[0].strip()

    if not sys_py_executable:
        print 'error: could not find system version for expected python ' \
            'version %s' % py_ver
        return False

    lib_dir = os.path.join(path, 'lib', py_ver)

    args = ['virtualenv', '-p', sys_py_executable]
    if not os.path.isfile(os.path.join(lib_dir,
            'no-global-site-packages.txt')):
        args.append('--system-site-packages')

    for filename in os.listdir(lib_dir):
        if filename.startswith('distribute-') and \
           filename.endswith('.egg'):
            args.append('--distribute')

    new_env = {}
    for key, value in os.environ.items():
        if not key.startswith('VIRTUALENV_'):
            new_env[key] = value
    args.append(path)
    subprocess.Popen(args, env=new_env).wait()


def main():
    parser = optparse.OptionParser()
    parser.add_option('--reinitialize', action='store_true',
                      help='Updates the python installation '
                      'and reinitializes the virtualenv.')
    parser.add_option('--update-path', help='Update the path for all '
                      'required executables and helper files that are '
                      'supported to the new python prefix.  You can also set '
                      'this to "auto" for autodetection.')
    options, paths = parser.parse_args()
    if not paths:
        paths = ['.']

    rv = 0

    if options.reinitialize:
        for path in paths:
            reinitialize_virtualenv(path)
    if options.update_path:
        for path in paths:
            if not update_paths(path, options.update_path):
                rv = 1
    sys.exit(rv)


if __name__ == '__main__':
    main()
