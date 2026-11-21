"""Simple YouTube player: paste a link, the video is downloaded and played in the terminal.

Requires yt-dlp (`pip install yt-dlp`) in addition to textual-video.
"""

from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.markup import escape
from textual.widgets import Footer, Input, Static
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from textual_video import VideoPlayer

DOWNLOADS = Path("downloads")


class _SilentLogger:
    """yt-dlp prints to the terminal by default, which would break the Textual screen."""

    def debug(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass  # errors are raised as DownloadError anyway


class YouTubePlayerApp(App):
    CSS = """
    #status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    VideoPlayer {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Paste a YouTube link and press Enter")
        yield Static("", id="status")
        yield Footer()

    def set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    @on(Input.Submitted)
    def on_url_submitted(self, event: Input.Submitted) -> None:
        url = event.value.strip()
        if not url:
            return
        event.input.clear()
        self.set_status("Starting download...")
        self.download(url)

    @work(thread=True, exclusive=True)
    def download(self, url: str) -> None:
        # yt-dlp is blocking, so it runs in a thread; UI updates go through call_from_thread
        def on_progress(d: dict) -> None:
            if d["status"] != "downloading":
                return
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                self.call_from_thread(
                    self.set_status,
                    f"Downloading... {d['downloaded_bytes'] / total:.0%}"
                )

        options = {
            # A terminal can't show more than ~480p anyway; smaller files download faster
            "format": "b[height<=480]/bv*[height<=480]+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": str(DOWNLOADS / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": _SilentLogger(),
            "progress_hooks": [on_progress]
        }
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
        except DownloadError as error:
            self.call_from_thread(
                self.set_status, f"[red]Error:[/] {escape(str(error))}"
            )
            return

        path = info["requested_downloads"][0]["filepath"]
        self.call_from_thread(self.play, path, info.get("title", path))

    async def play(self, path: str, title: str) -> None:
        await self.query(VideoPlayer).remove()  # stop the previous video, if any
        player = VideoPlayer(
            path, skip_frames=True
        )  # skip_frames keeps video in sync with audio
        await self.mount(player, before=self.query_one(Footer))
        player.focus()
        self.set_status(escape(title))


if __name__ == "__main__":
    YouTubePlayerApp().run()
