from PIL import Image, ImageChops


def _content_bbox(image: Image.Image, tolerance: int = 10):
    source = image.convert("RGB")
    background = Image.new("RGB", source.size, "white")
    difference = ImageChops.difference(source, background)
    mask = difference.convert("L").point(lambda value: 255 if value > tolerance else 0)
    return mask.getbbox()


def _expand_box(box: tuple[int, int, int, int], image_size: tuple[int, int], padding: int):
    width, height = image_size
    left, top, right, bottom = box
    return (
        max(0, left - padding),
        max(0, top - padding),
        min(width, right + padding),
        min(height, bottom + padding),
    )


def _fit_box_to_page_aspect(
    box: tuple[int, int, int, int],
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    image_width, image_height = image_size
    page_aspect = image_width / image_height
    left, top, right, bottom = box
    box_width = max(1, right - left)
    box_height = max(1, bottom - top)
    target_width = max(box_width, round(box_height * page_aspect))
    target_height = max(box_height, round(box_width / page_aspect))
    target_width = min(image_width, target_width)
    target_height = min(image_height, target_height)

    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    new_left = round(center_x - target_width / 2)
    new_top = round(center_y - target_height / 2)
    new_left = min(max(0, new_left), image_width - target_width)
    new_top = min(max(0, new_top), image_height - target_height)
    return (new_left, new_top, new_left + target_width, new_top + target_height)


def _ensure_minimum_box_size(
    box: tuple[int, int, int, int],
    image_size: tuple[int, int],
    min_width: int,
    min_height: int,
) -> tuple[int, int, int, int]:
    image_width, image_height = image_size
    left, top, right, bottom = box
    target_width = min(image_width, max(right - left, min_width))
    target_height = min(image_height, max(bottom - top, min_height))
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    new_left = round(center_x - target_width / 2)
    new_top = round(center_y - target_height / 2)
    new_left = min(max(0, new_left), image_width - target_width)
    new_top = min(max(0, new_top), image_height - target_height)
    return (new_left, new_top, new_left + target_width, new_top + target_height)


def trim_page_to_content(
    image: Image.Image,
    tolerance: int = 10,
    padding_ratio: float = 0.02,
    minimum_page_ratio: float = 0.72,
) -> Image.Image:
    """Trim excess white margin while preserving the page orientation and aspect ratio."""
    bbox = _content_bbox(image, tolerance)
    if not bbox:
        return image

    padding = max(18, round(min(image.size) * padding_ratio))
    crop_box = _expand_box(bbox, image.size, padding)
    crop_box = _fit_box_to_page_aspect(crop_box, image.size)
    min_width = round(image.width * minimum_page_ratio)
    min_height = round(image.height * minimum_page_ratio)
    crop_box = _ensure_minimum_box_size(crop_box, image.size, min_width, min_height)
    crop_box = _fit_box_to_page_aspect(crop_box, image.size)
    crop_width = crop_box[2] - crop_box[0]
    crop_height = crop_box[3] - crop_box[1]
    if crop_width >= image.width * 0.985 and crop_height >= image.height * 0.985:
        return image
    return image.crop(crop_box)
