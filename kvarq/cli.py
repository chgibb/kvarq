'''
KvarQ command line client
'''

from kvarq import VERSION
from kvarq import genes
from kvarq import engine
from kvarq import analyse
from kvarq.util import ProgressBar, TextHist, json_dump, JsonSummary, get_help_path
from kvarq.fastq import Fastq, FastqFileFormatException
from kvarq.log import lo, appendlog, set_debug, set_warning, format_traceback
from kvarq.config import default_config
from kvarq.testsuites import discover_testsuites, load_testsuites, update_testsuites

import argparse
import sys
import threading
import time
import json
import os, os.path
import codecs
from pprint import pprint
import glob

ERROR_COMMAND_LINE_SWITCH = -1
ERROR_FASTQ_FORMAT_ERROR = -2
ERROR_FILE_EXISTS = -3

# utils {{{1

def traceit(type, value, tb):
    if hasattr(sys, 'ps1') or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb) # default hook
    else:
        import traceback, pdb
        traceback.print_exception(type, value, tb)
        print()
        pdb.post_mortem(tb)

def heardEnter():
    # src : http://stackoverflow.com/questions/292095/polling-the-keyboard-in-python
    try:
        import select
        i,o,e = select.select([sys.stdin],[],[],0.0001)
        for s in i:
            if s == sys.stdin:
                input = sys.stdin.readline()
                return True
        return False
    except:
        # e.g. windows fails
        return False


# scan {{{1

def scan(args):

    testsuite_paths = discover_testsuites(args.testsuite_directory or [])
    if args.select_all:
        testsuites = load_testsuites(testsuite_paths, testsuite_paths.keys())
    else:
        testsuites = load_testsuites(testsuite_paths, args.select)

    if not testsuites:
        sys.stderr.write('\n*** you must specify at least one testsuite! ***\n\n')
        sys.stderr.write('(use the -t command line switch)\n\n')
        sys.exit(ERROR_COMMAND_LINE_SWITCH)

    # prepare scanning {{{2

    try:
        fastq = Fastq(args.fastq, paired=not args.no_paired, variant=args.variant)
    except FastqFileFormatException, e:
        lo.error('cannot open file %s : %s'%(args.fastq, str(e)))
        sys.exit(ERROR_FASTQ_FORMAT_ERROR)

    engine.config(
            nthreads=args.threads,
            maxerrors=args.errors,
            Amin=fastq.Q2A(args.quality),
            Azero=fastq.Azero,
            minreadlength=args.readlength,
            minoverlap=args.overlap
        )

    analyser = analyse.Analyser()

    if not args.force:
        if os.path.exists(args.json):
            lo.error('will not overwrite file ' + args.json)
            sys.exit(ERROR_FILE_EXISTS)
        if args.extract_hits and os.path.exists(args.extract_hits):
            lo.error('will not overwrite file ' + args.extract_hits)
            sys.exit(ERROR_FILE_EXISTS)

    # do scanning {{{2

    mb = os.path.getsize(args.fastq) / 1024 / 1024
    lo.info('scanning {} ({})...'.format(
            ', '.join(fastq.filenames()),
            ', '.join(['%.2f MB' % (filesize/1024.**2) for filesize in fastq.filesizes()])
        ))
    t0 = time.time()

    class AnalyseThread(threading.Thread):

        def __init__(self, analyser):
            super(AnalyseThread, self).__init__(name='analyse-thread')
            self.analyser = analyser
            self.finished = False
            self.exception = None
            self.traceback = None

        def run(self):
            try:
                self.analyser.spacing = args.spacing
                self.analyser.scan(fastq, testsuites, do_reverse=not args.no_reverse)
                self.finished = True
            except Exception, e:
                self.exception = e
                self.traceback = format_traceback(sys.exc_info())

    at = AnalyseThread(analyser)

    at.start()
    pb = ProgressBar(total=1)
    pb.start()

    # scan / stats loop {{{3
    sys.stderr.write('\n')
    sigints = 0
    sigintt = time.time()
    while not at.finished and at.exception is None:
        time.sleep(1)
        stats = engine.stats()
        if not stats['records_parsed']:
            continue

        if args.progress:
            pb.update(stats['progress'])
            sys.stderr.write(str(pb))

#        if args.coverage:
#            means = sorted([n/len(analyser[i])
#                    for i, n in enumerate(stats['nseqbasehits'])])
#
#            if means and means[len(means)/2] > args.coverage:
#                print >> sys.stderr
#                lo.info('aborting scanning: median of coverage %d > %d'%(
#                        means[len(means)/2], args.coverage))
#                engine.stop()
#                break

        # <CTRL-C> : output additional information
        if stats['sigints'] > sigints:

            # 2nd time : cancel scanning
            if time.time() - sigintt < 2.:
                sys.stderr.write('\n\n*** caught multiple <CTRL-C> '
                        'within 2s : abort scanning ***')
                engine.stop()
                at.join()
                break

            print()
            print(TextHist(title='readlengths').draw(stats['readlengths'], indexed=True))

            means = sorted([n/len(analyser[i])
                    for i, n in enumerate(stats['nseqbasehits'])])
            print()
            print(TextHist(title='mean coverages').draw(sorted(means), indexed=False))

            sigints = stats['sigints']
            sigintt = time.time()

    at.join()
    if at.exception:
        lo.error('could not scan %s : %s [%s]'%(args.fastq, str(at.exception), at.traceback))
        sys.exit(ERROR_FASTQ_FORMAT_ERROR)

    sys.stderr.write('\n')
    mbp = '%smb'% (stats['parsed']/1024**2)
    mbt = '%smb'% (stats['total' ]/1024**2)
    lo.info('performed scanning of %.2f%% (%s/%s, %d records) in %.3f seconds'% (
            1e2*stats['progress'], mbp, mbt, stats['records_parsed'], time.time()-t0))

    # save to file {{{2
    analyser.update_testsuites()

    data = analyser.encode(hits=args.hits)
    j = codecs.open(args.json, 'w', 'utf-8')
    json_dump(data, j)

    if args.extract_hits:
        at.analyser.extract_hits(args.extract_hits)


# show {{{1

def show(args):

    fastq = Fastq(args.file)

    if args.quality:
        Amin = fastq.Q2A(args.quality)
        n = args.number
        points = args.points
        lo.info('determining readlengths with quality>=%d of %s '
                'by reading %d records at %d points'%(
                args.quality, args.file, n, points))
        rls = fastq.lengths(Amin, n=n, points=points)

        hist = TextHist()
        print(hist.draw(sorted(rls)))

    if args.info:
        print('dQ=' + str(fastq.dQ))
        print('variants=' + str(fastq.variants))
        print('readlength=' + str(fastq.readlength))
        print('records_approx=' + str(fastq.records_approx or '?'))


# update {{{1

def update(args):

    if args.fastq:
        lo.warning('re-reading of hits not currently implemented')

    data = json.load(file(args.json))

    testsuite_paths = discover_testsuites(args.testsuite_directory or [])
    testsuites = {}
    update_testsuites(testsuites, data['info']['testsuites'], testsuite_paths)

    analyser = analyse.Analyser()
    analyser.decode(testsuites, data)
    analyser.update_testsuites()

    # save results back to .json
    data = analyser.encode(hits = analyser.hits is not None)
    j = codecs.open(args.json, 'w', 'utf-8')
    lo.info('re-wrote results to file ' + args.json)
    json.dump(data, j, indent=2)


# summarize {{{1

def summarize(args):

    js = JsonSummary()
    for fname in args.json:
        lo.info('processing ' + fname)
        js.add(fname)

    js.dump()


# illustrate {{{1

def illustrate(args):

    data = json.load(file(args.file))

    testsuite_paths = discover_testsuites(args.testsuite_directory or [])
    testsuites = {}
    update_testsuites(testsuites, data['info']['testsuites'], testsuite_paths)

    analyser = analyse.Analyser()
    lo.info('loading json-file args.file')
    analyser.decode(testsuites, data)
    lo.info('updating testsuites')
    analyser.update_testsuites()

    if args.readlengths:
        rls = analyser.stats['readlengths']

        hist = TextHist()
        print(hist.draw(rls, indexed=True))

    if args.coverage:
        for name, testsuite in analyser.testsuites.items():
            print(name + ':')
            for test in testsuite.tests:
                print('  - %s : %s' % (test, analyser[test]))
            print()

    if args.results:
        for testsuite, results in analyser.results.items():
            print('\n'+testsuite)
            print('-'*len(testsuite))
            pprint(results)


# version {{{1

def version(args):
    print(VERSION)


# gui {{{1

def gui(args):

    testsuite_paths = discover_testsuites(args.testsuite_directory or [])

    # only import Tkinter etc now
    import Tkinter
    from kvarq.gui.main import MainGUI
    MainGUI(testsuite_paths=testsuite_paths)
    Tkinter.mainloop()



# info {{{1

def info(args):

    testsuite_paths = discover_testsuites(args.testsuite_directory or [])
    if args.select_all:
        testsuites = load_testsuites(testsuite_paths, testsuite_paths.keys())
    else:
        testsuites = load_testsuites(testsuite_paths, args.select or [])

    print('version=' + VERSION)
    testsuites_descr = []
    tbp = tests = 0
    for name, testsuite in testsuites.items():
        bp = 0
        for test in testsuite.tests:
            if isinstance(test.template, genes.DynamicTemplate):
                bp += len(test.template.seq(spacing=args.spacing))
            else:
                bp += len(test.template.seq())
        testsuites_descr.append('%s-%s[%d:%dbp]' % (
            name, testsuite.version, len(testsuite.tests), bp))
        tbp += bp
        tests += len(testsuite.tests)
    print('testsuites=' + ','.join(testsuites_descr))
    print('sum=%d tests,%dbp' % (tests, tbp))
    print('sys.prefix=' + sys.prefix)


# explorer {{{1

def explorer(args):

    testsuite_paths = discover_testsuites(args.testsuite_directory or [])

    import Tkinter as tk
    from kvarq.gui.explorer import DirectoryExplorer, JsonExplorer
    if os.path.isdir(args.explorable):
        DirectoryExplorer(args.explorable,
                testsuites={}, testsuite_paths=testsuite_paths)
    else:
        JsonExplorer(args.explorable,
                testsuites={}, testsuite_paths=testsuite_paths)
    tk.mainloop()


# parser {{{1

parser = argparse.ArgumentParser(description='''

        analyse .fastq file and report specific mutations in a .json file;
        additional output is displayed on stdout and log information is printed
        on stderr -- for additional see %s

    ''' % get_help_path())

subparsers = parser.add_subparsers(help='main command to execute')

parser.add_argument('-d', '--debug', action='store_true',
        help='output log information at a debug level')
parser.add_argument('-q', '--quiet', action='store_true',
        help='only output warnings/errors to stderr/log')
parser.add_argument('-x', '--excepthook', action='store_true',
        help='catch exception and launch debugger')
parser.add_argument('-l', '--log',
        help='append log to specified file (similar to redirecting stderr, but without progress bar)')
parser.add_argument('-t', '--testsuite-directory', action='append',
        help='specify a directory that contains subdirectories from which testsuites can be loaded; these are added to the pool of testsuites that can later be selected (scan, info) or that are autoloaded (illustrate, explore, update)')

# version {{{2
parser_version = subparsers.add_parser('version',
        help='show version info')
parser_version.set_defaults(func=version)

# scan {{{2
parser_scan = subparsers.add_parser('scan')
parser_scan.set_defaults(func=scan)

# output console
parser_scan.add_argument('-p', '--progress', action='store_true',
        help='shows progress bar on stdout while scanning')

# general
parser_scan.add_argument('-S', '--no-scan', action='store_true',
        help='instead of scanning the original file, the provided .json file from a previous scan result is used and the .json structures are re-calculated from the hit-list (see --hits); can only be done if version matches and same test suit is used (see --testsuites)')

# select testsuites
parser_scan.add_argument('-L', '--select-all', action='store_true',
        help='load all discovered testsuites')
parser_scan.add_argument('-l', '--select', action='append',
        help='this parameter works the same way as the environment variable KVARQ_TESTSUITES : it is either the name of a testsuite (such as "MTBC/phylo"), or the name of a group of testsuites (such as "MTBC") that is located in one of the auto-discovered places (kvarq root directory, user directory, current working directory) -- or the path to a python file containing a testsuite (such as "~/my_testsuite.py")')


# scan config
parser_scan.add_argument('-t', '--threads', action='store', type=int,
        default=default_config['threads'],
        help='number of threads for concurrent scanning (default: %d)' % default_config['threads'])
parser_scan.add_argument('-Q', '--quality', action='store', type=int,
        default=default_config['quality'],
        help='discard nucleotides with Q score inferior to this value (default=%d; i.e. p=0.05)' % default_config['quality'])
parser_scan.add_argument('-e', '--errors', action='store', type=int,
        default=default_config['errors'],
        help='maximal number of consecutive errors allowed when comparing base sequences (default=%d)' % default_config['errors'])
parser_scan.add_argument('-r', '--readlength', action='store', type=int,
        default=default_config['minimum readlength'],
        help='minimum read length (default=%d)' % default_config['minimum readlength'])
parser_scan.add_argument('-o', '--overlap', action='store', type=int,
        default=default_config['minimum overlap'],
        help='minimum read overlap (default=%d)' % default_config['minimum overlap'])
parser_scan.add_argument('-s', '--spacing', action='store', type=int,
        default=default_config['spacing'],
        help='default flank length on both sides of templates generated from genome (default=%d)' % default_config['spacing'])
#parser_scan.add_argument('-c', '--coverage', type=int,
#        default=default_config['stop median coverage'],
#        help='stop scanning when median coverage (including margins) is above specified value (default=%d) -- specify 0 to force scanning of entire file' % default_config['stop median coverage'])
parser_scan.add_argument('-1', '--no-reverse', action='store_true',
        help='do not scan for hits in reverse strand')
parser_scan.add_argument('-P', '--no-paired', action='store_true',
        help='ignore paired file -- by default, the file "strain_2.fastq[.gz]" is also read if "strain_1.fastq[.gz]" is specified on the command line')
parser_scan.add_argument('--variant', choices=Fastq.vendor_variants.keys(),
        help='specify .fastq variant manually in case heuristic determination fails')

# output
parser_scan.add_argument('-f', '--force', action='store_true',
        help='overwrite any existing .json file')
parser_scan.add_argument('-H', '--hits', action='store_true',
        help='saves all hits in .json file; this way scan result can be re-used without (see --no-scan)')
parser_scan.add_argument('-x', '--extract_hits',
        help='stores the fastq records of all hits in specified file')

# main arguments
parser_scan.add_argument('fastq',
        help='name of .fastq file to scan')
parser_scan.add_argument('json',
        help='name of .json file to where results are stored (or loaded, see -S)')

# update {{{2
parser_update = subparsers.add_parser('update',
        help='update (re-calculate) testsuites based on coverages saved in .json file; result is stored in same file')
parser_update.set_defaults(func=update)

parser_update.add_argument('json',
        help='name of .json file to update')
parser_update.add_argument('fastq', nargs='?',
        help='also re-calculate coverages with .fastq file specified (when .fastq file is not specified, coverages are taken from .json)')

# show {{{2
parser_show = subparsers.add_parser('show',
        help='show some information about a .fastq file')
parser_show.set_defaults(func=show)

parser_show.add_argument('-n', '--number', action='store', default=10000, type=int,
        help='number of records to read (applies to -Q)')
parser_show.add_argument('-p', '--points', action='store', default=10, type=int,
        help='number of points in file where to sample (spaced evenly; applies to -Q)')

parser_show.add_argument('-Q', '--quality', action='store', default=0, type=int,
        help='show histogram of readlengths with given quality cutoff (see also -n, -o)')
parser_show.add_argument('-i', '--info', action='store_true',
        help='output some information about FastQ file')

parser_show.add_argument('file',
        help='name of .fastq file to analyze')


# summarize {{{2
parser_summarize = subparsers.add_parser('summarize',
        help='reads several .json files as generated by the "scan" command and summarizes the results to standard output in .csv format')
parser_summarize.set_defaults(func=summarize)

parser_summarize.add_argument('json', nargs='+',
        help='input .json files')

# illustrate {{{2
parser_illustrate = subparsers.add_parser('illustrate',
        help='illustrate some information contained in a .json file (previously generated using the "scan" command)')
parser_illustrate.set_defaults(func=illustrate)

parser_illustrate.add_argument('-l', '--readlengths', action='store_true',
        help='show a histogram of readlengths')
parser_illustrate.add_argument('-c', '--coverage', action='store_true',
        help='show tests/coverages sorted by testsuite')

parser_illustrate.add_argument('-r', '--results', action='count',
        help='shows results of analyses')

parser_illustrate.add_argument('file',
        help='name of .json file to illustrate')


# gui {{{2
parser_gui = subparsers.add_parser('gui',
        help='start GUI')
parser_gui.set_defaults(func=gui)

# info {{{2
parser_info = subparsers.add_parser('info',
        help='show infos about kvarq')
parser_info.add_argument('-L', '--select-all', action='store_true',
        help='load all discovered testsuites')
parser_info.add_argument('-l', '--select', action='append',
        help='this parameter works the same way as the environment variable KVARQ_TESTSUITES : it is either the name of a testsuite (such as "MTBC/phylo"), or the name of a group of testsuites (such as "MTBC") that is located in one of the auto-discovered places (kvarq root directory, user directory, current working directory) or the path to a python file containing a testsuite')

parser_info.add_argument('-s', '--spacing', action='store', type=int,
        default=default_config['spacing'],
        help='default flank length on both sides of templates generated from genome (default=%d)' % default_config['spacing'])
parser_info.set_defaults(func=info)

# explorer {{{2
parser_explorer = subparsers.add_parser('explorer',
        help='launches the directory/json explorer')
parser_explorer.add_argument('explorable',
        help='directory/.json file to explore')
parser_explorer.set_defaults(func=explorer)


# __main__ {{{1

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)

    assert not (args.debug and args.quiet), \
            'make up your mind: debug OR normal OR quiet'

    if args.debug:
        set_debug()
    if args.quiet:
        set_warning()
    if args.log:
        appendlog(args.log)
    if args.excepthook:
        sys.excepthook = traceit

    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])

