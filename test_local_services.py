import unittest

from local_services import build_ollama_messages, parse_commons_images


class LocalServiceTests(unittest.TestCase):
    def test_commons_image_results_include_thumbnail_and_license_attribution(self):
        results = parse_commons_images(
            {
                "query": {
                    "pages": {
                        "2": {
                            "index": 2,
                            "title": "File:Dog portrait.jpg",
                            "imageinfo": [
                                {
                                    "thumburl": "https://thumb.wikimedia.org/dog.jpg",
                                    "descriptionurl": (
                                        "https://commons.wikimedia.org/wiki/"
                                        "File:Dog_portrait.jpg"
                                    ),
                                    "extmetadata": {
                                        "Artist": {
                                            "value": (
                                                '<a href="/wiki/User:Alice">'
                                                "Alice"
                                                "</a>"
                                            )
                                        },
                                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                        "LicenseUrl": {
                                            "value": "https://creativecommons.org/licenses/by-sa/4.0"
                                        },
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Dog portrait.jpg")
        self.assertEqual(results[0]["attribution"], "Alice")
        self.assertEqual(results[0]["license"], "CC BY-SA 4.0")

    def test_local_ai_prompt_uses_sources_and_treats_web_text_as_untrusted(self):
        messages = build_ollama_messages(
            "chiens",
            [
                (
                    "Dog care",
                    "https://example.com/dogs",
                    "Dogs need fresh water.",
                )
            ],
            "Quels sont leurs besoins ?",
        )

        self.assertIn("non fiables", messages[0]["content"])
        english_messages = build_ollama_messages(
            "dogs",
            [("Dog care", "https://example.com/dogs", "Water.")],
            "Summarize",
            language="en",
        )
        self.assertIn("anglais", english_messages[0]["content"])
        self.assertIn("https://example.com/dogs", messages[1]["content"])
        self.assertIn("Quels sont leurs besoins", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
