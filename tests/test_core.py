import numpy as np

from morphometry.pipeline import otsu_value, parse_condition, segment_classical


def test_otsu_separates_bimodal_image():
    image = np.zeros((64, 64), dtype=float)
    image[:, 32:] = 1.0
    threshold = otsu_value(image)
    assert 0.0 <= threshold < 1.0


def test_segmentation_returns_shapes():
    yy, xx = np.ogrid[:128, :128]
    image = np.zeros((128, 128), dtype=float)
    image[(xx - 40) ** 2 + (yy - 60) ** 2 < 18 ** 2] = 1
    image[(xx - 85) ** 2 + (yy - 65) ** 2 < 15 ** 2] = 0.9
    mask, labels, _ = segment_classical(image)
    assert mask.shape == image.shape
    assert labels.max() >= 2


def test_condition_parser_keeps_unsieved_distinct():
    meta = parse_condition("Supplementary Figure S7/unsieved SP coating_PUR_SEM.tif", is_image=True)
    assert meta["sieving"] == "unsieved"
    assert meta["primer"] == "PUR"
