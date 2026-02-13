from PIL import Image, ImageDraw, ImageFont

FONT_SIZE = 14
MARKER_RADIUS_PX = 8
LABEL_OFFSET_PX = 10

POLYGONS = {
    # Face avant (x ≈ 0.0 à 0.5)
    "Tête": [(0.19, 0.00), (0.31, 0.00), (0.31, 0.12), (0.19, 0.12)],
    "Cou": [(0.21, 0.125), (0.29, 0.125), (0.29, 0.16), (0.21, 0.16)],
    "Épaule droite": [(0.08, 0.16), (0.18, 0.15), (0.18, 0.21), (0.08, 0.21)],
    "Épaule gauche": [(0.32, 0.15), (0.39, 0.16), (0.40, 0.21), (0.32, 0.21)],
    "Poitrine": [(0.18, 0.16), (0.32, 0.16), (0.33, 0.30), (0.16, 0.30)],
    "Abdomen": [(0.16, 0.30), (0.335, 0.30), (0.345, 0.44), (0.15, 0.44)],
    "Bras droit (sup)": [(0.10, 0.215), (0.15, 0.215), (0.15, 0.35), (0.08, 0.35)],
    "Bras gauche (sup)": [(0.34, 0.215), (0.4, 0.215), (0.41, 0.35), (0.34, 0.35)],
    "Avant-bras droit": [(0.07, 0.35), (0.16, 0.35), (0.13, 0.47), (0.05, 0.47)],
    "Avant-bras gauche": [(0.34, 0.35), (0.42, 0.35), (0.45, 0.47), (0.36, 0.47)],
    "Main droite": [(0.00, 0.47), (0.11, 0.47), (0.11, 0.57), (0.00, 0.57)],
    "Main gauche": [(0.39, 0.47), (0.49, 0.47), (0.49, 0.57), (0.39, 0.57)],
    "Hanche droite": [(0.14, 0.44), (0.24, 0.44), (0.24, 0.52), (0.13, 0.52)],
    "Hanche gauche": [(0.25, 0.44), (0.35, 0.44), (0.36, 0.52), (0.25, 0.52)],
    "Cuisse droite": [(0.13, 0.52), (0.24, 0.55), (0.23, 0.68), (0.13, 0.68)],
    "Cuisse gauche": [(0.255, 0.55), (0.365, 0.52), (0.365, 0.68), (0.265, 0.68)],
    "Genou droit": [(0.13, 0.68), (0.23, 0.68), (0.23, 0.74), (0.13, 0.74)],
    "Genou gauche": [(0.265, 0.68), (0.365, 0.68), (0.365, 0.74), (0.265, 0.74)],
    "Tibia droit": [(0.13, 0.745), (0.22, 0.745), (0.19, 0.89), (0.13, 0.89)],
    "Tibia gauche": [(0.275, 0.745), (0.37, 0.745), (0.37, 0.89), (0.305, 0.89)],
    "Pied droit": [(0.14, 0.895), (0.18, 0.895), (0.19, 1.0), (0.12, 1.0)],
    "Pied gauche": [(0.305, 0.895), (0.36, 0.895), (0.37, 1.0), (0.31, 1.0)],

    # Face arrière (x ≈ 0.5 à 1.0)
    "Tête (arrière)": [(0.69, 0.00), (0.81, 0.00), (0.81, 0.12), (0.69, 0.12)],
    "Haut du dos": [(0.68, 0.17), (0.825, 0.17), (0.845, 0.37), (0.66, 0.37)],
    "Bas du dos": [(0.66, 0.37), (0.845, 0.37), (0.855, 0.47), (0.64, 0.47)],
    "Cervicales": [(0.715, 0.125), (0.795, 0.125), (0.83, 0.17), (0.68, 0.17)],
    "Épaule gauche (arrière)": [(0.62, 0.16), (0.68, 0.16), (0.67, 0.215), (0.61, 0.215)],
    "Épaule droite (arrière)": [(0.83, 0.16), (0.88, 0.16), (0.90, 0.215), (0.83, 0.215)],
    "Bras gauche (arrière)": [(0.605, 0.215), (0.655, 0.215), (0.655, 0.35), (0.585, 0.35)],
    "Bras droit (arrière)": [(0.845, 0.215), (0.905, 0.215), (0.915, 0.35), (0.845, 0.35)],
    "Avant-bras gauche (arrière)": [(0.575, 0.35), (0.665, 0.35), (0.635, 0.47), (0.555, 0.47)],
    "Avant-bras droit (arrière)": [(0.845, 0.35), (0.925, 0.35), (0.955, 0.47), (0.865, 0.47)],
    "Main gauche (arrière)": [(0.505, 0.47), (0.615, 0.47), (0.615, 0.57), (0.505, 0.57)],
    "Main droite (arrière)": [(0.895, 0.47), (0.995, 0.47), (0.995, 0.57), (0.895, 0.57)],
    "Fesse gauche": [(0.63, 0.47), (0.75, 0.47), (0.75, 0.55), (0.63, 0.55)],
    "Fesse droite": [(0.75, 0.47), (0.88, 0.47), (0.88, 0.55), (0.75, 0.55)],
    "Cuisse gauche (arrière)": [(0.63, 0.55), (0.74, 0.55), (0.73, 0.70), (0.64, 0.70)],
    "Cuisse droite (arrière)": [(0.76, 0.55), (0.875, 0.55), (0.865, 0.70), (0.77, 0.70)],
    "Mollet gauche": [(0.62, 0.72), (0.71, 0.72), (0.70, 0.89), (0.64, 0.89)],
    "Mollet droit": [(0.78, 0.72), (0.88, 0.72), (0.87, 0.89), (0.805, 0.89)],
    "Pied gauche (dessous)": [(0.645, 0.895), (0.685, 0.895), (0.695, 1.0), (0.625, 1.0)],
    "Pied droit (dessous)": [(0.81, 0.895), (0.865, 0.895), (0.875, 1.0), (0.815, 1.0)],
}

# -------------------------------------------------
# Geometry helpers
# -------------------------------------------------

def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def assign_zone(x_norm, y_norm):
    for zone, poly in POLYGONS.items():
        if point_in_poly(x_norm, y_norm, poly):
            return zone
    return None

# -------------------------------------------------
# Text / font helpers
# -------------------------------------------------

def robust_text_size(draw, text, font):
    try:
        if hasattr(draw, "textbbox"):
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        pass

    try:
        if font and hasattr(font, "getsize"):
            return font.getsize(text)
    except Exception:
        pass

    try:
        return draw.textsize(text, font=font)
    except Exception:
        pass

    return max(10, len(text) * 7), max(10, int(FONT_SIZE * 0.9))


def load_font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except Exception:
        try:
            return ImageFont.load_default()
        except Exception:
            return None

# -------------------------------------------------
# Image helpers
# -------------------------------------------------

def get_image_content_bbox(pil_img, alpha_threshold=10):
    img = pil_img.convert("RGBA")
    w, h = img.size
    pix = img.load()

    mask = Image.new("L", (w, h), 0)
    mpx = mask.load()

    for y in range(h):
        for x in range(w):
            r, g, b, a = pix[x, y]
            if a > alpha_threshold and not (r > 250 and g > 250 and b > 250):
                mpx[x, y] = 255

    bbox = mask.getbbox()
    return bbox if bbox else (0, 0, w, h)


def norm_to_pixel_in_bbox(x_norm, y_norm, bbox):
    left, top, right, bottom = bbox
    bw = right - left
    bh = bottom - top
    return (
        int(left + x_norm * bw),
        int(top + y_norm * bh),
    )


def draw_polygons_overlay(img, polygons, font=None):
    img2 = img.copy().convert("RGBA")
    draw = ImageDraw.Draw(img2)
    bbox = get_image_content_bbox(img2)

    for name, poly in polygons.items():
        pts = [norm_to_pixel_in_bbox(x, y, bbox) for x, y in poly]
        draw.line(pts + [pts[0]], width=2, fill=(0, 0, 255, 180))

        try:
            tw, th = robust_text_size(draw, name, font)
            x, y = pts[0]
            draw.rectangle((x - 2, y - 2, x + tw + 2, y + th + 2), fill=(255, 255, 255, 200))
            draw.text((x, y), name, fill=(0, 0, 0, 255), font=font)
        except Exception:
            pass

    return img2


def draw_markers_on_image(pil_img, confirmed_markers, pending_markers, font=None):
    if pil_img is None:
        return None

    img = pil_img.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)
    bbox = get_image_content_bbox(img)

    for m in confirmed_markers:
        x, y = norm_to_pixel_in_bbox(m["x_norm"], m["y_norm"], bbox)
        draw.ellipse(
            (x - MARKER_RADIUS_PX, y - MARKER_RADIUS_PX,
             x + MARKER_RADIUS_PX, y + MARKER_RADIUS_PX),
            fill=(255, 0, 0, 200),
            outline=(0, 0, 0),
        )

    for m in pending_markers:
        x, y = norm_to_pixel_in_bbox(m["x_norm"], m["y_norm"], bbox)
        draw.ellipse(
            (x - MARKER_RADIUS_PX, y - MARKER_RADIUS_PX,
             x + MARKER_RADIUS_PX, y + MARKER_RADIUS_PX),
            fill=(255, 100, 100, 200),
            outline=(0, 0, 0),
        )

    return img
