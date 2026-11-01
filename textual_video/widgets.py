from io import BytesIO
from time import time

from asanypath import AsAnyPath as Path
from textual import work
from textual.widget import Widget
from textual.widgets import Static
from textual_image.widget import SixelImage

from textual_video.core import iter_frames


class VideoPlayer(Widget):
    def __init__(self, path: str | Path):
        super().__init__()
        self.path = Path(path)
        self.frame = 0
        self._last_frame_update = time()
        self.styles.layout = "vertical"

    @work(exclusive=True)
    async def _init(self):
        self.iterator = iter_frames(self.path)
        self.timer = self.set_interval(1 / 15, self._next_frame)

    def on_mount(self):
        self._init()

    async def _next_frame(self):
        self.log("update frame", index=self.frame)

        try:
            self._set_frame(await anext(self.iterator))
            self.frame += 1
        except StopAsyncIteration:
            self.timer.stop()
            self.log("stop", reason="frames end")

    def _set_frame(self, image: BytesIO):
        self.query_one(
            Static
        ).content = f"FPS: {round(1 / (time() - self._last_frame_update), 3)}"
        self._last_frame_update = time()
        self.query_one(SixelImage).image = image

    def compose(self):
        yield Static("FPS: 0")
        yield SixelImage()
