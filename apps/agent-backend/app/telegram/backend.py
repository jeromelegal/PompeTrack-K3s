from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class BackendClient:
    def __init__(self, *, base_url: str, api_key: str | None, timeout_seconds: int = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def latest_review(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/health-coach/reviews/latest")

    def list_reviews(self, *, limit: int = 20) -> list[dict[str, Any]]:
        data = self._request("GET", f"/api/v1/health-coach/reviews?limit={limit}")
        if isinstance(data, list):
            return data
        return []

    def review(self, review_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/health-coach/reviews/{urllib.parse.quote(review_id)}")

    def review_by_date_or_id(self, value: str) -> dict[str, Any]:
        item = value.strip()
        if not item:
            return self.latest_review()
        if item.startswith("health-review-"):
            return self.review(item)
        for review in self.list_reviews(limit=50):
            if review.get("review_date") == item or review.get("review_id") == item:
                review_id = review.get("review_id")
                if review_id:
                    return self.review(str(review_id))
        raise RuntimeError(f"Aucune revue trouvée pour {item}")

    def health_features(self, *, days: int = 30) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/health-coach/features?days={days}")

    def run_daily_review(self, *, days: int = 30, history_limit: int = 7) -> dict[str, Any]:
        query = urllib.parse.urlencode({"days": days, "store": "true", "history_limit": history_limit})
        return self._request("POST", f"/api/v1/health-coach/daily-review?{query}")

    def run_weekly_review(self, *, days: int = 90, history_limit: int = 7) -> dict[str, Any]:
        query = urllib.parse.urlencode({"days": days, "store": "true", "history_limit": history_limit})
        return self._request("POST", f"/api/v1/health-coach/weekly-review?{query}")

    def chat(self, *, prompt: str, session_id: str, user_id: str, model: str) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "session_id": session_id,
            "user": user_id,
        }
        data = self._request("POST", "/v1/chat/completions", payload=payload)
        choices = data.get("choices") or []
        if not choices:
            return "Je n'ai pas reçu de réponse exploitable du modèle."
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
        return _strip_agent_trace(content) or content or "Réponse vide du modèle."

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Backend HTTP {exc.code}: {raw}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Backend request failed: {exc}") from exc


def _strip_agent_trace(content: str) -> str:
    marker = "### Réponse finale"
    if marker not in content:
        return content.strip()
    return content.split(marker, 1)[1].strip()
