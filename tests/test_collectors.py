from collectors.base import BaseCollector
from models import RawItem, SourceType


def test_base_collector_is_abstract():
    try:
        BaseCollector(config={})
        assert False, "Should not be instantiable"
    except TypeError:
        pass


def test_collector_subclass():
    class DummyCollector(BaseCollector):
        @property
        def source_name(self) -> str:
            return "dummy"

        async def collect(self) -> list[RawItem]:
            return [
                RawItem(
                    title="Test",
                    url="https://example.com",
                    source_type=SourceType.BLOG,
                )
            ]

    c = DummyCollector(config={})
    assert c.source_name == "dummy"
    assert isinstance(c.config, dict)
