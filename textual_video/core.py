from asyncio import IncompleteReadError, create_subprocess_exec
from asyncio.subprocess import PIPE
from json import loads

from asanypath import AsAnyPath as Path
from PIL import Image


async def get_video_size(path: str | Path) -> tuple[int, int]:
    proc = await create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:stream_side_data=rotation",
        "-of",
        "json",
        path,
        stdout=PIPE
    )
    out, _ = await proc.communicate()
    stream = loads(out)["streams"][0]
    return stream["width"], stream["height"]


async def iter_frames(path: str | Path, width: int, height: int, fps: int = 15):
    scale = min(1, 500 / width)
    width, height = round(width * scale / 2) * 2, round(height * scale / 2) * 2
    proc = await create_subprocess_exec(
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        path,
        "-vf",
        f"fps={fps},scale={width}:{height}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
        stdout=PIPE
    )
    frame_size = width * height * 3
    try:
        while True:
            try:
                assert proc.stdout
                data = await proc.stdout.readexactly(frame_size)
            except IncompleteReadError:
                break
            yield Image.frombuffer("RGB", (width, height), data)
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.communicate()
