"""
Satellite Index Explorer - NDVI / NDWI / NDBI from satellite bands
======================================================================
Install once:
    pip install streamlit rasterio numpy matplotlib --break-system-packages

Run:
    streamlit run ndvi_app.py
"""

import streamlit as st
import numpy as np
import rasterio
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
import tempfile
import os
import io

st.set_page_config(page_title="Satellite Index Explorer", layout="wide", page_icon="🛰️")

# ---------------------------------------------------------------------------
# Dark theme + twinkling starfield background
# ---------------------------------------------------------------------------
STAR_CSS = """
<style>
.stApp {
    background: radial-gradient(ellipse at bottom, #0d1321 0%, #000000 100%);
}
#starfield {
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 0;
    pointer-events: none;
    overflow: hidden;
}
.star {
    position: absolute;
    background: white;
    border-radius: 50%;
    animation: twinkle ease-in-out infinite;
}
@keyframes twinkle {
    0%, 100% { opacity: 0.15; }
    50% { opacity: 1; }
}
h1, h2, h3, .stMarkdown, label, .stCaption, p {
    color: #e6edf3 !important;
}
.stRadio label, .stCheckbox label, .stSelectbox label {
    color: #e6edf3 !important;
}
[data-testid="stMetricValue"] {
    color: #7ee787 !important;
}
[data-testid="stSidebar"] {
    background-color: #0d1321;
}
/* Glassy panels for content blocks */
[data-testid="stFileUploader"],
[data-testid="stExpander"],
div[data-testid="stVerticalBlockBorderWrapper"],
.stAlert,
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.03) !important;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    padding: 10px;
}
[data-testid="stSidebar"] {
    background: rgba(13, 19, 33, 0.5) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}
</style>
"""

STAR_HTML = """
<div id="starfield">
{stars}
</div>
"""

import random
def make_stars(n=80):
    stars = []
    for _ in range(n):
        top = random.uniform(0, 100)
        left = random.uniform(0, 100)
        size = random.uniform(1, 2.5)
        duration = random.uniform(2, 6)
        delay = random.uniform(0, 5)
        stars.append(
            f'<div class="star" style="top:{top}%; left:{left}%; '
            f'width:{size}px; height:{size}px; '
            f'animation-duration:{duration}s; animation-delay:{delay}s;"></div>'
        )
    return "\n".join(stars)

st.markdown(STAR_CSS, unsafe_allow_html=True)
st.markdown(STAR_HTML.format(stars=make_stars()), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Live ISS Earth-view feed (small box, top-right, click to expand)
# Swap ISS_VIDEO_ID below for the currently-live NASA ISS video ID.
# Get it from: open the live NASA "Live High-Definition Views from ISS"
# video on YouTube, and copy the ID from its URL (youtube.com/watch?v=ID_HERE)
# ---------------------------------------------------------------------------
ISS_VIDEO_ID = "awQzjn72bI0"  # <-- replace with the current live video ID

ISS_WIDGET = f"""
<input type="checkbox" id="iss-toggle" class="iss-toggle-checkbox">
<label for="iss-toggle" class="iss-overlay"></label>
<label for="iss-toggle" class="iss-box">
  <iframe src="https://www.youtube.com/embed/{ISS_VIDEO_ID}?autoplay=1&mute=1"
          allow="autoplay; encrypted-media" frameborder="0"></iframe>
  <div class="iss-label">🔴 LIVE — ISS Earth View (click to expand)</div>
</label>
<style>
.iss-toggle-checkbox {{ display: none; }}
.iss-box {{
    position: fixed;
    top: 80px; right: 20px;
    width: 220px; height: 130px;
    z-index: 1000;
    cursor: pointer;
    border: 2px solid rgba(255,255,255,0.25);
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 4px 25px rgba(0,0,0,0.6);
    transition: all 0.35s ease;
}}
.iss-box iframe {{
    width: 100%; height: 100%;
    pointer-events: none;
}}
.iss-label {{
    position: absolute; bottom: 0; left: 0; right: 0;
    background: rgba(0,0,0,0.65);
    color: #e6edf3; font-size: 11px;
    padding: 3px 6px;
    text-align: center;
}}
.iss-overlay {{
    display: none;
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,0.85);
    z-index: 998;
}}
.iss-toggle-checkbox:checked ~ .iss-overlay {{ display: block; }}
.iss-toggle-checkbox:checked ~ .iss-box {{
    top: 8%; left: 12%; right: 12%; bottom: 8%;
    width: 76%; height: 84%;
    z-index: 999;
}}
.iss-toggle-checkbox:checked ~ .iss-box iframe {{ pointer-events: auto; }}
</style>
"""
st.markdown(ISS_WIDGET, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🛰️ Satellite Index Explorer")
st.write(
    "Upload satellite bands to generate **NDVI** (vegetation), **NDWI** (water), "
    "or **NDBI** (built-up area) maps."
)

with st.expander("📡 Don't have band files yet? Get them from these platforms"):
    l1, l2, l3 = st.columns(3)
    with l1:
        st.link_button("Bhoonidhi (NRSC/ISRO)", "https://bhoonidhi.nrsc.gov.in", use_container_width=True)
    with l2:
        st.link_button("Copernicus Data Space / SATVIEW", "https://dataspace.copernicus.eu", use_container_width=True)
    with l3:
        st.link_button("USGS EarthExplorer", "https://earthexplorer.usgs.gov", use_container_width=True)
    st.caption(
        "For NDVI: download Red (B04) + NIR (B08). "
        "For NDWI: download Green (B03) + NIR (B08). "
        "For NDBI: download SWIR (B11) + NIR (B08)."
    )

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Display Options")
show_histogram = st.sidebar.checkbox("Show histogram graph", value=False)

st.sidebar.header("Demo Data")
st.sidebar.caption("No real satellite files yet? Try these to see how the app works.")
demo_choice = st.sidebar.selectbox(
    "Demo scenario",
    ["None (use my own files)", "Single Date Demo", "Change Detection Demo"],
)

DEMO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_data")

if demo_choice == "Single Date Demo":
    st.session_state["demo_mode"] = "single"
elif demo_choice == "Change Detection Demo":
    st.session_state["demo_mode"] = "change"
else:
    st.session_state["demo_mode"] = None

mode = st.radio(
    "Mode", ["Single Date", "Compare Two Dates (Change Detection)"], horizontal=True
)

if st.session_state.get("demo_mode") == "single":
    mode = "Single Date"
elif st.session_state.get("demo_mode") == "change":
    mode = "Compare Two Dates (Change Detection)"

# ---------------------------------------------------------------------------
# Index definitions
# ---------------------------------------------------------------------------
INDEX_INFO = {
    "NDVI (Vegetation)": {
        "band_a_label": "Red band (B04)",
        "band_b_label": "NIR band (B08)",
        "demo_a": "demo_red_B04.tif",
        "demo_b": "demo_nir_B08.tif",
        "formula": lambda a, b: (b - a) / np.where((b + a) == 0, 1e-6, (b + a)),
        "cmap": ["#8B4513", "#D2B48C", "#F0E68C", "#9ACD32", "#228B22", "#006400"],
        "legend": "🟤 Brown = bare/built-up/water  🟡 Yellow = weak vegetation  🟢 Green = healthy vegetation",
        "verdict": [
            (0.1, "Bare soil / water / built-up dominated"),
            (0.3, "Sparse or stressed vegetation"),
            (0.6, "Moderate, healthy vegetation"),
            (999, "Dense, thriving vegetation"),
        ],
    },
    "NDWI (Water)": {
        "band_a_label": "Green band (B03)",
        "band_b_label": "NIR band (B08)",
        "demo_a": "demo_green_B03.tif",
        "demo_b": "demo_nir_B08.tif",
        "formula": lambda a, b: (a - b) / np.where((a + b) == 0, 1e-6, (a + b)),
        "cmap": ["#3b2f1e", "#8a7a5c", "#cfd9df", "#6ec6ff", "#1565c0", "#0d3b66"],
        "legend": "🟤 Brown = dry land  🔵 Blue = water present (darker blue = more water)",
        "verdict": [
            (-0.3, "No significant water detected"),
            (0.0, "Possibly moist soil or vegetation"),
            (0.3, "Some water presence"),
            (999, "Strong water presence"),
        ],
    },
    "NDBI (Built-up)": {
        "band_a_label": "SWIR band (B11)",
        "band_b_label": "NIR band (B08)",
        "demo_a": "demo_swir_B11.tif",
        "demo_b": "demo_nir_B08.tif",
        "formula": lambda a, b: (a - b) / np.where((a + b) == 0, 1e-6, (a + b)),
        "cmap": ["#00441b", "#78c679", "#f7f7c1", "#fdae61", "#d73027", "#7f0000"],
        "legend": "🟢 Green = vegetation/natural  🟡 Yellow = transitional  🔴 Red = built-up/urban",
        "verdict": [
            (-0.2, "Natural / vegetated area"),
            (0.0, "Mixed or transitional land"),
            (0.2, "Moderate built-up presence"),
            (999, "Dense built-up / urban area"),
        ],
    },
}

if mode == "Single Date":
    index_choice = st.selectbox("Which index?", list(INDEX_INFO.keys()))
    info = INDEX_INFO[index_choice]

    col1, col2 = st.columns(2)
    with col1:
        band_a_file = st.file_uploader(f"Upload {info['band_a_label']} — GeoTIFF", type=["tif", "tiff"])
    with col2:
        band_b_file = st.file_uploader(f"Upload {info['band_b_label']} — GeoTIFF", type=["tif", "tiff"])
else:
    st.caption("Change detection currently supports NDVI only.")
    st.markdown("**Older date**")
    c1, c2 = st.columns(2)
    with c1:
        red_old = st.file_uploader("Red band (old date)", type=["tif", "tiff"], key="red_old")
    with c2:
        nir_old = st.file_uploader("NIR band (old date)", type=["tif", "tiff"], key="nir_old")

    st.markdown("**Recent date**")
    c3, c4 = st.columns(2)
    with c3:
        red_new = st.file_uploader("Red band (new date)", type=["tif", "tiff"], key="red_new")
    with c4:
        nir_new = st.file_uploader("NIR band (new date)", type=["tif", "tiff"], key="nir_new")


def load_band_from_upload(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tif") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    with rasterio.open(tmp_path) as src:
        band = src.read(1).astype("float32")
    os.remove(tmp_path)
    return band


def load_band_from_path(path):
    with rasterio.open(path) as src:
        return src.read(1).astype("float32")


def fig_to_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    return buf


def compute_ndvi(red, nir):
    denom = (nir + red)
    denom[denom == 0] = 1e-6
    return np.clip((nir - red) / denom, -1, 1)


def get_verdict(value, thresholds):
    for limit, label in thresholds:
        if value < limit:
            return label
    return thresholds[-1][1]


if mode == "Single Date":
    using_demo = st.session_state.get("demo_mode") == "single"
    has_data = using_demo or (band_a_file is not None and band_b_file is not None)

    if has_data:
        with st.spinner(f"Computing {index_choice}..."):
            if using_demo:
                st.info(f"📍 Showing demo data for {index_choice} — a synthetic scene with forest, bare land, sparse vegetation, and water quadrants.")
                band_a = load_band_from_path(os.path.join(DEMO_DIR, info["demo_a"]))
                band_b = load_band_from_path(os.path.join(DEMO_DIR, info["demo_b"]))
            else:
                band_a = load_band_from_upload(band_a_file)
                band_b = load_band_from_upload(band_b_file)

            if band_a.shape != band_b.shape:
                st.error(
                    f"Band sizes don't match ({band_a.shape} vs {band_b.shape}). "
                    "Make sure both files are from the same scene and area."
                )
            else:
                index_map = np.clip(info["formula"](band_a, band_b), -1, 1)
                mean_val = float(np.nanmean(index_map))
                label = get_verdict(mean_val, info["verdict"])

                st.subheader("Result")
                m1, m2 = st.columns(2)
                m1.metric(f"Mean {index_choice.split()[0]}", f"{mean_val:.3f}")
                m2.metric("Verdict", label)

                cmap = LinearSegmentedColormap.from_list("idx", info["cmap"])

                fig, axes = plt.subplots(
                    1, 2 if show_histogram else 1,
                    figsize=(14, 6) if show_histogram else (8, 6)
                )
                if not show_histogram:
                    axes = [axes]

                im0 = axes[0].imshow(index_map, cmap=cmap, vmin=-1, vmax=1)
                axes[0].set_title(f"{index_choice.split()[0]} Map")
                axes[0].axis("off")
                fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04, label=index_choice.split()[0])

                if show_histogram:
                    axes[1].hist(index_map.flatten(), bins=50, color="#4682B4", edgecolor="black")
                    axes[1].axvline(mean_val, color="red", linestyle="--", label=f"Mean = {mean_val:.2f}")
                    axes[1].set_title("Distribution")
                    axes[1].set_xlabel(f"{index_choice.split()[0]} value")
                    axes[1].set_ylabel("Pixel count")
                    axes[1].legend()

                plt.tight_layout()
                st.pyplot(fig)
                st.download_button(
                    "📥 Download this map (PNG)",
                    data=fig_to_bytes(fig),
                    file_name=f"{index_choice.split()[0]}_map.png",
                    mime="image/png"
                )
                st.caption(info["legend"])
    else:
        st.info("Upload both band files above to see the result.")

else:
    using_demo = st.session_state.get("demo_mode") == "change"
    files_ready = using_demo or all(
        f is not None for f in [red_old, nir_old, red_new, nir_new]
    )
    if files_ready:
        with st.spinner("Computing change detection..."):
            if using_demo:
                st.info("📍 Showing demo data — a forest scene where a clearing appears and a settlement expands between the old and new dates.")
                r_old = load_band_from_path(os.path.join(DEMO_DIR, "demo_old_red_B04.tif"))
                n_old = load_band_from_path(os.path.join(DEMO_DIR, "demo_old_nir_B08.tif"))
                r_new = load_band_from_path(os.path.join(DEMO_DIR, "demo_new_red_B04.tif"))
                n_new = load_band_from_path(os.path.join(DEMO_DIR, "demo_new_nir_B08.tif"))
            else:
                r_old = load_band_from_upload(red_old)
                n_old = load_band_from_upload(nir_old)
                r_new = load_band_from_upload(red_new)
                n_new = load_band_from_upload(nir_new)

            shapes = {r_old.shape, n_old.shape, r_new.shape, n_new.shape}
            if len(shapes) > 1:
                st.error(f"All four bands must be the same size. Got shapes: {shapes}")
            else:
                ndvi_old = compute_ndvi(r_old, n_old)
                ndvi_new = compute_ndvi(r_new, n_new)
                change = ndvi_new - ndvi_old

                loss_pct = float(np.mean(change < -0.1) * 100)
                gain_pct = float(np.mean(change > 0.1) * 100)

                st.subheader("Result")
                m1, m2, m3 = st.columns(3)
                m1.metric("Mean NDVI (old)", f"{float(np.nanmean(ndvi_old)):.3f}")
                m2.metric("Mean NDVI (new)", f"{float(np.nanmean(ndvi_new)):.3f}")
                m3.metric("Vegetation lost", f"{loss_pct:.1f}% of area")

                veg_cmap = LinearSegmentedColormap.from_list(
                    "veg", ["#8B4513", "#D2B48C", "#F0E68C", "#9ACD32", "#228B22", "#006400"]
                )
                fig, axes = plt.subplots(1, 3, figsize=(20, 6))

                axes[0].imshow(ndvi_old, cmap=veg_cmap, vmin=-1, vmax=1)
                axes[0].set_title("NDVI - Old Date")
                axes[0].axis("off")

                axes[1].imshow(ndvi_new, cmap=veg_cmap, vmin=-1, vmax=1)
                axes[1].set_title("NDVI - New Date")
                axes[1].axis("off")

                change_cmap = LinearSegmentedColormap.from_list("change", ["#8B0000", "#FFFFFF", "#006400"])
                im2 = axes[2].imshow(change, cmap=change_cmap, vmin=-0.5, vmax=0.5)
                axes[2].set_title("Change (Red = Loss, Green = Gain)")
                axes[2].axis("off")
                fig.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04, label="NDVI change")

                plt.tight_layout()
                st.pyplot(fig)
                st.download_button(
                    "📥 Download this comparison (PNG)",
                    data=fig_to_bytes(fig),
                    file_name="ndvi_change_comparison.png",
                    mime="image/png"
                )

                st.caption(
                    f"🔴 Vegetation loss detected in **{loss_pct:.1f}%** of the area  |  "
                    f"🟢 Vegetation gain in **{gain_pct:.1f}%** of the area"
                )

                if show_histogram:
                    fig2, ax = plt.subplots(figsize=(10, 4))
                    ax.hist(change.flatten(), bins=50, color="#4682B4", edgecolor="black")
                    ax.axvline(0, color="black", linewidth=1)
                    ax.axvline(-0.1, color="#8B0000", linestyle="--", label="Loss threshold")
                    ax.axvline(0.1, color="#006400", linestyle="--", label="Gain threshold")
                    ax.set_title("Distribution of NDVI Change")
                    ax.set_xlabel("NDVI change (new − old)")
                    ax.set_ylabel("Pixel count")
                    ax.legend()
                    plt.tight_layout()
                    st.pyplot(fig2)
                    st.download_button(
                        "📥 Download this histogram (PNG)",
                        data=fig_to_bytes(fig2),
                        file_name="ndvi_change_histogram.png",
                        mime="image/png"
                    )
    else:
        st.info("Upload all four band files (old + new dates) above to see the change map.")
