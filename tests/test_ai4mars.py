"""X1 geometry on a synthetic grid (no AI4MARS or terrain number)."""
import numpy as np

from pipeline.ai4mars_check import sector_mask


def test_sector_points_the_right_way_and_circle_is_full():
    ext, res = [-100.0, -100.0, 100.0, 100.0], 2.0
    rr, cc = sector_mask((100, 100), ext, res, 0.0, 0.0, 315.0, 45.0)          # looking north, 90 deg wide
    y = ext[3] - (rr + .5) * res; x = ext[0] + (cc + .5) * res
    assert (y > 0).all() and (np.abs(x) <= y + 1e-9).all() and (np.hypot(x, y) <= 30).all()
    rr2, cc2 = sector_mask((100, 100), ext, res, 0.0, 0.0, None, None)
    assert abs(len(rr2) - np.pi * 15 ** 2) / (np.pi * 15 ** 2) < 0.05 and abs(len(rr2) / len(rr) - 4) < 0.3
    rr3, _ = sector_mask((100, 100), ext, res, 0.0, 0.0, 80.0, 100.0)             # narrow, looking east
    x3 = ext[0] + (_ + .5) * res
    assert (x3 > 0).all()
