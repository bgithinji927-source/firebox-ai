import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.main import chunk_pages, extract_document, owner_id


class ProcessingTests(unittest.TestCase):
    def test_plain_text_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.txt"
            path.write_text("A real text document for extraction.", encoding="utf-8")
            pages = extract_document(path, ".txt")
        self.assertEqual(pages, [{"page": None, "text": "A real text document for extraction."}])

    def test_chunking_preserves_source_page_and_covers_text(self):
        text = "alpha beta " * 120
        chunks = chunk_pages([{"page": 4, "text": text}], size=240, overlap=32)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk["page"] == 4 for chunk in chunks))
        self.assertTrue(all(chunk["text"] for chunk in chunks))
        self.assertIn("alpha", " ".join(chunk["text"] for chunk in chunks))

    def test_owner_header_is_ignored(self):
        os.environ["FIREBOX_OWNER_ID"] = "workspace-owner"
        self.assertEqual(owner_id("attacker-selected-owner"), "workspace-owner")

    def test_workspace_requires_credentials_but_health_is_public(self):
        with patch.dict(os.environ, {"APP_USERNAME": "test-user", "APP_PASSWORD": "test-password"}):
            client = TestClient(app)
            self.assertEqual(client.get("/api/health").status_code, 200)
            self.assertEqual(client.get("/").status_code, 401)
            self.assertEqual(client.get("/api/conversations").status_code, 401)
            self.assertEqual(client.get("/", auth=("test-user", "test-password")).status_code, 200)


if __name__ == "__main__":
    unittest.main()
