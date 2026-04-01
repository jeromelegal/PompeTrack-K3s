import pytest
from PIL import Image, ImageDraw, ImageFont

from utils.pain_map_utils import *

# Tests for "point_in_poly"
def test_point_in_poly_inside():
    poly = [(0,0), (1,0), (1,1), (0,1)]
    assert point_in_poly(0.5, 0.5, poly)

# Tests for "point_in_poly" outside
def test_point_in_poly_outside():
    poly = [(0,0), (1,0), (1,1), (0,1)]
    assert not point_in_poly(1.5, 0.5, poly)

# Tests for "assign_zone"
def test_assign_zone_found():
    assert assign_zone(0.25, 0.05) == "Tête"

# Tests for "assign_zone" not found
def test_assign_zone_none():
    assert assign_zone(0.99, 0.99) is None

# Tests for "robust_text_size"
def test_robust_text_size_ok():
    img = Image.new("RGBA", (100,100))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    w, h = robust_text_size(draw, "abc", font)
    assert w > 0 and h > 0

# Tests for "load_font"
def test_load_font():
    assert load_font(12) is not None

# Tests for "get_image_content_bbox"
def test_get_image_content_bbox_detects_content():
    img = Image.new("RGBA", (50,50), (255,255,255,0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((10,10,30,30), fill=(0,0,0,255))
    assert get_image_content_bbox(img) == (10,10,31,31)

# Tests for "get_image_content_bbox" empty
def test_get_image_content_bbox_empty():
    img = Image.new("RGBA", (40,40), (255,255,255,0))
    assert get_image_content_bbox(img) == (0,0,40,40)

# Tests for "draw_polygons_overlay"
def test_draw_polygons_overlay():
    img = Image.new("RGBA", (100,200), (255,255,255,255))
    out = draw_polygons_overlay(img, {"Z": [(0,0),(1,0),(1,1),(0,1)]})
    assert isinstance(out, Image.Image)

# Tests for "draw_markers_on_image" empty
def test_draw_markers_on_image_none():
    assert draw_markers_on_image(None, [], []) is None

# Tests for "draw_markers_on_image"
def test_draw_markers_on_image_ok():
    img = Image.new("RGBA", (100,200), (255,255,255,255))
    markers = [{"x_norm":0.5, "y_norm":0.5}]
    out = draw_markers_on_image(img, markers, [])
    assert isinstance(out, Image.Image)
