
#from _util import debug_on

from kvarq import engine
from kvarq import genes
from kvarq import analyse
from kvarq.fastq import Fastq
from kvarq.analyse import Coverage
from kvarq.engine import Hit

import unittest
import os.path


MTBCpath = os.path.join(os.path.dirname(__file__), os.path.pardir, 'testsuites', 'MTBC')
phylo = genes.load_testsuite(os.path.join(MTBCpath, 'phylo.py'))
spoligo = genes.load_testsuite(os.path.join(MTBCpath, 'spoligo.py'))


class AnalyserTest(unittest.TestCase):

    ''' tests :py:mod:`kvarq.analyse` '''

    def setUp(self):
        self.fname = os.path.join(os.path.dirname(__file__), 'fastqs',
                'test_analyser.fastq')
        engine.config(nthreads=1, minoverlap=10)
        from kvarq.log import set_warning
        set_warning()


    def test_encoding(self):

        ''' saves/loads analyser to/from file '''

        analyser = analyse.Analyser()
        analyser.scan(Fastq(self.fname), {'phylo' : phylo})

        analyser.update_coverages()
        analyser.update_testsuites()
        results1 = analyser.results
        data = analyser.encode(hits=True)

        analyser = analyse.Analyser()
        analyser.decode({'phylo' : phylo}, data)
        analyser.update_coverages()
        analyser.update_testsuites()
        results2 = analyser.results

        assert results1 == results2


    def test_genes(self):

        ''' asserts specific genes are found in crafted .fastq file '''

        engine.config(nthreads=1, minoverlap=10, maxerrors=1)

        analyser = analyse.Analyser()
        analyser.scan(Fastq(self.fname), {'phylo': phylo, 'spoligo': spoligo})
        analyser.update_coverages()
        analyser.update_testsuites()

        assert analyser.results['spoligo'].split(' ')[0] == '400000000000001'
        l2_beijing = 'lineage 2/beijing sublineage'
        assert analyser.results['phylo'].startswith(l2_beijing)
        #coverages = analyser.results['coverages']
        #assert coverages[str(resistance.RRDR)]['outliers'] == [13]


    def test_coverage(self):
        #   AACCGGTT    : template
        #   ATCCGGTTTT  : hit1
        # AAAACCGGTT    : hit2
        #  AATCCGGTTA   : hit3
        seq = genes.Sequence('AACCGGTT')
        cov = Coverage(seq)

        # hit1
        cov.apply_hit(
                Hit(seq_nr=0, file_pos=-1, seq_pos=0, length=8, readlength=10),
                'ATCCGGTTTT', on_plus_strand=True)
        #print cov.serialize()
        assert cov.minf() == 1
        assert not cov.mixed()
        assert tuple(cov.coverage) == tuple( [1]*8 )
        assert 1 in cov.mutations
        cov.deserialize(cov.serialize())
        assert tuple(cov.coverage) == tuple( [1]*8 )
        assert 1 in cov.mutations

        # hit2
        cov.apply_hit(
                Hit(seq_nr=0, file_pos=-1, seq_pos=-2, length=8, readlength=10),
                'AACCGGTT', on_plus_strand=True)
        # hit3
        cov.apply_hit(
                Hit(seq_nr=0, file_pos=-1, seq_pos=-1, length=8, readlength=10),
                'ATCCGGTTA', on_plus_strand=True)

        assert cov.minf() > 0.65 and cov.minf() < 0.69
        assert cov.mixed()
        fs = cov.fractions_at(1)
        assert fs.keys()[0] == 'T'
        assert fs.values()[0] > 0.65
        assert fs.keys()[1] == 'A'
        assert fs.values()[1] < 0.35

if __name__ == '__main__': unittest.main()

