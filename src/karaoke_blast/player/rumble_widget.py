"""Embedded Rumble iframe player."""

from __future__ import annotations

import http.cookiejar
import logging

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkCookie
from PyQt6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInterceptor,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QWidget

from karaoke_blast.services.rumble_cookies import resolved_rumble_cookies_file

logger = logging.getLogger(__name__)

_WATCH_MODE = "__watch__"


class _RumbleRefererInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, referer: str = "https://rumble.com/") -> None:
        super().__init__()
        self._referer = referer.encode("ascii")

    def set_referer(self, referer: str) -> None:
        self._referer = referer.encode("ascii")

    def interceptRequest(self, info) -> None:
        host = info.requestUrl().host().lower()
        if "rumble.com" not in host and "cloudflare" not in host:
            return
        info.setHttpHeader(b"Referer", self._referer)


def _install_browser_cookies(profile: QWebEngineProfile) -> None:
    path = resolved_rumble_cookies_file()
    if path is None:
        return
    jar = http.cookiejar.MozillaCookieJar(str(path))
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except OSError as exc:
        logger.debug("Could not load cookies for Rumble WebEngine: %s", exc)
        return
    store = profile.cookieStore()
    for cookie in jar:
        if "rumble" not in cookie.domain:
            continue
        qcookie = QNetworkCookie(
            cookie.name.encode("utf-8"), cookie.value.encode("utf-8")
        )
        if cookie.domain:
            qcookie.setDomain(cookie.domain)
        qcookie.setPath(cookie.path or "/")
        store.setCookie(qcookie, QUrl("https://rumble.com"))


class RumbleWidget(QWebEngineView):
    playback_error = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        self._interceptor = _RumbleRefererInterceptor()
        profile = QWebEngineProfile("karaoke-blast-rumble", parent)
        _install_browser_cookies(profile)
        profile.setUrlRequestInterceptor(self._interceptor)
        page = QWebEnginePage(profile, parent)
        super().__init__(parent)
        self.setPage(page)
        self.setStyleSheet("background-color: black;")
        self.page().setBackgroundColor(self.palette().color(self.backgroundRole()))
        settings = self.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False
        )
        self._load_mode: str | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.page().loadFinished.connect(self._on_load_finished)

    def load_embed(self, embed_id: str, *, page_referer: str | None = None) -> None:
        self._load_mode = embed_id
        if page_referer:
            self._interceptor.set_referer(page_referer)
        else:
            self._interceptor.set_referer("https://rumble.com/")
        embed_url = f"https://rumble.com/embed/{embed_id}/"
        self.load(QUrl(embed_url))

    def load_watch_page(self, page_url: str) -> None:
        self._load_mode = _WATCH_MODE
        self._interceptor.set_referer(page_url)
        _install_browser_cookies(self.page().profile())
        self.load(QUrl(page_url))

    def clear(self) -> None:
        self._load_mode = None
        self.setHtml(
            "<!DOCTYPE html><html><body style='background:#000'></body></html>",
            QUrl("about:blank"),
        )

    def activate_playback(self) -> None:
        """Start or resume Rumble playback (WebEngine often needs a nudge after load)."""
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.page().runJavaScript(_PLAYBACK_JS)

    def pause_playback(self) -> None:
        self.page().runJavaScript(_PAUSE_JS)

    def toggle_playback(self) -> None:
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.page().runJavaScript(_TOGGLE_JS)

    def _on_load_finished(self, ok: bool) -> None:
        if self._load_mode is None:
            return
        if ok:
            self._schedule_playback_activation()
            return
        if self._load_mode == _WATCH_MODE:
            self.playback_error.emit(
                "Could not load the Rumble page. Refresh rumble.com cookies in Preferences."
            )
            return
        url = self.page().url().toString()
        if "/embed/" not in url:
            return
        self.playback_error.emit("Could not load the Rumble player.")

    def _schedule_playback_activation(self) -> None:
        QTimer.singleShot(150, self.activate_playback)
        QTimer.singleShot(600, self.activate_playback)


_PLAYBACK_JS = """
(function () {
  const video = document.querySelector("video");
  if (video) {
    const playPromise = video.play();
    if (playPromise && playPromise.catch) {
      playPromise.catch(function () {});
    }
    return;
  }
  const selectors = [
    ".rmp-play-pause",
    ".rmp-big-play",
    "[data-js='rumble-play']",
    "button[aria-label*='Play']",
    ".play-overlay",
  ];
  for (const sel of selectors) {
    const btn = document.querySelector(sel);
    if (btn) {
      btn.click();
      return;
    }
  }
  const el = document.elementFromPoint(
    Math.floor(window.innerWidth / 2),
    Math.floor(window.innerHeight / 2)
  );
  if (el) {
    el.click();
  }
})();
"""

_PAUSE_JS = """
(function () {
  const video = document.querySelector("video");
  if (video && !video.paused) {
    video.pause();
  }
})();
"""

_TOGGLE_JS = """
(function () {
  const video = document.querySelector("video");
  if (video) {
    if (video.paused) {
      const p = video.play();
      if (p && p.catch) p.catch(function () {});
    } else {
      video.pause();
    }
    return;
  }
  const el = document.elementFromPoint(
    Math.floor(window.innerWidth / 2),
    Math.floor(window.innerHeight / 2)
  );
  if (el) el.click();
})();
"""
