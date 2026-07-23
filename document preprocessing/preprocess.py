# -------------------------------
# DESKEW
# -------------------------------
def deskew(gray):
    coords = np.column_stack(np.where(gray > 0))
    if len(coords) == 0:
        return gray

    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle

    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)

    return cv2.warpAffine(
        gray, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )


# -------------------------------
# PREPROCESS
# -------------------------------
def preprocess_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = deskew(gray)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return gray