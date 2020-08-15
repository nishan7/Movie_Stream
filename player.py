import os

from ezflix import yts
from opensubs import get_subs
from old.eztv import eztv


class Scrape():
    def __init__(
            self,
            query,
            media_type="tv",
            limit=20,
            sort_by="seeds",
            sort_order="desc",
            quality=None,
            minimum_rating=None,
            language="en",
            page=1,
            debug=False,
            cli_mode=False,
    ):
        self._torrents = []
        self._query = query
        self._media_type = media_type
        self._limit = limit
        self._sort_by = sort_by
        self._sort_order = sort_order
        self._quality = quality
        self._minimum_rating = minimum_rating
        self._language = language
        self._page = page
        self._debug = debug

    def torrent_info(self, val):
        if self._torrents is None or int(val) > len(self._torrents):
            return None
        for torrent in self._torrents:
            if torrent["id"] == int(val):
                return torrent
        return None

    def search(self):
        if self._media_type == "tv":
            self._torrents = eztv(
                self._query.replace(" ", "-").lower(),
                page=self._page,
                limit=self._limit,
                quality=self._quality,
                debug=self._debug,
            )
        elif self._media_type == "movie":
            self._torrents = yts(
                q=self._query,
                limit=self._limit,
                sort_by=self._sort_by,
                sort_order=self._sort_order,
                quality=self._quality,
                minimum_rating=self._minimum_rating,
                page=self._page,
                debug=self._debug,
            )


def peerflix(magnet_link, media_player, subtitles, remove, file_path):
    subtitles = (
        '--subtitles %s' % ' '.join(file_path) if subtitles and file_path is not None else ""
    )
    remove = "--remove" if remove else ""
    cmd = 'peerflix "%s" --%s %s %s -d' % (magnet_link, media_player, subtitles, remove)
    print("Executing " + cmd)
    os.system("start cmd /k {}".format(cmd))


def play(query, quality='1080p', media_type='movie'):
    e = Scrape(query=query, media_type=media_type, quality=quality)
    e.search()
    magnet = e.torrent_info(1)
    subs_file_path = get_subs(query)
    peerflix(magnet["link"], media_player='vlc', subtitles=True, remove=False, file_path=subs_file_path)

# if __name__ == '__main__':
