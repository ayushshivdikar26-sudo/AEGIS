"""
Generate high-resolution system diagrams and charts for the AEGIS academic report.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

out_dir = Path("report_figures")
out_dir.mkdir(exist_ok=True)

# -------------------------------------------------------------
# 1. Architecture Diagram (Figure 3.1)
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6.2), dpi=300)
ax.set_xlim(0, 10)
ax.set_ylim(0, 6.2)
ax.axis("off")

c_ui = "#1e293b"
c_api = "#0f172a"
c_core = "#1e1b4b"
c_db = "#064e3b"
c_ai = "#4c1d95"

def draw_box(x, y, w, h, title, items, color, border_color="#38bdf8"):
    rect = patches.FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.15",
        facecolor=color, edgecolor=border_color, linewidth=1.5
    )
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h - 0.25, title, ha="center", va="top", color="#f8fafc",
            fontsize=10.5, fontweight="bold", fontfamily="DejaVu Sans")
    for i, it in enumerate(items):
        ax.text(x + 0.18, y + h - 0.58 - i * 0.23, f"- {it}", ha="left", va="top",
                color="#cbd5e1", fontsize=8.5, fontfamily="DejaVu Sans")

draw_box(0.5, 4.5, 9.0, 1.45, "1. Presentation Tier (Vanilla ES2022 / Michroma / CSS Design Tokens)", [
    "Scrubbable Hero with Animated Canvas WebThreads (threads.js)",
    "Real-Time Dashboard with SVG Needle Speedometer & Sample Badges",
    "Interactive Manifest Import Modal & Client Preflight Validation (validate_manifest.js)",
    "Plain-Language UX Suite: 'How to Read AEGIS' Guide Drawer & Plain-Language Version Diffs"
], c_ui, border_color="#00e5ff")

draw_box(0.5, 2.6, 4.3, 1.6, "2. API & Gateway Tier (FastAPI)", [
    "Asymmetric Supabase JWKS JWT Auth",
    "Sliding-Window Redis Rate Limiter",
    "Multipart Manifest Ingestion Stream",
    "Strict CSP (default-src 'self')"
], c_api, border_color="#38bdf8")

draw_box(5.2, 2.6, 4.3, 1.6, "3. AI Overview & Fallback Subsystem", [
    "Groq API Service (Meta Llama-3.1-8b-instant)",
    "Prompt Injection Hardening & 25s Timeout",
    "Local SQLite ai_overviews Offline Caching",
    "Deterministic Offline Fallback Synthesizer"
], c_ai, border_color="#c084fc")

draw_box(0.5, 0.3, 4.3, 2.0, "4. Deterministic Core Analysis Engine", [
    "Manifest Parser (NFC Normalization & Bidi Strip)",
    "Host Match Pattern & PSL Scope Tiering (covers)",
    "Risk Scoring Engine (Normalized Blend & Floors)",
    "Justification Engine (15 Categories, Rules R1-R6)",
    "Chronological Creep & Host Broadening Detector",
    "Chrome Extension i18n Placeholder Resolver"
], c_core, border_color="#818cf8")

draw_box(5.2, 0.3, 4.3, 2.0, "5. Persistence & Data Infrastructure", [
    "Supabase Cloud PostgreSQL 15 (Forced RLS)",
    "Multi-Tenant User Isolation ((auth.uid() = user_id))",
    "Immutable Version Snapshots & Relations",
    "Local SQLite Hybrid Cache (Backend/data/aegis.db)",
    "Decoupled Chrome/Edge Local Browser Scanner"
], c_db, border_color="#34d399")

# Connectors
ax.annotate("", xy=(5.0, 4.5), xytext=(5.0, 4.2),
            arrowprops=dict(arrowstyle="<->", color="#00e5ff", lw=1.5))
ax.annotate("", xy=(2.65, 2.6), xytext=(2.65, 2.3),
            arrowprops=dict(arrowstyle="<->", color="#38bdf8", lw=1.5))
ax.annotate("", xy=(7.35, 2.6), xytext=(7.35, 2.3),
            arrowprops=dict(arrowstyle="<->", color="#c084fc", lw=1.5))
ax.annotate("", xy=(4.8, 3.4), xytext=(5.2, 3.4),
            arrowprops=dict(arrowstyle="<->", color="#94a3b8", lw=1.2, ls="--"))

plt.tight_layout()
plt.savefig(out_dir / "fig_3_1_architecture.png", bbox_inches="tight", facecolor="#090d16")
plt.close()
print("Saved fig_3_1_architecture.png")


# -------------------------------------------------------------
# 2. End-to-End Analysis Pipeline (Figure 4.1)
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
ax.set_xlim(0, 10)
ax.set_ylim(0, 5.5)
ax.axis("off")

steps = [
    ("Step 1: Manifest Ingestion", "Upload modal / local scan / JSON paste;\nstrict size (<1MB) & recursion (<32) limits", 0.5, 4.2, 2.6, 1.0, "#1e293b", "#38bdf8"),
    ("Step 2: Preprocessing & i18n", "Unicode NFC normalization; Bidi strip;\nresolve __MSG_...__ localization strings", 3.7, 4.2, 2.6, 1.0, "#1e293b", "#38bdf8"),
    ("Step 3: Partitioning & Scope", "Partition API tokens & PSL host tiers;\nevaluate match pattern coverage (covers)", 6.9, 4.2, 2.6, 1.0, "#1e1b4b", "#818cf8"),
    ("Step 4: Deterministic Scoring", "Normalized set scores: R_api & R_host;\nDanger floors (70 / 40); exact breakdown", 0.5, 1.8, 2.6, 1.0, "#1e1b4b", "#818cf8"),
    ("Step 5: Justification Check", "Lexical categorization (15 categories);\nEvaluate rules R1-R6; Excess Score (J)", 3.7, 1.8, 2.6, 1.0, "#064e3b", "#34d399"),
    ("Step 6: Version Creep Audit", "Group Added/Removed/Retained;\nHost broadening (PSL tier delta); Verdict", 6.9, 1.8, 2.6, 1.0, "#831843", "#f43f5e"),
    ("Step 7: AI Overview & Local Cache", "Groq Llama-3.1 generation with prompt defense;\noffline deterministic fallback; SQLite cache", 2.1, 0.2, 5.8, 0.9, "#4c1d95", "#c084fc")
]

for title, desc, x, y, w, h, bg, border in steps:
    rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.12",
                                  facecolor=bg, edgecolor=border, linewidth=1.5)
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h - 0.2, title, ha="center", va="top", color="#f8fafc",
            fontsize=8.5, fontweight="bold", fontfamily="DejaVu Sans")
    ax.text(x + w / 2, y + h - 0.48, desc, ha="center", va="top", color="#cbd5e1",
            fontsize=7.2, fontfamily="DejaVu Sans")

# Connectors
ax.annotate("", xy=(3.7, 4.7), xytext=(3.1, 4.7), arrowprops=dict(arrowstyle="->", color="#38bdf8", lw=1.5))
ax.annotate("", xy=(6.9, 4.7), xytext=(6.3, 4.7), arrowprops=dict(arrowstyle="->", color="#38bdf8", lw=1.5))
ax.annotate("", xy=(8.2, 2.8), xytext=(8.2, 4.2), arrowprops=dict(arrowstyle="->", color="#818cf8", lw=1.5))
ax.annotate("", xy=(6.9, 2.3), xytext=(6.3, 2.3), arrowprops=dict(arrowstyle="<-", color="#818cf8", lw=1.5))
ax.annotate("", xy=(3.7, 2.3), xytext=(3.1, 2.3), arrowprops=dict(arrowstyle="<-", color="#34d399", lw=1.5))
ax.annotate("", xy=(5.0, 1.1), xytext=(5.0, 1.8), arrowprops=dict(arrowstyle="->", color="#f43f5e", lw=1.5))

plt.tight_layout()
plt.savefig(out_dir / "fig_4_1_pipeline.png", bbox_inches="tight", facecolor="#090d16")
plt.close()
print("Saved fig_4_1_pipeline.png")


# -------------------------------------------------------------
# 3. Hero & Preloading Workflow (Figure 4.2)
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 4.5), dpi=300)
ax.set_xlim(0, 10)
ax.set_ylim(0, 4.5)
ax.axis("off")

p1 = patches.FancyBboxPatch((0.5, 2.4), 4.2, 1.7, boxstyle="round,pad=0.08,rounding_size=0.12",
                            facecolor="#0f172a", edgecolor="#00e5ff", linewidth=1.5)
ax.add_patch(p1)
ax.text(2.6, 3.8, "Client-Side User Experience", ha="center", va="top", color="#00e5ff",
        fontsize=9.5, fontweight="bold", fontfamily="DejaVu Sans")
ax.text(0.7, 3.4, "1. User lands on Scrubbable Hero Section", ha="left", va="top", color="#f8fafc", fontsize=8)
ax.text(0.7, 3.1, "2. Background Canvas WebThreads animates", ha="left", va="top", color="#cbd5e1", fontsize=8)
ax.text(0.7, 2.8, "3. User reads intro badges & scrolls down (2-3s)", ha="left", va="top", color="#cbd5e1", fontsize=8)

p2 = patches.FancyBboxPatch((5.3, 2.4), 4.2, 1.7, boxstyle="round,pad=0.08,rounding_size=0.12",
                            facecolor="#064e3b", edgecolor="#34d399", linewidth=1.5)
ax.add_patch(p2)
ax.text(7.4, 3.8, "Asynchronous Background Preload", ha="center", va="top", color="#34d399",
        fontsize=9.5, fontweight="bold", fontfamily="DejaVu Sans")
ax.text(5.5, 3.4, "1. Frontend fires getExtensions() on mount", ha="left", va="top", color="#f8fafc", fontsize=8)
ax.text(5.5, 3.1, "2. Single-join PostgREST query executes", ha="left", va="top", color="#cbd5e1", fontsize=8)
ax.text(5.5, 2.8, "3. Snapshots & permissions cached in memory", ha="left", va="top", color="#cbd5e1", fontsize=8)

p3 = patches.FancyBboxPatch((1.5, 0.4), 7.0, 1.4, boxstyle="round,pad=0.08,rounding_size=0.12",
                            facecolor="#1e1b4b", edgecolor="#818cf8", linewidth=1.5)
ax.add_patch(p3)
ax.text(5.0, 1.5, "Seamless Zero-Latency Dashboard Activation", ha="center", va="top", color="#818cf8",
        fontsize=10, fontweight="bold", fontfamily="DejaVu Sans")
ax.text(5.0, 1.15, "When user scrolls into #app-dashboard, all extension cards, risk speedometer gauges,\nand permission breakdowns render immediately with 0ms perceived latency (no loading spinners).",
        ha="center", va="top", color="#e2e8f0", fontsize=8)

ax.annotate("", xy=(3.5, 1.8), xytext=(2.6, 2.4), arrowprops=dict(arrowstyle="->", color="#00e5ff", lw=1.5))
ax.annotate("", xy=(6.5, 1.8), xytext=(7.4, 2.4), arrowprops=dict(arrowstyle="->", color="#34d399", lw=1.5))

plt.tight_layout()
plt.savefig(out_dir / "fig_4_2_preloading.png", bbox_inches="tight", facecolor="#090d16")
plt.close()
print("Saved fig_4_2_preloading.png")


# -------------------------------------------------------------
# 4. Results & Coverage Chart (Figure 6.1)
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.2), dpi=300)
modules = [
    "Risk Scoring",
    "Core Models",
    "Host Patterns",
    "Version Creep",
    "Manifest Parser",
    "Permission Rules",
    "Import Preflight"
]
coverage = [100, 100, 95, 95, 94, 94, 100]
colors = ["#00e5ff", "#00e5ff", "#38bdf8", "#38bdf8", "#818cf8", "#818cf8", "#34d399"]

bars = ax.barh(modules, coverage, color=colors, height=0.6)
ax.set_xlim(0, 115)
ax.set_xlabel("Code Coverage Percentage (%)", color="#f8fafc", fontsize=9, fontweight="bold")
ax.set_title("AEGIS Deterministic Subsystem Code Coverage (Pytest / pytest-cov)", color="#f8fafc", fontsize=10.5, fontweight="bold", pad=12)
ax.tick_params(colors="#cbd5e1", labelsize=8.5)
ax.set_facecolor("#0f172a")
fig.patch.set_facecolor("#090d16")

for bar in bars:
    w = bar.get_width()
    ax.text(w + 2, bar.get_y() + bar.get_height() / 2, f"{int(w)}%",
            ha="left", va="center", color="#f8fafc", fontsize=8.5, fontweight="bold")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["bottom"].set_color("#334155")
ax.spines["left"].set_color("#334155")

plt.tight_layout()
plt.savefig(out_dir / "fig_6_1_coverage.png", bbox_inches="tight", facecolor="#090d16")
plt.close()
print("Saved fig_6_1_coverage.png")
