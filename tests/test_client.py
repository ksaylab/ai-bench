import io
import json
import unittest
import urllib.error
from unittest import mock

from aibench import client

OK = json.dumps({"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode()


def answer():
    r = mock.MagicMock()
    r.__enter__.return_value = r
    r.headers = {"Content-Type": "application/json"}
    r.read.return_value = OK
    return r


def refused():
    return urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))


class TestReconnect(unittest.TestCase):
    """07/11: the ssh tunnel to a RunPod pod dropped twice mid-run. A lost connection is waited out for a while (the
    tunnel reopens), so one drop does not lose the case; a server error (HTTP 5xx) keeps the few attempts it had."""

    def chat(self, outcomes):
        sleeps = []
        with mock.patch.object(client.urllib.request, "urlopen", side_effect=outcomes), \
                mock.patch.object(client.time, "sleep", side_effect=sleeps.append):
            try:
                return client.chat("http://127.0.0.1:1/v1", "m", [{"role": "user", "content": "x"}]), sleeps
            except client.ClientError as e:
                return e, sleeps

    def test_a_lost_connection_is_waited_out(self):
        r, sleeps = self.chat([refused()] * 10 + [answer()])  # longer than the 3 attempts of a server error
        self.assertEqual(r["text"], "hi")
        self.assertLessEqual(sum(sleeps), client.RECONNECT_S)

    def test_a_connection_that_never_comes_back_gives_up(self):
        r, sleeps = self.chat([refused()] * 1000)
        self.assertIsInstance(r, client.ClientError)
        self.assertTrue(str(r).startswith("connection:"), r)
        self.assertGreaterEqual(sum(sleeps), client.RECONNECT_S)
        self.assertLess(sum(sleeps), client.RECONNECT_S + 30)

    def test_a_server_error_keeps_its_three_attempts(self):
        err = urllib.error.HTTPError("u", 503, "busy", {}, io.BytesIO(b""))
        r, sleeps = self.chat([err] * 1000)
        self.assertEqual(str(r), "HTTP 503")
        self.assertEqual(len(sleeps), 3)


if __name__ == "__main__":
    unittest.main()
