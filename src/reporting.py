"""Generate a compact post-match PDF from an FPSights analysis result."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
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
            f"Video: {video_path.name}<br/>Generated: "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles["BodyText"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("Performance summary", styles["FPSightsSection"]),
    ]

    summary_rows = [
        ["Metric", "Result", "Evidence"],
        [
            "Crosshair score",
            _percent(crosshair.get("score_percent")),
            f"{crosshair.get('evaluated_frames', 0)} detected frames",
        ],
        [
            "Mean head error",
            _number(crosshair.get("mean_head_error_px"), "px"),
            "Distance from crosshair to estimated enemy head",
        ],
        [
            "Aim acquisition",
            _number(aim.get("average_ms"), "ms"),
            (
                f"{aim.get('measured_encounters', 0)}/"
                f"{aim.get('encounters', 0)} encounters measured"
            ),
        ],
        [
            "Enemy detections",
            str(detection.get("total_detections", 0)),
            f"Across {detection.get('frames_with_detections', 0)} frames",
        ],
        [
            "Minimap tracking",
            _percent(positioning.get("coverage_percent")),
            f"{positioning.get('sample_count', 0)} player-marker samples",
        ],
        [
            "Gameplay rounds",
            str(segmentation.get("rounds", 0)),
            _duration(segmentation.get("analyzable_duration_ms")),
        ],
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

    story.append(Paragraph("Coaching feedback", styles["FPSightsSection"]))
    for recommendation in coaching_recommendations(crosshair, aim):
        story.append(Paragraph(f"- {recommendation}", styles["BodyText"]))
        story.append(Spacer(1, 1.5 * mm))

    story.extend(
        [
            Paragraph("Interpretation notes", styles["FPSightsSection"]),
            Paragraph(
                "Aim acquisition measures the time until the screen-center "
                "crosshair reaches the estimated head area. It is not shot "
                "reaction time. Detection-based results may include missed "
                "enemies or false positives, so use the review video to verify "
                "important events.",
                styles["BodyText"],
            ),
        ]
    )

    document.build(story)
    return output_path


def coaching_recommendations(
    crosshair: dict[str, Any], aim: dict[str, Any]
) -> list[str]:
    recommendations: list[str] = []
    score = crosshair.get("score_percent")
    if isinstance(score, (int, float)):
        if score >= 70:
            recommendations.append("Crosshair placement is a strength. Maintain head-level pre-aim.")
        elif score >= 40:
            recommendations.append("Crosshair placement is developing. Pre-aim common angles more consistently.")
        else:
            recommendations.append("Crosshair placement needs work. Practice keeping the crosshair near head level.")
    else:
        recommendations.append("Crosshair placement could not be measured in this analysis.")

    reaction = aim.get("average_ms")
    measured = aim.get("measured_encounters", 0)
    encounters = aim.get("encounters", 0)
    if isinstance(reaction, (int, float)):
        if reaction <= 250:
            recommendations.append("Aim acquisition was quick in the encounters that could be measured.")
        else:
            recommendations.append("Aim acquisition was slow. Practice controlled flicks and angle preparation.")
    else:
        recommendations.append("Aim acquisition could not be measured from the detected encounters.")

    if encounters and measured < encounters:
        recommendations.append(
            f"Aim was not acquired in {encounters - measured} of {encounters} detected encounters."
        )
    return recommendations


def _percent(value: Any) -> str:
    return f"{value:.1f}%" if isinstance(value, (int, float)) else "N/A"


def _number(value: Any, unit: str) -> str:
    return f"{value:.1f} {unit}" if isinstance(value, (int, float)) else "N/A"


def _duration(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "N/A"
    return f"{value / 1000:.1f} seconds analyzed"
