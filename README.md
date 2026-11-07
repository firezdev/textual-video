# textual-video
[![AI-DECLARATION: assist](https://img.shields.io/badge/䷼%20AI--DECLARATION-assist-fef9c3?labelColor=fef9c3)](https://ai-declaration.md)

Textual widget for playing videos in terminal UIs. Based on [textual-image](https://github.com/lnqs/textual-image).

![example](screenshots/example.png)

## Installation
```bash
uv add textual-video
```

## Example
```python
from textual_video import VideoPlayer
from textual.app import App, ComposeResult

class ExampleApp(App):
    def compose(self) -> ComposeResult:
        yield VideoPlayer('examples/video.mp4')

if __name__ == '__main__':
    ExampleApp().run()
```
