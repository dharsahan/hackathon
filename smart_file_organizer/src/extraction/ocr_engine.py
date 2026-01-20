"""
OCR Engine
==========

Optical Character Recognition using Tesseract.
Includes image preprocessing for improved accuracy.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from src.utils.logging_config import get_logger
from src.utils.exceptions import ExtractionError

logger = get_logger(__name__)

# Lazy imports for heavy libraries
pytesseract = None
Image = None
cv2 = None
np = None
pdf2image = None


def _import_tesseract():
    """Lazy import pytesseract."""
    global pytesseract
    if pytesseract is None:
        import pytesseract as _pytesseract

        pytesseract = _pytesseract
    return pytesseract


def _import_pil():
    """Lazy import PIL."""
    global Image
    if Image is None:
        from PIL import Image as _Image

        Image = _Image
    return Image


def _import_cv2():
    """Lazy import OpenCV."""
    global cv2, np
    if cv2 is None:
        import cv2 as _cv2
        import numpy as _np

        cv2 = _cv2
        np = _np
    return cv2, np


def _import_pdf2image():
    """Lazy import pdf2image."""
    global pdf2image
    if pdf2image is None:
        import pdf2image as _pdf2image

        pdf2image = _pdf2image
    return pdf2image


@dataclass
class OCRConfig:
    """OCR engine configuration.

    Attributes:
        languages: Tesseract language codes (e.g., "eng", "eng+fra").
        dpi: DPI for PDF to image conversion.
        enable_preprocessing: Apply image preprocessing for better accuracy.
        timeout: OCR timeout in seconds.
        psm: Page segmentation mode (0-13).
        oem: OCR Engine Mode (0-3).
    """

    languages: str = "eng"
    dpi: int = 300
    enable_preprocessing: bool = True
    timeout: int = 30
    psm: int = 1  # Automatic page segmentation with OSD
    oem: int = 3  # Default, based on what is available

    def to_tesseract_config(self) -> str:
        """Convert to Tesseract config string."""
        return f"--psm {self.psm} --oem {self.oem}"


class ImagePreprocessor:
    """Image preprocessing for improved OCR accuracy.

    Applies various filters and transformations to make text more readable.
    """

    @staticmethod
    def preprocess(image) -> "np.ndarray":
        """Apply preprocessing pipeline to image.

        Args:
            image: OpenCV image array (BGR).

        Returns:
            Preprocessed image (grayscale).
        """
        cv2, np = _import_cv2()

        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Adaptive thresholding for varying lighting conditions
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Denoise
        denoised = cv2.fastNlMeansDenoising(binary, None, 10, 7, 21)

        return denoised

    @staticmethod
    def deskew(image) -> "np.ndarray":
        """Correct skew in scanned documents.

        Args:
            image: Grayscale image array.

        Returns:
            Deskewed image.
        """
        cv2, np = _import_cv2()

        # Find all non-zero points (text pixels)
        coords = np.column_stack(np.where(image > 0))

        if len(coords) < 10:
            return image

        # Get the minimum area rectangle
        angle = cv2.minAreaRect(coords)[-1]

        # Adjust angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Only correct if skew is significant but not too extreme
        if abs(angle) > 0.5 and abs(angle) < 15:
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
            )
            return rotated

        return image

    @staticmethod
    def remove_shadows(image) -> "np.ndarray":
        """Remove shadows from document images.

        Args:
            image: BGR image array.

        Returns:
            Shadow-corrected image.
        """
        cv2, np = _import_cv2()

        rgb_planes = cv2.split(image)
        result_planes = []

        for plane in rgb_planes:
            dilated = cv2.dilate(plane, np.ones((7, 7), np.uint8))
            blurred = cv2.medianBlur(dilated, 21)
            diff = 255 - cv2.absdiff(plane, blurred)
            result_planes.append(diff)

        return cv2.merge(result_planes)


class OCREngine:
    """OCR engine using Tesseract.

    Features:
    - Image preprocessing for improved accuracy
    - PDF page conversion
    - Multiple language support
    - Configurable timeout
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        """Initialize OCR engine.

        Args:
            config: OCR configuration. Uses defaults if not provided.
        """
        self.config = config or OCRConfig()
        self.preprocessor = ImagePreprocessor()
        self._verify_tesseract()

    def _verify_tesseract(self) -> None:
        """Verify Tesseract is installed and accessible."""
        pytesseract = _import_tesseract()
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            logger.warning(f"Tesseract not found or not accessible: {e}")

    def extract_text(self, image_path: Path) -> str:
        """Extract text from an image file.

        Args:
            image_path: Path to the image.

        Returns:
            Extracted text.

        Raises:
            ExtractionError: If OCR fails.
        """
        pytesseract = _import_tesseract()
        cv2, np = _import_cv2()
        Image = _import_pil()

        try:
            # Load image with OpenCV
            image = cv2.imread(str(image_path))

            if image is None:
                raise ExtractionError(
                    "Failed to load image",
                    file_path=str(image_path),
                    extractor_type="OCR",
                )

            # Apply preprocessing if enabled
            if self.config.enable_preprocessing:
                processed = self.preprocessor.preprocess(image)
            else:
                processed = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Convert to PIL Image for Tesseract
            pil_image = Image.fromarray(processed)

            # Perform OCR
            text = pytesseract.image_to_string(
                pil_image,
                lang=self.config.languages,
                timeout=self.config.timeout,
                config=self.config.to_tesseract_config(),
            )

            return text.strip()

        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
            raise ExtractionError(
                f"OCR failed: {e}", file_path=str(image_path), extractor_type="OCR"
            )

    def extract_from_pdf(self, pdf_path: Path, max_pages: int = 5) -> str:
        """Extract text from PDF using OCR.

        Converts PDF pages to images and performs OCR on each.

        Args:
            pdf_path: Path to PDF file.
            max_pages: Maximum pages to process.

        Returns:
            Combined extracted text.
        """
        pdf2image = _import_pdf2image()
        Image = _import_pil()
        pytesseract = _import_tesseract()
        cv2, np = _import_cv2()

        try:
            # Convert PDF pages to images
            images = pdf2image.convert_from_path(
                pdf_path, dpi=self.config.dpi, first_page=1, last_page=max_pages
            )

            text_parts = []

            for i, pil_image in enumerate(images):
                logger.debug(f"OCR processing page {i+1}/{len(images)}")

                # Convert PIL to OpenCV format
                cv_image = np.array(pil_image)
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)

                # Preprocess
                if self.config.enable_preprocessing:
                    processed = self.preprocessor.preprocess(cv_image)
                else:
                    processed = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

                # Convert back to PIL
                pil_processed = Image.fromarray(processed)

                # OCR
                text = pytesseract.image_to_string(
                    pil_processed,
                    lang=self.config.languages,
                    timeout=self.config.timeout,
                    config=self.config.to_tesseract_config(),
                )

                if text.strip():
                    text_parts.append(text.strip())

            return "\n\n".join(text_parts)

        except Exception as e:
            logger.error(f"PDF OCR failed for {pdf_path}: {e}")
            raise ExtractionError(
                f"PDF OCR failed: {e}", file_path=str(pdf_path), extractor_type="OCR"
            )

    def is_available(self) -> bool:
        """Check if OCR engine is available.

        Returns:
            True if Tesseract is installed and accessible.
        """
        try:
            pytesseract = _import_tesseract()
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
