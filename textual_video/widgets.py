from io import BytesIO
from pathlib import Path

from textual import work
from textual.widget import Widget
from textual_image.widget import SixelImage

from textual_video.core import load_video_frames


class VideoPlayer(Widget):
    def __init__(self, path: str | Path):
        super().__init__()
        self.path = Path(path)
        self.frame = 0

    @work(exclusive=True)
    async def load_frames(self):
        await load_video_frames(self.path)

        self.loading = False
        self.set_interval(1 / 25, self.update_frame)

    async def on_mount(self):
        self.loading = True
        self.load_frames()

    def update_frame(self):
        self.frame += 1
        self.log.debug("update frame", index=self.frame)
        self._set_frame(
            (Path("frames") / self.path.name / f"{self.frame}.jpg").read_bytes()
        )

    def _set_frame(self, image: bytes):
        self.query_one(SixelImage).image = BytesIO(image)

    def compose(self):
        yield SixelImage()
