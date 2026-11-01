from io import BytesIO
from time import time
from typing import AsyncIterator

from asanypath import AsAnyPath as Path
from textual import work
from textual.widget import Widget
from textual.widgets import Static
from textual_image.widget import SixelImage
from typing_extensions import cast

from textual_video.core import save_video_frames


class VideoPlayer(Widget):
    def __init__(self, path: str | Path):
        super().__init__()
        self.path = Path(path)
        self.frame = 0
        self._batch_index = 0
        self._batch: list[BytesIO] = []
        self._last_frame_update = time()
        self.styles.layout = "vertical"

    @work(exclusive=True)
    async def _save_frames(self):
        self.frames_count = await save_video_frames(self.path)
        self.log("save frames", count=self.frames_count)

        self.loading = False
        self.timer = self.set_interval(1 / 15, self._next_frame)

    @work(exclusive=True)
    async def _load_batch(self):
        frames = [
            frame
            async for frame in cast(
                AsyncIterator[Path],
                (Path("frames") / self.path.name).glob(
                    rf"{'0' * (10 - 3 - len(str(self._batch_index)))}{self._batch_index}???.jpg"
                )
            )
        ]
        frames.sort(key=lambda frame: frame.name)
        self._batch = [BytesIO(await frame.read_bytes()) for frame in frames]

        self.log("load batch", index=self._batch_index, count=len(self._batch))
        self._batch_index += 1

    async def on_mount(self):
        self.loading = True
        self._save_frames()

    def _next_frame(self):
        self.log("update frame", index=self.frame)

        if self.frame % 1000 == 0 or not self._batch:
            self._load_batch()

        self._set_frame(self._batch[self.frame % 1000])
        self.frame += 1
        if self.frame >= self.frames_count:
            self.frame = 1
            # self.timer.stop()
            # self.log("stop", reason="frames end")

    def _set_frame(self, image: BytesIO):
        self.query_one(
            Static
        ).content = f"FPS: {round(1 / (time() - self._last_frame_update), 3)}"
        self._last_frame_update = time()
        self.query_one(SixelImage).image = image

    def compose(self):
        yield Static("FPS: 0")
        yield SixelImage()
