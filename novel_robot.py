#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""A web robot that is used to collect and download novels."""

import json
import os
import re
import sys
import threading
import traceback
import urllib.parse
import requests
from bs4 import BeautifulSoup
from bs4 import SoupStrainer

__author__ = 'EternalPhane'
__copyright__ = 'Copyright (c) 2016 EternalPhane'
__license__ = 'MIT'
__version__ = '0.0.1'
__maintainer__ = 'EternalPhane'
__email__ = 'eternalphane@gmail.com'
__status__ = 'Prototype'


def main(argv):
    """Main function."""
    global HEADERS, VERBOSE, SITES, SITE_ID
    HEADERS = {
        'Connection': 'Keep-Alive',
        'Accept': 'text/html,application/xhtml+xml,*/*',
        'Accept-Language': 'en-US,en;q=0.8,zh-Hans-CN;q=0.5,zh-Hans;q=0.3',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/51.0.2704.63 Safari/537.36'
        )
    }
    VERBOSE = False
    SITE_ID = 0
    process_argv(argv)
    with open('sites.list', 'r') as file:
        SITES = json.load(file)
    site = SITES[SITE_ID]
    title = '剑道真解'

    global RE_BAIDU_URL, RE_URL, RE_TITLE, RE_CONTENTS, RE_CHAPTER
    RE_BAIDU_URL = re.compile(
        r'<a[\w\W]+?data-click[\w\W]+?href = "(http[^@\r\n]+?)"[\w\W]+?<em>([^<>]+?)</em>.+</a>'
    )
    RE_URL = re.compile(r'^(http[s]?://%s|[^h])[^()<>]+$' % (site))
    RE_TITLE = re.compile(r'^[《 ]?%s[》 ]?' % (title))
    RE_CONTENTS = re.compile(r'.*?(目录|阅读).*?')
    RE_CHAPTER = re.compile(r'[第]?[序一二三四五六七八九十百千0-9]+[章节 ].+?')

    global LIST_TAG_TITLE
    LIST_TAG_TITLE = ['p', 'span', 'h1', 'h2', 'h3']

    global STRAINER_URL, STRAINER_TEXT
    STRAINER_URL = SoupStrainer('a', href=RE_URL)
    STRAINER_TEXT = SoupStrainer(['div', 'p', 'span', 'h1', 'h2', 'h3'])

    contents_url = locate_contents(site, title)
    if not contents_url:
        print('"%s" not found on %s.' % (title, site))
        return
    print('contents page of "%s": %s' % (title, contents_url['url']))
    print('generating contents...')
    contents = get_contents(contents_url['url'], contents_url['html'])
    print('capturing...')
    capture_to_file(title, contents)
    print('finished! path: %s.txt' % (os.path.dirname(__file__) + title))


def process_argv(argv):
    """Processes argv."""
    argc = len(argv)
    i = 1
    while i < argc:
        if argv[i] == '-v':
            global VERBOSE
            VERBOSE = True
        if argv[i] == '--site_id':
            i += 1
            global SITE_ID
            SITE_ID = int(argv[i])
        i += 1


def get_request(url, rash=False):
    """Wrapper for requests.get()."""
    resp = requests.get(url, headers=HEADERS)
    if resp.encoding == 'ISO-8859-1':
        encodings = None
        if not rash:
            encodings = requests.utils.get_encodings_from_content(
                resp.content[:1024].decode('ISO-8859-1')
            )
        if encodings:
            resp.encoding = encodings[0]
        else:
            resp.encoding = resp.apparent_encoding
    return resp


def get_true_url(url, base_url=None):
    """Gets the redirected or absolute url of given url."""
    if base_url:
        return urllib.parse.urljoin(base_url, url)
    try:
        return requests.head(url, headers=HEADERS, allow_redirects=True, timeout=5).url
    except requests.exceptions.Timeout:
        return url


def draw_progress(progress, bar_length=20):
    """Draws a progress bar.
    """
    length = int(progress * bar_length / 100 + 0.5)
    print('\r[%s%s] %.2f%% ' % ('=' * length, ' ' * (bar_length-length), progress), end='')


def locate_contents(site, title, max_depth=3):
    """Locates the contents page of specific novel.

    Searches the url of specific novel`s contents page according to its title on given website.

    Args:
      site: A string contains the url of website.
      title: A string contains the title of novel.
      max_depth: An int defines the max depth for dfs.

    Returns:
      A dict contains the url, html source and encoding of specific novel`s contents page, None if
      specific novel not found.
    """
    url = requests.head(
        'https://www.baidu.com/s',
        headers=HEADERS,
        allow_redirects=True,
        params={'wd': '%s site:%s' % (title, site)}
    ).url
    visited = set([url])
    queue = []
    print('depth: 0    analyzing <-- %s' % (url))
    depth = 1
    resp = get_request(url)
    for url in RE_BAIDU_URL.findall(resp.text):
        try:
            url = [x for x in url]
            url[0] = get_true_url(url[0])
            if RE_TITLE.match(url[1]):
                contents_url = check_contents_url(url[0], visited)
                if contents_url:
                    return contents_url
            if url[0] not in visited:
                queue.insert(0, url[0])
                visited.add(url[0])
                if VERBOSE:
                    print('appending to queue --> %s' % (url[0]))
        except:
            traceback.print_exc()
            continue
    while queue:
        url = queue.pop()
        if url == '':
            depth -= 1
            continue
        print('depth: %d    analyzing <-- %s' % (depth, url))
        resp = get_request(url)
        if 'html' not in resp.headers['Content-Type']:
            continue
        urls = []
        soup = BeautifulSoup(
            resp.content,
            'html.parser',
            from_encoding=resp.encoding,
            parse_only=STRAINER_URL
        )
        for url in soup('a'):
            try:
                url['href'] = get_true_url(url['href'], resp.url)
                if RE_TITLE.match(url.text):
                    contents_url = check_contents_url(url['href'], visited)
                    if contents_url:
                        return contents_url
                if url['href'] not in visited and depth < max_depth:
                    urls.insert(0, url['href'])
                    visited.add(url['href'])
                    if VERBOSE:
                        print('appending to queue --> %s' % (url['href']))
            except:
                traceback.print_exc()
                continue
        queue.append('')
        queue.extend(urls)
        depth += 1


def check_contents_url(url, visited):
    """Checks if a url refers to the contents page of specific novel.

    Checks whether a url refers to specific novel`s contents page, description page or any other
    page. If it refers to the description page, search for the url of the novel`s contents page on
    the description page.

    Args:
      resp: A string contains the url.
      visited: A set contains visited urls.

    Returns：
      A dict contains the url and html source of specific novel`s contents page, None if the url
      refers to any other page. The encoding of html source is utf-8.
      {
          'url': url,
          'html': html_source
      }
    """
    resp = get_request(url)
    if 'html' not in resp.headers['Content-Type']:
        return None
    soup = BeautifulSoup(resp.content, 'html.parser', from_encoding=resp.encoding)
    str_title = soup.find(LIST_TAG_TITLE, text=RE_TITLE)
    if str_title:
        urls = soup('a', href=RE_URL)
        chapter_num = 0
        for url in urls:
            if re.search(RE_CHAPTER, url.text):
                chapter_num += 1
            if chapter_num > 10:
                return {
                    'url': resp.url,
                    'html': str(soup)
                }
        contents_url = None
        for url in urls:
            if re.search(RE_CONTENTS, url.text):
                contents_url = url['href']
                break
        if contents_url:
            contents_url = get_true_url(contents_url, resp.url)
            if contents_url not in visited:
                visited.add(contents_url)
                return check_contents_url(contents_url, visited)
    return None


def get_contents(url, html):
    """Gets the contents of a novel.

    Generates a list contains the contents and the urls refer to the chapters of specific novel.

    Args:
      url: A string contains the url of specific novel`s contents page
      html: A string contains the html source of specific novel`s contents page.

    Returns:
      A list contains several tuples whoes first elem is the chapter name and second elem is the
      url refer to the chapter.
    """
    contents = []
    contents_url = url
    soup = BeautifulSoup(html, 'html.parser', from_encoding='utf-8', parse_only=STRAINER_URL)
    urls = soup('a', text=RE_CHAPTER)
    total = len(urls)
    generated = 0
    for url in urls:
        contents.append((url.text, get_true_url(url['href'], contents_url)))
        generated += 1
        draw_progress(generated / total * 100)
    print()
    return contents


def capture_to_file(title, contents, max_threads=50):
    """Captures the novel to file.

    Args:
      title: A string contains the title of the novel.
      contents: A list contains the contents of the novel, generated by get_contents.
      max_threads: An int defines the max number of capture threads.
    """
    # TODO: make the captured file name customizable
    total = len(contents)
    finished = 0
    thread_arr = []
    thread_event = threading.Event()
    thread_event.set()
    thread_num = [0]
    lock = threading.Lock()

    def _make_soup(index, ready):
        resp = get_request(contents[index][1])
        soup = BeautifulSoup(
            resp.content,
            'html.parser',
            from_encoding=resp.encoding,
            parse_only=STRAINER_TEXT
        )
        for tag in soup(['script', 'style', 'a']):
            tag.extract()
        contents[index] = (contents[index][0], soup)
        ready.set()
        lock.acquire()
        try:
            thread_num[0] -= 1
        finally:
            lock.release()
        if thread_num[0] < max_threads:
            thread_event.set()
        else:
            thread_event.clear()

    def _run_thread():
        i = 0
        while i < max_threads and i < total:
            thread_arr[i][0].start()
            i += 1
        thread_num[0] += i
        for thread in thread_arr[i:]:
            thread_event.wait()
            thread[0].start()
            thread_num[0] += 1

    for i in range(total):
        ready = threading.Event()
        thread_arr.append((threading.Thread(target=_make_soup, args=(i, ready)), ready))
    threading.Thread(target=_run_thread).start()
    with open(title + '.txt', 'w', encoding='utf-8') as file:
        while finished < total:
            thread_arr[finished][1].wait()
            file.write(contents[finished][0])
            file.write('\r\n')
            soup = contents[finished][1]
            for line in soup.stripped_strings:
                if len(line) < 4:
                    continue
                file.write(line)
                file.write('\r\n')
            file.write('\r\n')
            file.flush()
            finished += 1
            draw_progress(finished * 100 / total)
    print()


if __name__ == '__main__':
    main(sys.argv)
