import unittest
from prepare_dataset import detection_label


class DatasetTests(unittest.TestCase):
    def test_polygon_becomes_enclosing_box(self):
        label, converted = detection_label('0 0.2 0.3 0.8 0.3 0.8 0.9 0.2 0.9')
        self.assertTrue(converted)
        self.assertEqual([float(x) for x in label.split()[1:]], [0.5, 0.6, 0.6, 0.6])

    def test_box_stays_box(self):
        label, converted = detection_label('1 0.5 0.5 0.2 0.4')
        self.assertFalse(converted)
        self.assertEqual(int(label.split()[0]), 1)

    def test_bad_labels_rejected(self):
        for line in ['2 0.5 0.5 0.1 0.1', '0 nan 0.5 0.1 0.1', '1 0.5 0.5 0 0', '0 0.2 0.3 0.4']:
            with self.assertRaises(ValueError):
                detection_label(line)
