import unittest

from omegaml.defaults import update_from_obj


class MiscTests(unittest.TestCase):
    def test_update_obj_dict(self):
        # source and target are dicts, scalar values
        source = {
            'FOO': 'bar'
        }
        target = {
            'FOO': 'baz'
        }
        update_from_obj(source, target)
        self.assertEqual(target['FOO'], 'bar')
        # source is dict, target is dict, dict values replace
        source = {
            'FOO': dict(sub='bar')
        }
        target = {
            'FOO': dict(sub='baz')
        }
        update_from_obj(source, target)
        self.assertEqual(target['FOO'], dict(sub='bar'))
        # source is dict, target is dict, dict values merge
        source = {
            'FOO': dict(othersub='bar')
        }
        target = {
            'FOO': dict(sub='baz')
        }
        update_from_obj(source, target)
        self.assertEqual(target['FOO'], dict(sub='baz', othersub='bar'))
        # source is dict, target is dict, dict values delete
        source = {
            'FOO': dict(othersub='bar', sub='__delete__')
        }
        target = {
            'FOO': dict(sub='baz')
        }
        update_from_obj(source, target)
        self.assertEqual(target['FOO'], dict(othersub='bar'))

    def test_update_obj_attrs(self):
        # source is dict, target is attributes, scalar values
        source = {
            'FOO': 'bar'
        }
        target = MiscTests
        target.FOO = 'baz'
        update_from_obj(source, target)
        self.assertEqual(target.FOO, 'bar')
        # source is dict, target is obj, merge
        source = {
            'FOO': dict(othersub='bar')
        }
        target.FOO = dict(sub='baz')
        update_from_obj(source, target)
        self.assertEqual(target.FOO, dict(sub='baz', othersub='bar'))
        # source is dict, target is obj, merge delete
        source = {
            'FOO': dict(othersub='bar', sub='__delete__')
        }
        target.FOO = dict(sub='baz')
        update_from_obj(source, target)
        self.assertEqual(target.FOO, dict(othersub='bar'))



if __name__ == '__main__':
    unittest.main()
