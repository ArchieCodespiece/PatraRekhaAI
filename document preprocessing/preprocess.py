import cv2
import numpy as np


# ============================================================
# DESKEW
# ============================================================

def deskew(gray):
    """
    Correct small rotation/skew in a grayscale document image.
    """

    coords = np.column_stack(np.where(gray > 0))

    if len(coords) == 0:
        return gray

    angle = cv2.minAreaRect(coords)[-1]

    angle = -(90 + angle) if angle < -45 else -angle

    h, w = gray.shape

    matrix = cv2.getRotationMatrix2D(
        (w // 2, h // 2),
        angle,
        1.0,
    )

    return cv2.warpAffine(
        gray,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


# ============================================================
# PREPROCESS
# ============================================================

def preprocess_image(img):
    """
    Prepare a PDF page image for PaddleOCR.

    PaddleOCR/PaddleX expects a 3-channel image.
    Therefore, preprocessing is performed in grayscale,
    but the final image is converted back to BGR.
    """

    # --------------------------------------------------------
    # Ensure NumPy array
    # --------------------------------------------------------

    img = np.asarray(img)

    # --------------------------------------------------------
    # Convert to grayscale
    # --------------------------------------------------------

    if img.ndim == 3:
        gray = cv2.cvtColor(
            img,
            cv2.COLOR_RGB2GRAY,
        )

    elif img.ndim == 2:
        gray = img

    else:
        raise ValueError(
            f"Unsupported image shape: {img.shape}"
        )

    # --------------------------------------------------------
    # Deskew
    # --------------------------------------------------------

    gray = deskew(gray)

    # --------------------------------------------------------
    # Light blur
    # --------------------------------------------------------

    gray = cv2.GaussianBlur(
        gray,
        (3, 3),
        0,
    )

    # --------------------------------------------------------
    # Convert grayscale back to 3-channel BGR
    #
    # IMPORTANT:
    # PaddleOCR/PaddleX expects img.shape[2] to exist.
    # --------------------------------------------------------

    processed = cv2.cvtColor(
        gray,
        cv2.COLOR_GRAY2BGR,
    )

    return processed