import os
import io
import base64
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
FONT_REG      = os.path.join(BASE_DIR, "TheSeasons-Regular.ttf")
TEMPLATE_2    = os.path.join(BASE_DIR, "template_2.png")  # dark photo / centered
TEMPLATE_4    = os.path.join(BASE_DIR, "template_4.png")  # light photo / left-aligned teal

# ── Colors ───────────────────────────────────────────────────────────────────
WHITE = (255, 255, 255)
TEAL  = (15, 79, 107)

# ── State abbreviation map ───────────────────────────────────────────────────
STATE_ABBR = {
    'Alabama':'AL','Alaska':'AK','Arizona':'AZ','Arkansas':'AR','California':'CA',
    'Colorado':'CO','Connecticut':'CT','Delaware':'DE','Florida':'FL','Georgia':'GA',
    'Hawaii':'HI','Idaho':'ID','Illinois':'IL','Indiana':'IN','Iowa':'IA',
    'Kansas':'KS','Kentucky':'KY','Louisiana':'LA','Maine':'ME','Maryland':'MD',
    'Massachusetts':'MA','Michigan':'MI','Minnesota':'MN','Mississippi':'MS',
    'Missouri':'MO','Montana':'MT','Nebraska':'NE','Nevada':'NV','New Hampshire':'NH',
    'New Jersey':'NJ','New Mexico':'NM','New York':'NY','North Carolina':'NC',
    'North Dakota':'ND','Ohio':'OH','Oklahoma':'OK','Oregon':'OR','Pennsylvania':'PA',
    'Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD','Tennessee':'TN',
    'Texas':'TX','Utah':'UT','Vermont':'VT','Virginia':'VA','Washington':'WA',
    'West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY'
}

# ── Template 2 slot positions (dark photo, centered text) ────────────────────
T2 = {
    "type_top":     416,
    "type_bot":     472,
    "where_top":    876,
    "where_bot":    907,
    "where_val_x":  447,
    "budget_top":   1042,
    "budget_bot":   1073,
    "budget_val_x": 447,
    "type_color":   WHITE,
    "val_color":    WHITE,
    "align":        "center",
    "type_size_cap": 200,
}

# ── Template 4 slot positions (light photo, left-aligned teal) ───────────────
T4 = {
    "type_top":     340,
    "type_bot":     695,
    "where_top":    876,
    "where_bot":    907,
    "where_val_x":  447,
    "budget_top":   1042,
    "budget_bot":   1073,
    "budget_val_x": 447,
    "type_color":   TEAL,
    "val_color":    WHITE,
    "align":        "left",
    "type_left_x":  30,
    "type_size_cap": 160,
}

W_CANVAS = 1080

# ── Font helpers ─────────────────────────────────────────────────────────────
def get_font(size):
    return ImageFont.truetype(FONT_REG, size)

def measure(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]

def render_at(draw, text, font, x, y, color):
    bb = draw.textbbox((0, 0), text, font=font)
    draw.text((x - bb[0], y - bb[1]), text, font=font, fill=color)

# ── Text placement ────────────────────────────────────────────────────────────
def place_type(draw, lines, cfg):
    slot_top    = cfg["type_top"]
    slot_bot    = cfg["type_bot"]
    slot_h      = slot_bot - slot_top
    slot_center = (slot_top + slot_bot) / 2
    color       = cfg["type_color"]
    size_cap    = cfg.get("type_size_cap", 160)
    align       = cfg["align"]
    x_left      = cfg.get("type_left_x", 30)
    max_w       = (W_CANVAS - x_left - 30) if align == "left" else 920

    # Single-line types on T4 use full cap; multi-line Deborah-style cap at 90
    effective_cap = 90 if (align == "left" and len(lines) >= 3) else size_cap

    for size in range(effective_cap, 20, -1):
        f = get_font(size)
        widths, heights = [], []
        for line in lines:
            tw, th = measure(draw, line, f)
            widths.append(tw)
            heights.append(th)
        line_h  = max(heights)
        gap     = max(6, size // 10)
        total_h = line_h * len(lines) + gap * (len(lines) - 1)
        if max(widths) <= max_w and total_h <= slot_h:
            y_start = slot_center - total_h / 2
            for i, line in enumerate(lines):
                tw, _ = measure(draw, line, f)
                x = x_left if align == "left" else (W_CANVAS - tw) / 2
                render_at(draw, line, f, x, y_start + i * (line_h + gap), color)
            return

def place_inline(draw, text, slot_top, slot_bot, x_start, color):
    slot_center = (slot_top + slot_bot) / 2
    slot_h      = slot_bot - slot_top
    max_w       = W_CANVAS - x_start - 40
    for size in range(90, 10, -1):
        f = get_font(size)
        tw, th = measure(draw, text, f)
        if tw <= max_w and th <= slot_h + 6:
            render_at(draw, text, f, x_start, slot_center - th / 2, color)
            return

# ── Data helpers ──────────────────────────────────────────────────────────────
def build_type_lines(types_raw):
    types = [t.strip() for t in types_raw.split(',') if t.strip()]
    if len(types) == 1:
        return [types[0].upper()]
    elif len(types) == 2:
        return [f"{types[0].upper()} &", types[1].upper()]
    elif len(types) == 3:
        return [f"{types[0].upper()} &", f"{types[1].upper()} &", types[2].upper()]
    else:
        return ["BEAUTY"]

def build_state_text(draw, states_raw, max_width=580):
    states = [s.strip() for s in states_raw.split(',') if s.strip()]
    full   = ' · '.join(states)
    f      = get_font(28)
    tw, _  = measure(draw, full, f)
    if tw <= max_width:
        return full
    abbrs = [STATE_ABBR.get(s, s[:2].upper()) for s in states]
    return ' · '.join(abbrs)

# ── Core image generator ──────────────────────────────────────────────────────
def generate_image(template_num, business_types, states, budget):
    cfg      = T2 if template_num == 2 else T4
    tmpl_path = TEMPLATE_2 if template_num == 2 else TEMPLATE_4

    img  = Image.open(tmpl_path).copy()
    draw = ImageDraw.Draw(img)

    type_lines = build_type_lines(business_types)
    state_text = build_state_text(draw, states)

    place_type(draw, type_lines, cfg)
    place_inline(draw, state_text, cfg["where_top"], cfg["where_bot"],
                 cfg["where_val_x"], cfg["val_color"])
    place_inline(draw, budget, cfg["budget_top"], cfg["budget_bot"],
                 cfg["budget_val_x"], cfg["val_color"])

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/generate", methods=["POST"])
def generate():
    """
    Expected JSON body:
    {
        "template":   2,                          // 2 or 4
        "types":      "Salons, Spas",             // comma-separated
        "states":     "Pennsylvania, Florida",    // comma-separated
        "budget":     "Under $100,000"
    }
    Returns JSON:
    {
        "image_b64": "<base64 PNG string>"
    }
    """
    data = request.get_json(force=True)

    template_num   = int(data.get("template", 2))
    business_types = data.get("types", "Beauty")
    states         = data.get("states", "")
    budget         = data.get("budget", "")

    if not states or not budget:
        return jsonify({"error": "states and budget are required"}), 400

    try:
        buf        = generate_image(template_num, business_types, states, budget)
        img_b64    = base64.b64encode(buf.read()).decode("utf-8")
        return jsonify({"image_b64": img_b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
