from igscraper.utils import normalize_hashtags


def test_normalize_hashtags():
    caption = "This is a #test post with #multiple #hashtags"
    assert normalize_hashtags(caption) == ['#test', '#multiple', '#hashtags']
