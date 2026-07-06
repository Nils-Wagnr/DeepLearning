"""Capture reproducible ClaimGuard demo frames from the real Streamlit UI.

The script starts a private Streamlit server and a headless Chromium instance,
drives the RQ5 upload and model comparison through the Chrome DevTools Protocol,
and writes presentation-ready PNG frames plus an animated GIF.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image
from websockets.sync.client import connect


ROOT = Path(__file__).resolve().parents[3]
PRESENTATION_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PRESENTATION_ROOT / "assets"
OUTPUT_DIR = ASSETS_DIR / "demo_frames"
GIF_OUTPUT = ASSETS_DIR / "ClaimGuard_UI_Demo.gif"
REPORT = ROOT / "data" / "reports" / "NW2_RQ5_Report.pdf"
PORT = 8511
DEBUG_PORT = 9223
CHROME_CANDIDATES = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
)


class CDP:
    """Minimal synchronous Chrome DevTools Protocol client."""

    def __init__(self, websocket_url: str) -> None:
        self.socket = connect(websocket_url, origin=f"http://localhost:{DEBUG_PORT}")
        self.message_id = 0

    def close(self) -> None:
        self.socket.close()

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.message_id += 1
        message_id = self.message_id
        self.socket.send(
            json.dumps({"id": message_id, "method": method, "params": params or {}})
        )
        while True:
            response = json.loads(self.socket.recv())
            if response.get("id") != message_id:
                continue
            if "error" in response:
                raise RuntimeError(f"CDP {method} failed: {response['error']}")
            return response.get("result", {})

    def evaluate(self, expression: str) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        return result.get("result", {}).get("value")


def wait_for(check, description: str, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for {description}")


def click_text(cdp: CDP, text: str) -> None:
    encoded = json.dumps(text)
    expression = f"""
    (() => {{
      const wanted = {encoded};
      const nodes = [...document.querySelectorAll('button, label, [role="tab"]')];
      const element = nodes.find(node => node.innerText && node.innerText.trim() === wanted)
        || nodes.find(node => node.innerText && node.innerText.includes(wanted));
      if (!element) return false;
      element.scrollIntoView({{block: 'center'}});
      element.click();
      return true;
    }})()
    """
    wait_for(lambda: bool(cdp.evaluate(expression)), f"clickable text {text!r}", 30)


def scroll_to_text(cdp: CDP, text: str, offset: int = -80) -> None:
    encoded = json.dumps(text)
    expression = f"""
    (() => {{
      const wanted = {encoded};
      const nodes = [...document.querySelectorAll('h1,h2,h3,h4,h5,p,div,button')];
      const element = nodes.find(node => {{
        const rect = node.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && node.innerText && node.innerText.includes(wanted);
      }});
      if (!element) return false;
      element.scrollIntoView({{block: 'start', behavior: 'instant'}});
      window.scrollBy({{top: {offset}, behavior: 'instant'}});
      return true;
    }})()
    """
    wait_for(lambda: bool(cdp.evaluate(expression)), f"text {text!r}", 30)
    time.sleep(0.7)


def capture(cdp: CDP, name: str) -> Path:
    result = cdp.call(
        "Page.captureScreenshot",
        {"format": "png", "fromSurface": True, "captureBeyondViewport": False},
    )
    path = OUTPUT_DIR / f"{name}.png"
    path.write_bytes(base64.b64decode(result["data"]))
    return path


def set_upload(cdp: CDP, path: Path) -> None:
    document = cdp.call("DOM.getDocument", {"depth": -1, "pierce": True})
    root_id = document["root"]["nodeId"]
    query = cdp.call(
        "DOM.querySelector", {"nodeId": root_id, "selector": 'input[type="file"]'}
    )
    node_id = query.get("nodeId")
    if not node_id:
        raise RuntimeError("Streamlit file input was not found")
    cdp.call("DOM.setFileInputFiles", {"nodeId": node_id, "files": [str(path.resolve())]})


def build_gif(frames: list[Path]) -> None:
    images = [Image.open(frame).convert("RGB") for frame in frames]
    durations = [3000, 5000, 4000, 8000]
    images[0].save(
        GIF_OUTPUT,
        save_all=True,
        append_images=images[1:],
        duration=durations[: len(images)],
        loop=0,
        optimize=True,
    )


def main() -> None:
    chrome = next((path for path in CHROME_CANDIDATES if path.exists()), None)
    if chrome is None:
        raise FileNotFoundError("Chrome or Edge was not found")
    if not REPORT.exists():
        raise FileNotFoundError(REPORT)

    resolved_output = OUTPUT_DIR.resolve()
    expected_parent = ASSETS_DIR.resolve()
    if resolved_output.parent != expected_parent or resolved_output.name != "demo_frames":
        raise RuntimeError(f"Refusing to replace unexpected output directory: {resolved_output}")
    if resolved_output.exists():
        shutil.rmtree(resolved_output)
    OUTPUT_DIR.mkdir(parents=True)
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    with tempfile.TemporaryDirectory(prefix="claimguard-browser-") as profile:
        streamlit = subprocess.Popen(
            [
                str(ROOT / ".venv" / "Scripts" / "streamlit.exe"),
                "run",
                str(ROOT / "apps" / "streamlit_app.py"),
                "--server.headless=true",
                f"--server.port={PORT}",
                "--server.fileWatcherType=none",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=hidden,
        )
        browser = None
        cdp = None
        try:
            wait_for(
                lambda: _url_available(f"http://localhost:{PORT}/_stcore/health"),
                "Streamlit server",
                60,
            )
            browser = subprocess.Popen(
                [
                    str(chrome),
                    "--headless=new",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--remote-allow-origins=*",
                    f"--remote-debugging-port={DEBUG_PORT}",
                    f"--user-data-dir={profile}",
                    "--window-size=1600,900",
                    f"http://localhost:{PORT}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=hidden,
            )
            wait_for(
                lambda: bool(_debug_pages()),
                "Chromium debugging endpoint",
                30,
            )
            page = next(item for item in _debug_pages() if item.get("type") == "page")
            cdp = CDP(page["webSocketDebuggerUrl"])
            for domain in ("Page.enable", "Runtime.enable", "DOM.enable"):
                cdp.call(domain)
            cdp.call(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False},
            )
            wait_for(
                lambda: bool(cdp.evaluate("document.body.innerText.includes('ClaimGuard')")),
                "ClaimGuard UI",
                60,
            )

            click_text(cdp, "Datei hochladen")
            wait_for(
                lambda: bool(cdp.evaluate("!!document.querySelector('input[type=file]')")),
                "file input",
                20,
            )
            set_upload(cdp, REPORT)
            wait_for(
                lambda: bool(cdp.evaluate("document.body.innerText.includes('NW2_RQ5_Report.pdf')")),
                "uploaded filename",
                20,
            )
            frames = [capture(cdp, "01_upload")]

            click_text(cdp, "Dokument analysieren")
            wait_for(
                lambda: bool(cdp.evaluate("document.body.innerText.includes('Ergebnis für NW2_RQ5_Report.pdf')")),
                "document analysis",
                180,
            )
            time.sleep(1)
            frames.append(capture(cdp, "02_overview"))

            click_text(cdp, "Modellvergleich")
            scroll_to_text(cdp, "Automatischer Modellvergleich")
            frames.append(capture(cdp, "04_comparison_setup"))

            click_text(cdp, "Ausgewählte Modelle automatisch vergleichen")
            wait_for(
                lambda: bool(cdp.evaluate("document.body.innerText.includes('Übersicht je Backend')")),
                "model comparison",
                240,
            )
            scroll_to_text(cdp, "Übersicht je Backend")
            frames.append(capture(cdp, "05_comparison_summary"))
            build_gif(frames)
            print(f"Created {len(frames)} frames in {OUTPUT_DIR}")
            print(f"Created {GIF_OUTPUT}")
        finally:
            if cdp is not None:
                cdp.close()
            if browser is not None:
                browser.terminate()
                browser.wait(timeout=10)
            streamlit.terminate()
            streamlit.wait(timeout=10)


def _url_available(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


def _debug_pages() -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(
            f"http://localhost:{DEBUG_PORT}/json/list", timeout=1
        ) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return []


if __name__ == "__main__":
    main()
