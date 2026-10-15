"""Generate a compact post-match PDF from an FPSights analysis result."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_pdf_report(result: dict[str, Any], output_path: Path) -> Path:
    """Write one readable MVP report and return its path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    video = result.get("video") or {}
    analytics = result.get("analytics") or {}
    crosshair = analytics.get("crosshair") or {}
    aim = analytics.get("aim_reaction") or {}
    positioning = analytics.get("positioning") or {}
    detection = result.get("detection") or {}
    segmentation = result.get("segmentation") or {}

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="FPSightsTitle",
            parent=styles["Title"],
            textColor=colors.HexColor("#ff375f"),
            alignment=TA_CENTER,
            spaceAfter=5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="FPSightsSection",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#1c3348"),
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="FPSightsTableHeader",
            parent=styles["BodyText"],
            textColor=colors.white,
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="FPSightsTableCell",
            parent=styles["BodyText"],
            leading=13,
        )
    )

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="FPSights Post-Match Report",
        author="FPSights",
    )

    video_path = Path(str(video.get("path", "Unknown video")))
    story = [
        Paragraph("FPSights Post-Match Report", styles["FPSightsTitle"]),
        Paragraph(
            f"Video: {escape(video_path.name)}<br/>Generated: "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles["BodyText"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("Performance summary", styles["FPSightsSection"]),
    ]

    summary_rows = [
        ["Metric", "Result", "Evidence"],
        [
            "Crosshair proximity",
            _number(crosshair.get("score_percent"), "%"),
            "Estimated from crosshair distance to enemy head point",
        ],
        [
            "Aim alignment time",
            _number(aim.get("average_ms"), "ms"),
            (
                f"Measured subset: {aim.get('measured_encounters', 0)}/"
                f"{aim.get('encounters', 0)} encounters"
            ),
        ],
        [
            "Enemy detections",
            str(detection.get("total_detections", 0)),
            f"Across {detection.get('frames_with_detections', 0)} frames",
        ],
        [
            "Minimap marker coverage",
            _percent(positioning.get("coverage_percent")),
            f"{positioning.get('sample_count', 0)} POV-marker samples",
        ],
        [
            "Gameplay rounds",
            str(segmentation.get("rounds", 0)),
            _duration(segmentation.get("analyzable_duration_ms")),
        ],
    ]
    summary_rows = [
        [
            Paragraph(escape(str(value)), styles["FPSightsTableHeader" if row_index == 0 else "FPSightsTableCell"])
            for value in row
        ]
        for row_index, row in enumerate(summary_rows)
    ]
    summary_table = Table(summary_rows, colWidths=[42 * mm, 35 * mm, 79 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#132536")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f3f6f8")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b8c5cf")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(summary_table)
    if result.get("limited_run") or result.get("status") == "stopped":
        story.append(Paragraph("Partial run: these results cover only processed frames.", styles["BodyText"]))

    story.append(Paragraph("Coaching report", styles["FPSightsSection"]))
    for recommendation in simple_coaching(result):
        story.append(Paragraph(escape(recommendation), styles["BodyText"]))
        story.append(Spacer(1, 2 * mm))

    heatmap_path = (result.get("artifacts") or {}).get("heatmap")
    if heatmap_path and Path(heatmap_path).is_file():
        heatmap = Image(str(heatmap_path))
        scale = min(156 * mm / heatmap.imageWidth, 75 * mm / heatmap.imageHeight)
        heatmap.drawWidth = heatmap.imageWidth * scale
        heatmap.drawHeight = heatmap.imageHeight * scale
        story.append(KeepTogether([
            Paragraph("POV minimap activity", styles["FPSightsSection"]),
            heatmap,
            Paragraph("Warmer areas contain more marker observations. Approximate crop coordinates; map rotation and missed markers limit interpretation.", styles["BodyText"]),
        ]))

    story.extend(
        [
            Paragraph("Interpretation notes", styles["FPSightsSection"]),
            Paragraph(
                "Crosshair proximity is an estimate from detected enemy boxes, not "
                "shooting accuracy or a skill grade. Aim alignment time includes "
                "only the measured encounters; it is not shot reaction time. "
                "Minimap marker coverage is tracking availability, not positioning skill. POV samples may include spectated teammates; alive state and identity are not verified. Rotating or centered minimaps do not provide fixed map locations. "
                "Missed enemies and false positives can change these figures. "
                "No manual round-by-round checking is required.",
                styles["BodyText"],
            ),
        ]
    )

    document.build(story)
    return output_path


def coaching_recommendations(
    crosshair: dict[str, Any], aim: dict[str, Any]
) -> list[str]:
    """Describe available estimates without grading a player's ability."""
    messages: list[str] = []
    score = crosshair.get("score_percent")
    frames = _count(crosshair.get("evaluated_frames"))
    if _is_number(score) and frames:
        messages.append(
            f"Crosshair proximity estimate: {score:.1f}% across {frames} detected "
            "frames. This measures distance to an estimated head point, not "
            "shooting accuracy. Review the source moments before choosing a drill."
        )
    else:
        messages.append(
            "Crosshair proximity was not measurable. Review a clear live-round "
            "encounter before drawing a conclusion."
        )

    measured = _count(aim.get("measured_encounters"))
    encounters = _count(aim.get("encounters"))
    average = aim.get("average_ms")
    if _is_number(average) and measured:
        messages.append(
            f"Aim alignment estimate: {average:.0f} ms in {measured} of "
            f"{encounters} detected encounters. The other "
            f"{max(0, encounters - measured)} encounters were not measured; "
            "this is not shot reaction time."
        )
    else:
        messages.append(
            f"Aim alignment was not measurable in {encounters} detected "
            "encounters. No speed conclusion is available."
        )
    messages.append(
        "Next step: inspect a few original-video moments and practice one "
        "visible habit for five minutes. Do not use these estimates as a rank."
    )
    return messages


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _count(value: Any) -> int:
    return max(0, int(value)) if _is_number(value) else 0


def _percent(value: Any) -> str:
    return f"{value:.1f}%" if isinstance(value, (int, float)) else "N/A"


def _number(value: Any, unit: str) -> str:
    return f"{value:.1f} {unit}" if isinstance(value, (int, float)) else "N/A"


def _duration(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "N/A"
    return f"{value / 1000:.1f} seconds analyzed"


def simple_coaching(result: dict[str, Any]) -> list[str]:
    """Shared UI/PDF wording: observations and general drills stay separate."""
    analytics = result.get("analytics") or {}
    vertical = analytics.get("vertical_placement") or {}
    aim = analytics.get("aim_reaction") or {}
    count = vertical.get("evaluated_frames", 0)
    messages = []
    if count:
        messages.append(
            f"Crosshair height: below the estimated head in {vertical['below_frames']} frames, "
            f"above in {vertical['above_frames']}, level in {vertical['level_frames']} "
            f"({count} single-enemy frames). Average vertical gap: "
            f"{vertical['mean_absolute_offset_pct']:.1f}% of enemy box height. "
            "This describes screen alignment, not mouse movement or confirmed mistakes."
        )
    else:
        messages.append("Crosshair height: unavailable for this analysis. Older saved runs need a fresh analysis for this metric.")
    measured = aim.get("measured_encounters", 0)
    total = aim.get("encounters", 0)
    if measured and aim.get("average_ms") is not None:
        messages.append(
            f"Aim alignment: {aim['average_ms']:.0f} ms average across {measured}/{total} encounters. "
            "Only encounters that reached the estimated head area are included. "
            "Sampled frames limit timing precision; this is not time-to-damage or reaction time."
        )
    else:
        messages.append("Aim alignment: not enough measured encounters to report a time.")
    messages.extend([
        "General practice - pre-aim: hold common angles at expected head height and clear one angle at a time. This is a drill, not a diagnosed mistake.",
        "General practice - stop, aim, fire: practise controlled taps or short bursts. Use the in-game shooting-error display to practise stopping before firing; FPSights does not measure movement error.",
        "Optional Range drill: use Medium bots with armor and the same weapon each session. Record your score out of 30 and compare with your own baseline. Spend five minutes; no universal pass score is applied.",
        "Not measured: HS%, first-shot hit rate, time-to-damage and movement error. Enemy boxes alone cannot establish hits, shots or damage."
    ])
    if result.get("limited_run") or result.get("status") == "stopped":
        messages.insert(0, "Partial analysis: this report covers only the processed footage.")
    return messages
