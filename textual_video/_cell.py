from textual_image._terminal import get_cell_size


def fit_cells(
    video_w: int, video_h: int, max_cols: int, max_rows: int
) -> tuple[int, int, int, int]:
    """Return (cols, rows, width_px, height_px) for the largest box that fits."""
    cell = get_cell_size()  # cached after the first call, so it's cheap
    scale = min(max_cols * cell.width / video_w, max_rows * cell.height / video_h, 1.0)
    scale = min(scale, 500 / video_w)
    cols = max(1, int(video_w * scale / cell.width))
    rows = max(1, int(video_h * scale / cell.height))
    return cols, rows, cols * cell.width, rows * cell.height
