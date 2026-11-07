from io import BytesIO
from time import time
from typing import Literal

from asanypath import AsAnyPath as Path
from textual import work
from textual.widget import Widget
from textual.widgets import Static
from textual_image.widget import (
    AutoImage,
    BaseImage,
    HalfcellImage,
    SixelImage,
    SixelOptions,
    TGPImage,
    UnicodeImage
)

from textual_video._cell import fit_cells
from textual_video.core import get_video_size, iter_frames


class VideoPlayer(Widget):
    def __init__(
        self,
        path: str | Path,
        fps: int = 15,
        graphics: Literal["auto", "tgp", "sixel", "halfcell", "unicode"] = "auto",
        sixel_options: SixelOptions | None = None
    ):
        super().__init__()
        self.path = Path(path)
        self.fps = fps
        self.graphics = graphics
        self.graphics_sixel_options = sixel_options
        self.frame = 0
        self._last_frame_update = time()

        self.styles.layout = "vertical"

    @work(exclusive=True)
    async def _init(self):
        original_w, original_h = await get_video_size(self.path)

        textual_w, textual_h, video_w, video_h = fit_cells(
            original_w, original_h, self.size.width, self.size.height - 1
        )

        image = self.query_one(SixelImage)
        image.styles.width = textual_w
        image.styles.height = textual_h

        self.iterator = iter_frames(self.path, video_w, video_h, self.fps)
        self.timer = self.set_interval(1 / self.fps, self._next_frame)
        self._start = None

    def on_resize(self, event):  # noe on mount because we need size
        self._init()

    async def _next_frame(self):
        if self._start is None:
            self._start = time() - 0.001

        target = int((time() - self._start) * self.fps)
        if self.frame > target:
            self.log.warning("ahead of schedule")
            return  # ahead

        try:
            frame = await anext(self.iterator)
            self.frame += 1
            self.log("update frame", index=self.frame)
            self._set_frame(frame)

        except StopAsyncIteration:
            self.timer.stop()
            self.log("stop", reason="frames end")

    def _set_frame(self, image: BytesIO):
        self.query_one(
            Static
        ).content = f"FPS: {round(1 / (time() - self._last_frame_update), 3)}"
        self._last_frame_update = time()
        self.query_one(BaseImage).image = image

    def compose(self):
        yield Static("FPS: 0")
        match self.graphics:
            case "auto":
                yield AutoImage()
            case "unicode":
                yield UnicodeImage()
            case "halfcell":
                yield HalfcellImage()
            case "sixel":
                yield SixelImage()
            case "tgp":
                yield TGPImage()
