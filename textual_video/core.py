from typing import AsyncIterator, cast

from aio_ffmpeg import FFmpegClient
from asanypath import AsAnyPath as Path

client = FFmpegClient()


async def save_video_frames(path: Path) -> int:
    frames: Path = Path("frames") / path.name
    await frames.mkdir(exist_ok=True, parents=True)

    async for file in cast(AsyncIterator[Path], frames.iterdir()):
        await file.unlink()

    await (
        client.pipeline(path)
        # .video_filter(rf"select='between(n\,{offset}\,{offset + 10})'")
        .video_filter("fps=15")
        .output(frames / "%10d.jpg")
        .run()
    )
    return len([True async for _ in cast(AsyncIterator[Path], frames.glob("*"))])
