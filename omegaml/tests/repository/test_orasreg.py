import shutil
import unittest
from pathlib import Path
from tempfile import mkdtemp

from omegaml.backends.repository import chdir
from omegaml.backends.repository.orasreg import OrasOciRegistry


class TestOCIRegistry(unittest.TestCase):

    def tearDown(self):
        shutil.rmtree(self.tmppath)

    @property
    def tmppath(self):
        return Path(mkdtemp())

    def test_init_variants(self):
        rpath = self.tmppath
        # -- no repo specified initially
        reg = OrasOciRegistry(rpath)
        with self.assertRaises(AssertionError):
            reg.create()
            reg.manifest()
        # -- requires repo specified on any operations
        reg.create(repo='fooimage:scratch')
        manifest = reg.manifest(repo='fooimage:scratch')
        self.assertIsInstance(manifest, dict)
        # -- with repo specified initially
        reg = OrasOciRegistry(rpath, 'fooimage2:scratch')
        manifest = reg.create()
        self.assertIsInstance(manifest, dict)

    def test_artifacts(self):
        """ Test that artifacts are empty initially """
        rpath = self.tmppath
        lpath = rpath / 'fooimage'
        shutil.rmtree(lpath) if lpath.exists() else None
        reg = OrasOciRegistry(rpath, 'fooimage:scratch')
        reg.create()
        artifacts = reg.artifacts()
        self.assertIsInstance(artifacts, list)
        self.assertEqual(len(artifacts), 0)

    def test_manifest(self):
        """ Test that a manifest is correctly created """
        rpath = self.tmppath
        reg = OrasOciRegistry(rpath, 'orasimage:test')
        reg.create()
        manifest = reg.manifest()
        self.assertIsInstance(manifest, dict)
        self.assertIn('schemaVersion', manifest)
        self.assertIn('layers', manifest)

    def test_create(self):
        """ Test that the registry is created """
        rpath = self.tmppath
        lpath = rpath / 'fooimage'
        shutil.rmtree(lpath) if lpath.exists() else None
        reg = OrasOciRegistry(rpath, 'fooimage:scratch')
        reg.create()
        self.assertEqual(reg.tags(), ['scratch'])

    def test_tags(self):
        """ Test that tags are correctly retrieved """
        rpath = self.tmppath
        reg = OrasOciRegistry(rpath, 'orasimage:test')
        with open(rpath / 'myfile.txt', 'w') as fout:
            fout.write('hello world\n')
        with chdir(rpath):
            reg.add('myfile.txt')
        tags = reg.tags()
        self.assertEqual(tags, ['test'])

    def test_add(self):
        """ Test that files are added to the registry """
        rpath = self.tmppath
        filespath = self._make_files(rpath)
        reg = OrasOciRegistry(rpath, 'orasimage:test')
        with chdir(filespath):
            artifact = reg.add('./files')
        self.assertIsInstance(artifact, dict)
        digest = reg.artifacts()[-1]['digest']
        self.assertIn(digest, reg.members)

    def test_add_multi(self):
        """ Test that multiple files are added to the registry """
        rpath = self.tmppath
        filespath = self._make_files(rpath)
        reg = OrasOciRegistry(rpath, 'orasimage:test')
        with chdir(filespath):  # change to /files so that we don't have a 'readme.txt' in the registry
            artifact = reg.add(['./files', './readme.txt'], types=['', 'text/plain'])
        self.assertIsInstance(artifact, dict)
        artifacts = reg.artifacts()
        self.assertEqual(artifacts[0]['mediaType'], 'application/vnd.oci.image.layer.v1.tar+gzip')
        self.assertEqual(artifacts[-1]['mediaType'], 'text/plain')

    def test_extract(self):
        rpath = self.tmppath
        filespath = self._make_files(rpath)
        reg = OrasOciRegistry(rpath, 'orasimage:test')
        with chdir(filespath):
            reg.add(['./files', './readme.txt'], types=['', 'text/plain'])
        artifacts = reg.artifacts()
        self.assertEqual(len(artifacts), 2)
        epath = rpath / 'orasimage-extract'
        shutil.rmtree(epath, ignore_errors=True)
        reg.extract(epath)
        self.assertTrue(epath.is_dir())
        self.assertTrue((epath / 'files').exists())
        self.assertTrue((epath / 'files' / 'myfile.txt').exists())
        self.assertTrue((epath / 'files' / 'otherfile.txt').exists())
        self.assertTrue((epath / 'readme.txt').exists())

    def _make_files(self, rpath):
        subdir = rpath / 'myfiles'
        shutil.rmtree(subdir, ignore_errors=True)
        subdir.mkdir()
        FILES = {
            subdir / 'files' / 'myfile.txt': ['hello world'],
            subdir / 'files' / 'otherfile.txt': ['hello universe'],
            subdir / 'readme.txt': ['readme first'],
        }
        for fn, lines in FILES.items():
            fn.parent.mkdir(exist_ok=True)
            with open(fn, 'w') as fout:
                fout.writelines(lines)
        return subdir
