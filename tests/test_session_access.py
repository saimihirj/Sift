import unittest

from fastapi import HTTPException

from backend.services.session_access import require_session_owner


class SessionAccessTests(unittest.TestCase):
    def test_matching_beta_key_can_open_session(self) -> None:
        require_session_owner({"user_identifier": "beta:founder:SIFTKEY"}, "BETA:FOUNDER:siftkey")

    def test_missing_or_different_beta_key_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as missing:
            require_session_owner({"user_identifier": "beta:founder:SIFTKEY"}, "")
        self.assertEqual(missing.exception.status_code, 403)

        with self.assertRaises(HTTPException) as different:
            require_session_owner({"user_identifier": "beta:founder:SIFTKEY"}, "beta:other:SIFTKEY")
        self.assertEqual(different.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
