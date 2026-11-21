from io import BytesIO
from time import monotonic
from typing import Literal

from asanypath import AsAnyPath as Path
from textual import work
from textual.binding import Binding
from textual.containers import Center
from textual.message import Message
from textual.reactive import reactive
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

from textual_video._audio import AudioPlayer
from textual_video._cell import fit_cells
from textual_video.core import get_video_meta, iter_frames


class VideoTrack(Static):
    LINE: str = "━"
    CIRCLE: str | None = "█"

    def set_watched(self, ratio: float):
        if self.CIRCLE:
            watched = round(ratio * (self.size.width - 1))
            self.update(
                f"[red]{self.LINE * watched}{self.CIRCLE}[grey]{self.LINE * (self.size.width - watched - 1)}"
            )
        else:
            watched = round(self.size.width * ratio)
            self.update(
                f"[red]{self.LINE * watched}[grey]{self.LINE * (self.size.width - watched)}"
            )


class PlayButton(Static):
    PLAY = "▶"
    PAUSE = "⏸"
    paused = reactive(False)
    DEFAULT_CSS = """
    PlayButton {
        width: auto;
    }
    """

    class Pressed(Message):
        pass

    def render(self):
        return self.PLAY if self.paused else self.PAUSE

    def on_click(self, event):
        event.stop()
        self.post_message(self.Pressed())


class NerdPlayButton(PlayButton):
    PLAY = "\uf04b"
    PAUSE = "\uf04c"


class VideoPlayer(Widget, can_focus=True):
    BINDINGS = [Binding("space", "toggle_pause"), Binding("f", "toggle_fullscreen")]

    TRACK_CLASS: type[VideoTrack] = VideoTrack
    PLAY_BUTTON: type[PlayButton] = PlayButton

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
        self.audio = AudioPlayer(path)
        self.fps = fps
        self.repeat = repeat
        self.skip_frames = skip_frames
        self.graphics = graphics
        self.graphics_sixel_options = sixel_options

        self.frame = 0
        self.paused = False
        self._last_frame_update = monotonic()
        self.debug_show_fps = False
        self.timer = None

        self.styles.layout = "vertical"

    @work(exclusive=True)
    async def _reload(self):
        self.log("init video", path=self.path)
        textual_w, textual_h, video_w, video_h = fit_cells(
            *self._meta,
            self.size.width,
            self.size.height - 2 - int(self.debug_show_fps),
            max_width=None if self.is_maximized else 500,
            upscale=self.is_maximized
        )

        image = self.query_one(BaseImage)
        image.styles.width = textual_w
        image.styles.height = textual_h
        row_width = "100%" if self.is_maximized else textual_w
        self.query_one(Center).styles.width = row_width
        self.query_one(VideoTrack).styles.width = row_width

        restarting = self.frame > 0  # resized or maximized while playing
        if self.timer is not None:
            self.timer.stop()

        self.log("start playback")
        self.iterator = iter_frames(
            self.path, video_w, video_h, start=self.frame / self.fps, fps=self.fps
        )
        self.timer = self.set_interval(1 / self.fps, self._next_frame)

        if restarting:
            if self.paused:
                self.timer.pause()
            return  # keep the video clock and the audio as they are

        self._start = None
        self._paused_at = None
        self._ended = False

        await self.audio.start()

    async def on_mount(self):
        w, h, self.duration = await get_video_meta(self.path)
        self._meta = (w, h)
        self._reload()

    def on_resize(self):
        if self._meta is not None:
            self._reload()

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

                self.frame = target - 1

            frame = await anext(self.iterator)
            self.frame += 1
            self.log.debug("update frame", index=self.frame)
            self._set_frame(frame)

        except StopAsyncIteration:
            self.log("stop playback")
            self.timer.stop()
            if self.repeat:
                self.frame = 0
                self._reload()
            else:
                self.action_toggle_pause()
                self._ended = True

        self.query_one(VideoTrack).set_watched(self.frame / self.fps / self.duration)

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

            if self._ended:
                self._ended = False
                self.frame = 0
                self._reload()
            else:
                self.call_next(self.audio.start, self.frame / self.fps)
            self.timer.resume()

        else:
            self._paused_at = monotonic()
            self.timer.pause()
            self.call_next(self.audio.stop)

        self.paused = not self.paused
        self.query_one(PlayButton).paused = self.paused

    def on_play_button_pressed(self):
        self.action_toggle_pause()

    def action_toggle_fullscreen(self):
        self.log("toggle fullscreen")
        if self.is_maximized:
            self.screen.minimize()
        else:
            self.screen.maximize(self)
        self._reload()

    def compose(self):
        if self.debug_show_fps:
            yield Static("FPS: 0")
        with Center():
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

        yield self.TRACK_CLASS()
        yield self.PLAY_BUTTON()

    async def on_unmount(self):
        if (timer := getattr(self, "timer", None)) is not None:
            timer.stop()
        await self.audio.stop()
        if (iterator := getattr(self, "iterator", None)) is not None:
            await iterator.aclose()
