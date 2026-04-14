from kitefs import hello


class TestHello:
    def test_returns_greeting_string(self):
        assert hello() == "Hello from kitefs!"
