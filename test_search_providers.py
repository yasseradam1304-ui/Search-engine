import unittest
from urllib.parse import parse_qs, urlsplit

from search_providers import (
    ENGINES,
    build_result_script,
    build_search_url,
    is_web_address,
    parse_search_results,
)


class SearchProviderTests(unittest.TestCase):
    def test_builds_search_urls_for_every_engine(self):
        self.assertEqual(
            set(ENGINES),
            {
                "Google",
                "Brave",
                "DuckDuckGo",
                "Bing",
                "Ecosia",
                "Qwant",
                "Yahoo",
                "Startpage",
            },
        )
        for engine in ENGINES:
            with self.subTest(engine=engine):
                address = build_search_url("chiens", engine, "fr")
                parsed = urlsplit(address)
                self.assertEqual(parsed.scheme, "https")
                self.assertTrue(any(
                    "chiens" in values
                    for values in parse_qs(parsed.query).values()
                ))

    def test_defaults_to_google_and_supports_search_languages(self):
        french = build_search_url("voitures", language="fr")
        english = build_search_url("cars", "Google", "en")

        self.assertIn("google.com/search", french)
        self.assertEqual(parse_qs(urlsplit(french).query)["hl"], ["fr"])
        self.assertEqual(parse_qs(urlsplit(english).query)["hl"], ["en"])
        self.assertEqual(parse_qs(urlsplit(english).query)["gl"], ["US"])

    def test_search_terms_and_addresses_are_distinguished(self):
        self.assertFalse(is_web_address("chiens"))
        self.assertFalse(is_web_address("voitures électriques"))
        self.assertTrue(is_web_address("https://example.com/page"))
        self.assertTrue(is_web_address("www.example.com"))
        self.assertFalse(is_web_address("https://[broken"))

    def test_engine_dom_scripts_use_provider_specific_selectors(self):
        self.assertIn("a.l1", build_result_script("Brave"))
        self.assertIn("h3", build_result_script("Google"))
        self.assertIn("b_algo", build_result_script("Bing"))
        self.assertIn("result__a", build_result_script("DuckDuckGo"))

    def test_search_results_discard_invalid_and_duplicate_destinations(self):
        results = parse_search_results(
            [
                {
                    "title": "Dog guide",
                    "snippet": "Everything about dog care.",
                    "url": "https://example.com/dogs",
                },
                {
                    "title": "Script link",
                    "url": "javascript:alert(1)",
                },
                {
                    "title": "Duplicate link",
                    "url": "https://example.com/dogs",
                },
                {
                    "title": "Malformed URL",
                    "url": "https://example.com:invalid",
                },
                {"title": None, "url": "https://example.com/empty"},
            ]
        )
        self.assertEqual(
            results,
            [
                (
                    "Dog guide",
                    "https://example.com/dogs",
                    "Everything about dog care.",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
