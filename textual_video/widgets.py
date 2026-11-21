from io import BytesIO
from time import monotonic
from typing import Literal

from asanypath import AsAnyPath as Path
from textual import work
from textual.binding import Binding
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


class VideoPlayer(Widget, can_focus=True):
    BINDINGS = [Binding("space", "toggle_pause")]

    def __init__(
        self,
        path: str | Path,
        *,
        fps: int = 20,
        skip_frames: bool = False,
        repeat: bool = False,
        graphics: Literal["auto", "tgp", "sixel", "halfcell", "unicode"] = "auto",
        sixel_options: SixelOptions | None = None
    ):
        """
        Args:
            path (str | Path): Path to video.
            fps (int): Video FPS. Recommended maximum: 30~40, if more video will slow down (if skip_frames=False). Defaults to 20.
            skip_frames (bool): Allow to skip some frames; video may stutter, but duration will be exact on every selected FPS. Defaults to False.
            repeat (bool): Start video from beginning when it is ended. Defaults to False.
            graphics (str): Image redner type: "auto", "tgp", "sixel", "halfcell", or "unicode". Defaults to auto.
            sixel_options (SixelOptions, optional): Sixel image options; only used when graphics is set to "sixel". Defaults to None.
        """
        super().__init__()
        self.path = Path(path)
        self.fps = fps
        self.repeat = repeat
        self.skip_frames = skip_frames
        self.graphics = graphics
        self.graphics_sixel_options = sixel_options

        self.frame = 0
        self.paused = False
        self._last_frame_update = monotonic()
        self._inited = False
        self.debug_show_fps = False

        self.styles.layout = "vertical"

    @work(exclusive=True)
    async def _init(self):
        self.log("init video", path=self.path)
        self._inited = True
        original_w, original_h = await get_video_size(self.path)

        widget_h = self.size.height
        if self.debug_show_fps:
            widget_h -= 1

        textual_w, textual_h, video_w, video_h = fit_cells(
            original_w, original_h, self.size.width, widget_h
        )

        image = self.query_one(BaseImage)
        image.styles.width = textual_w
        image.styles.height = textual_h

        self.iterator = iter_frames(self.path, video_w, video_h, self.fps)
        self.timer = self.set_interval(1 / self.fps, self._next_frame)
        self._start = None
        self._paused_at = None

    def on_resize(self, event):  # not on mount because we need size
        if not self._inited:
            self._init()

    async def _next_frame(self):
        if self._start is None:
            self._start = monotonic() - 0.001

        target = int((monotonic() - self._start) * self.fps)
        if self.frame > target:
            self.log.warning(
                "skip frames",
                reason="too early",
                frame=self.frame,
                count=self.frame - target
            )
            return

        try:
            if self.skip_frames and self.frame < target - 3:
                self.log.warning(
                    "skip frames",
                    reason="too late",
                    frame=self.frame,
                    count=target - self.frame
                )
                for _ in range(target - self.frame - 1):
                    await anext(self.iterator)

                self.frame = target

            frame = await anext(self.iterator)
            self.frame += 1
            self.log.debug("update frame", index=self.frame)
            self._set_frame(frame)

        except StopAsyncIteration:
            self.timer.stop()
            self.log("stop", reason="frames end")
            if self.repeat:
                self.frame = 0
                self._init()

    def _set_frame(self, image: BytesIO):
        if self.debug_show_fps:
            self.query_one(
                Static
            ).content = f"FPS: {round(1 / (monotonic() - self._last_frame_update), 3)}"
            self._last_frame_update = monotonic()
        self.query_one(BaseImage).image = image

    def action_toggle_pause(self):
        self.log("toggle pause")
        if self.paused:
            self._last_frame_update = monotonic()
            if self._start is not None:
                assert self._paused_at
                self._start += monotonic() - self._paused_at
            self.timer.resume()
        else:
            self._paused_at = monotonic()
            self.timer.pause()
        self.paused = not self.paused

    def compose(self):
        if self.debug_show_fps:
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
