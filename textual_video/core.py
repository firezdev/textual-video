from asyncio import IncompleteReadError, Queue, create_subprocess_exec, create_task
from json import loads
from re import compile
from subprocess import PIPE

from asanypath import AsAnyPath as Path
from PIL import Image

PTS_RE = compile(rb"pts_time:\s*([0-9.]+)")


async def get_video_meta(path: str | Path) -> tuple[int, int, float]:
    proc = await create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        path,
        stdout=PIPE
    )
    out = loads((await proc.communicate())[0])
    return (
        out["streams"][0]["width"],
        out["streams"][0]["height"],
        float(out["format"]["duration"])
    )


async def iter_frames(
    path: str | Path, width: int, height: int, start: float = 0.0, fps: int = 15
):
    proc = await create_subprocess_exec(
        "ffmpeg",
        "-loglevel",
        "error",
        "-ss",
        str(start),
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


async def iter_keyframes(
    path: str, width: int, height: int, duration: float, limit: int = 300
):
    """Yield (seconds, image) for up to `limit` keyframes spread over the video."""
    gap = duration / limit
    vf = rf"select=isnan(prev_selected_t)+gte(t-prev_selected_t\,{gap}),scale={width}:{height},showinfo"
    proc = await create_subprocess_exec(
        "ffmpeg",
        "-loglevel",
        "info",
        "-skip_frame",
        "nokey",
        "-i",
        path,
        "-vf",
        vf,
        "-fps_mode",
        "passthrough",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
        stdout=PIPE,
        stderr=PIPE
    )
    frame_size = width * height * 3
    times: Queue[float | None] = Queue()

    async def read_times():
        # showinfo prints one line with pts_time per output frame
        assert proc.stderr
        async for line in proc.stderr:
            if m := PTS_RE.search(line):
                await times.put(float(m.group(1)))
        await times.put(None)

    reader = create_task(read_times())
    try:
        while True:
            try:
                assert proc.stdout
                data = await proc.stdout.readexactly(frame_size)
            except IncompleteReadError:
                break
            t = await times.get()
            if t is None:
                break
            yield t, Image.frombuffer("RGB", (width, height), data)

    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.communicate()
        await reader
