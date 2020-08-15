import io
import json
import os
import zipfile
import requests
import requests_cache

requests_cache.install_cache('cache')


def download(link):
    r = requests.get(link)
    zip = zipfile.ZipFile(io.BytesIO(r.content))
    for name in zip.namelist():
        if name.endswith('srt'):
            zip.extractall(path=os.path.abspath('./cmd/'))
            try:
                os.rename(os.path.abspath('./cmd/' + name), os.path.abspath('./cmd/' + name.replace(' ', '_')))
            except FileExistsError:
                pass
            return os.path.abspath('./cmd/' + name.replace(' ', '_'))


# Downlaod subtitles for the imdbd-id, can download more than 1 mores subtitles
def get_subs(imdb_id='tt1375666'):
    headers = {'User-Agent': 'nishanpaudel'}
    r = requests.get('https://rest.opensubtitles.org/search/imdbid-{}/sublanguageid-eng'.format(imdb_id),
                     headers=headers)

    response = json.loads(r.text)

    links = []
    for i in range(min(1, len(response))):
        links.append(response[i]['ZipDownloadLink'])

    if not links:
        return None

    subs = ['"' + download(link) + '"' for link in links]
    return subs

# print(get_subs('tt1022603'))

#
