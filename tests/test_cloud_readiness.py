import unittest
from unittest.mock import patch

from backend.api import auth as auth_routes
from backend.schemas import StartSessionRequest
from backend.services import auth
from backend.services.model_router import _ollama_payload, _profile_config_for_provider, active_provider, provider_catalog


class CloudReadinessTests(unittest.TestCase):
    def test_start_session_accepts_vertex_provider(self) -> None:
        payload = StartSessionRequest(provider="vertex", model="gemini-2.5-flash")

        self.assertEqual(payload.provider, "vertex")

    def test_start_session_accepts_local_openai_provider(self) -> None:
        payload = StartSessionRequest(provider="local_openai", model="Qwen/Qwen3-8B")

        self.assertEqual(payload.provider, "local_openai")

    def test_auth_catalog_includes_supported_oauth_providers(self) -> None:
        original_registered = auth._REGISTERED
        auth._REGISTERED = False
        try:
            providers = auth.auth_provider_catalog()
        finally:
            auth._REGISTERED = original_registered

        self.assertEqual([provider["key"] for provider in providers], ["google", "apple", "linkedin", "x"])
        self.assertTrue(all("configured" in provider for provider in providers))

    def test_oauth_callback_url_prefers_clean_public_frontend(self) -> None:
        class Request:
            def url_for(self, *_args, **_kwargs):
                raise AssertionError("SIFT_FRONTEND_URL should provide the callback host")

        with patch.dict("os.environ", {"SIFT_FRONTEND_URL": "https://sift-vc.web.app/"}, clear=False):
            callback_url = auth_routes._oauth_callback_url(Request(), "google")

        self.assertEqual(callback_url, "https://sift-vc.web.app/api/auth/callback/google")

    def test_oauth_callback_url_falls_back_to_request_url_for_local_dev(self) -> None:
        class Request:
            def url_for(self, route_name, provider):
                self.route_name = route_name
                self.provider = provider
                return "http://testserver/api/auth/callback/linkedin"

        request = Request()
        with patch.dict("os.environ", {"SIFT_FRONTEND_URL": ""}, clear=False):
            callback_url = auth_routes._oauth_callback_url(request, "linkedin")

        self.assertEqual(callback_url, "http://testserver/api/auth/callback/linkedin")
        self.assertEqual(request.route_name, "auth_callback")
        self.assertEqual(request.provider, "linkedin")

    def test_cloud_provider_catalog_hides_ollama_and_marks_vertex_ready(self) -> None:
        with patch.dict("os.environ", {"SIFT_ENABLE_OLLAMA": "false", "SIFT_ENABLE_LOCAL_OPENAI": "false", "SIFT_GCP_PROJECT_ID": "sift-495116"}, clear=False):
            providers = provider_catalog()
            keys = [provider["key"] for provider in providers]

        self.assertNotIn("ollama", keys)
        self.assertNotIn("local_openai", keys)
        vertex = next(provider for provider in providers if provider["key"] == "vertex")
        self.assertTrue(vertex["serverConfigured"])

    def test_local_openai_catalog_is_key_free_when_enabled(self) -> None:
        with patch.dict("os.environ", {"SIFT_ENABLE_LOCAL_OPENAI": "true"}, clear=False):
            providers = provider_catalog()
            local = next(provider for provider in providers if provider["key"] == "local_openai")

        self.assertFalse(local["requiresApiKey"])
        self.assertTrue(local["serverConfigured"])
        self.assertTrue(local["modelPresets"])

    def test_active_provider_uses_vertex_when_ollama_disabled_on_gcp(self) -> None:
        with patch.dict("os.environ", {"SIFT_ENABLE_OLLAMA": "false", "SIFT_GCP_PROJECT_ID": "sift-495116"}, clear=False):
            self.assertEqual(active_provider(), "vertex")

    def test_local_ollama_payload_keeps_model_warm_and_caps_fast_profile(self) -> None:
        with patch.dict(
            "os.environ",
            {"OLLAMA_KEEP_ALIVE": "10m", "OLLAMA_NUM_CTX_SPEED": "4096", "OLLAMA_MAX_TOKENS_SPEED": "180"},
            clear=False,
        ):
            profile = _profile_config_for_provider("ollama", "speed")
            payload = _ollama_payload("system", [{"role": "user", "content": "hello"}], profile, stream=True)

        self.assertEqual(payload["keep_alive"], "10m")
        self.assertEqual(payload["options"]["num_ctx"], 4096)
        self.assertEqual(payload["options"]["num_predict"], 180)


if __name__ == "__main__":
    unittest.main()
