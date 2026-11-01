from pathlib import Path

from aio_ffmpeg import FFmpegClient

client = FFmpegClient()


async def load_video_frames(path: Path):
    frames = Path("frames") / path.name
    frames.mkdir(exist_ok=True, parents=True)

    for file in frames.iterdir():
        file.unlink()

    await (
        client.pipeline(path)
        # .video_filter(rf"select='between(n\,{offset}\,{offset + 10})'")
        .video_filter("fps=25")
        .output(frames / "%d.jpg")
        .run()
    )
