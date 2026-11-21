from asyncio import create_subprocess_exec
from asyncio.subprocess import DEVNULL, Process
from os import close, pipe
from shutil import which

from asanypath import AsAnyPath as Path


class AudioPlayer:
    """Plays a video's audio track with ffmpeg (accurate seek) piped into ffplay."""

    def __init__(self, path: str | Path):
        self.path = path
        self.available = which("ffplay") is not None
        self._procs: list[Process] = []

    async def start(self, position: float = 0.0, speed: float = 1.0) -> None:
        await self.stop()
        if not self.available:
            return
        read_fd, write_fd = pipe()
        args = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-nostdin",
            "-ss",
            str(position),
            "-i",
            self.path,
            "-vn"
        ]
        if speed != 1.0:
            args += ["-af", f"atempo={speed}"]
        decoder = await create_subprocess_exec(
            *args, "-f", "wav", "pipe:1", stdout=write_fd, stderr=DEVNULL
        )
        player = await create_subprocess_exec(
            "ffplay",
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            stdin=read_fd,
            stdout=DEVNULL,
            stderr=DEVNULL
        )
        # The children hold their own copies of the pipe ends
        close(read_fd)
        close(write_fd)
        self._procs = [decoder, player]

    async def stop(self) -> None:
        for proc in self._procs:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()  # safe: no pipes to drain on our side
        self._procs = []
