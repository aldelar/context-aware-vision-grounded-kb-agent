"""CU image analysis — send images to kb_image_analyzer, return descriptions.

Sends individual image files to the custom ``kb_image_analyzer`` Content
Understanding analyzer and returns structured descriptions including
``Description``, ``UIElements``, and ``NavigationPath``.

Prerequisites:
    - ``kb_image_analyzer`` must be deployed (``manage_analyzers deploy``).
    - ``gpt-4.1`` must be deployed and registered as CU default.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from fn_convert_cu.cu_client import get_cu_client

logger = logging.getLogger(__name__)

ANALYZER_ID = "kb_image_analyzer"


@dataclass
class ImageAnalysisResult:
    """Result of CU image analysis for a single image."""

    filename_stem: str
    description: str
    ui_elements: list[str] = field(default_factory=list)
    navigation_path: str = ""


def analyze_image(image_path: Path) -> ImageAnalysisResult:
    """Send a single image to CU ``kb_image_analyzer`` and return structured fields.

    Parameters
    ----------
    image_path:
        Path to an image file (``.image`` or ``.png``).

    Returns
    -------
    ImageAnalysisResult
        Populated with ``Description``, ``UIElements``, ``NavigationPath``.
        On failure, returns a result with a placeholder description.
    """
    stem = image_path.stem

    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Detect content type from magic bytes
    content_type = _detect_content_type(image_path)

    logger.info("Analyzing image %s via CU %s", image_path.name, ANALYZER_ID)

    try:
        client = get_cu_client()
        poller = client.begin_analyze_binary(
            analyzer_id=ANALYZER_ID,
            binary_input=image_path.read_bytes(),
            content_type=content_type,
        )
        result = poller.result()

        contents = result.contents or []
        if not contents:
            logger.warning("CU returned 0 contents for image %s", image_path.name)
            return ImageAnalysisResult(
                filename_stem=stem,
                description=f"Image: {stem}",
            )

        # Extract fields from the first content block
        fields = contents[0].get("fields", {})

        description = ""
        desc_field = fields.get("Description")
        if desc_field:
            description = desc_field.get("valueString", "")

        ui_elements: list[str] = []
        ui_field = fields.get("UIElements")
        if ui_field:
            items = ui_field.get("valueArray", [])
            ui_elements = [
                item.get("valueString", "") for item in items if item.get("valueString")
            ]

        navigation_path = ""
        nav_field = fields.get("NavigationPath")
        if nav_field:
            navigation_path = nav_field.get("valueString", "")

        logger.info(
            "Image %s: description=%d chars, ui_elements=%d, nav_path=%r",
            stem,
            len(description),
            len(ui_elements),
            navigation_path[:50] if navigation_path else "",
        )

        return ImageAnalysisResult(
            filename_stem=stem,
            description=description or f"Image: {stem}",
            ui_elements=ui_elements,
            navigation_path=navigation_path,
        )

    except Exception:
        logger.exception("Failed to analyze image %s", image_path.name)
        return ImageAnalysisResult(
            filename_stem=stem,
            description=f"Image: {stem}",
        )


def analyze_all_images(image_paths: list[Path]) -> list[ImageAnalysisResult]:
    """Analyze multiple images and return results in the same order.

    Images that fail analysis get a placeholder description (no crash).
    """
    results: list[ImageAnalysisResult] = []
    for path in image_paths:
        results.append(analyze_image(path))
    return results


def _detect_content_type(image_path: Path) -> str:
    """Detect image MIME type from file magic bytes."""
    header = image_path.read_bytes()[:12]
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if header[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if header[:4] == b"GIF8":
        return "image/gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    # Default to PNG (most common for our .image files)
    return "image/png"
