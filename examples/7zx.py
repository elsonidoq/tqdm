# -*- coding: utf-8 -*-
"""Usage:
  7zx.py [--help | options] <zipfiles>...

Options:
  -h, --help     Print this help and exit
  -v, --version  Print version and exit
  -c, --compressed       Use compressed (instead of uncompressed) file sizes
  -s, --silent   Do not print one row per zip file
  -y, --yes      Assume yes to all queries (for extraction)
  -D=<level>, --debug=<level>
                 Print various types of debugging information. Choices:
                         CRITICAL|FATAL
                         ERROR
                         WARN(ING)
                         [default: INFO]
                         DEBUG
                         NOTSET
  -d, --debug-trace      Print lots of debugging information (-D NOTSET)
"""
from __future__ import print_function
from docopt import docopt
import logging as log
import subprocess
import re
from tqdm import tqdm
import pty
import os
import io
__author__ = "Casper da Costa-Luis <casper.dcl@physics.org>"
__licence__ = "MPLv2.0"
__version__ = "0.2.0"
__license__ = __licence__


RE_SCN = re.compile("([0-9]+)\s+([0-9]+)\s+(.*)$", flags=re.M)


def main():
    args = docopt(__doc__, version=__version__)
    if args.pop('--debug-trace', False):
        args['--debug'] = "NOTSET"
    log.basicConfig(level=getattr(log, args['--debug'], log.INFO),
                    format='%(levelname)s: %(message)s')
    log.debug(args)

    # Get compressed sizes
    zips = {}
    for fn in args['<zipfiles>']:
        info = subprocess.check_output(["7z", "l", fn]).strip()
        finfo = RE_SCN.findall(info)

        # builtin test: last line should be total sizes
        log.debug(finfo)
        totals = map(int, finfo[-1][:2])
        # log.debug(totals)
        for s in range(2):
            assert(sum(map(int, (inf[s] for inf in finfo[:-1]))) == totals[s])
        fcomp = dict((n, int(c if args['--compressed'] else u))
                     for (u, c, n) in finfo[:-1])
        # log.debug(fcomp)
        # zips  : {'zipname' : {'filename' : int(size)}}
        zips[fn] = fcomp

    # Extract
    cmd7zx = ["7z", "x", "-bd"]
    if args['--yes']:
        cmd7zx += ["-y"]
    log.info("Extracting from {:d} file(s)".format(len(zips)))
    with tqdm(total=sum(sum(fcomp.values()) for fcomp in zips.values()),
              unit="B", unit_scale=True) as tall:
        for fn, fcomp in zips.items():
            md, sd = pty.openpty()
            ex = subprocess.Popen(cmd7zx + [fn],
                                  bufsize=1,
                                  stdout=md,  # subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
            os.close(sd)
            with io.open(md, mode="rU", buffering=1) as m:
                with tqdm(total=sum(fcomp.values()), disable=len(zips) < 2,
                          leave=False, unit="B", unit_scale=True) as t:
                    while True:
                        try:
                            l_raw = m.readline()
                        except IOError:
                            break
                        l = l_raw.strip()
                        if l.startswith("Extracting"):
                            exname = l.lstrip("Extracting").lstrip()
                            s = fcomp.get(exname, 0)  # 0 is likely folders
                            t.update(s)
                            tall.update(s)
                        elif l:
                            if not any(l.startswith(i) for i in
                                       ("7-Zip ",
                                        "p7zip Version ",
                                        "Everything is Ok",
                                        "Folders: ",
                                        "Files: ",
                                        "Size: ",
                                        "Compressed: ")):
                                if l.startswith("Processing archive: "):
                                    if not args['--silent']:
                                        t.write(t.format_interval(
                                            t.start_t - tall.start_t) + ' ' +
                                            l.lstrip("Processing archive: "))
                                else:
                                    t.write(l)
            ex.wait()
main.__doc__ = __doc__


if __name__ == "__main__":
    main()
