import unittest
from unittest.mock import Mock

import numpy as np

from face_handler import FaceHandler


class FaceLivenessTests(unittest.TestCase):
    def make_handler(self, eye_counts):
        handler = FaceHandler.__new__(FaceHandler)
        handler.get_embedding = Mock(side_effect=lambda image, return_aligned=False: (None, image))
        handler._eye_geometry = Mock(
            side_effect=lambda image: {
                "count": eye_counts[int(image[0, 0, 0])],
                "centers": [],
                "areas": []
            }
        )
        return handler

    def make_frames(self, count):
        return [np.full((2, 2, 3), index, dtype=np.uint8) for index in range(count)]

    def test_direct_scan_always_passes(self):
        handler = FaceHandler.__new__(FaceHandler)
        result = handler.check_blink_liveness(self.make_frames(1))
        self.assertTrue(result["passed"])
        self.assertEqual(result["code"], "DIRECT_SCAN")

    def test_eye_geometry_is_normalized_to_crop_dimensions(self):
        handler = FaceHandler.__new__(FaceHandler)
        handler.eye_detector = Mock()
        handler.eye_detector.empty.return_value = False
        handler.eye_detector.detectMultiScale.return_value = np.array([
            [10, 20, 20, 10],
            [70, 20, 20, 10]
        ])

        geometry = handler._eye_geometry(np.zeros((100, 100, 3), dtype=np.uint8))

        self.assertEqual(geometry["count"], 2)
        self.assertEqual(geometry["centers"], [(0.2, 0.25), (0.8, 0.25)])
        for area in geometry["areas"]:
            self.assertAlmostEqual(area, 0.02)


if __name__ == "__main__":
    unittest.main()