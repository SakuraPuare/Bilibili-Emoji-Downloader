import asyncio
import json
import pathlib
import re
import time
from itertools import chain
from typing import Union, Dict, List

import httpx
import tqdm.asyncio
from httpx import Response
from selenium import webdriver

download_folder = pathlib.Path(__file__).with_name('download')
filename_patten = re.compile(r'[\\/:*?\"<>|]')

if not download_folder.exists() and not download_folder.is_dir():
    download_folder.mkdir()

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;'
              'q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'cache-control': 'no-cache',
    'dnt': '1',
    'pragma': 'no-cache',
    'sec-ch-ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/123.0.0.0 Safari/537.36',
}
httpx_cookies = httpx.Cookies()
limit = asyncio.Semaphore(20)


def load_cookies():
    driver = webdriver.Chrome()
    # wait to load
    time.sleep(1)
    driver.get('https://passport.bilibili.com/account/security#/home')

    # 加载cookies
    cookies_path = pathlib.Path('cookies.json')
    if cookies_path.exists():
        with open(cookies_path, 'r') as f:
            cookies = f.read()
            cookies = json.loads(cookies)
            for cookie in cookies:
                driver.add_cookie(cookie)
        driver.get('https://passport.bilibili.com/account/security#/home')
    else:
        # 等待登录
        time.sleep(0.25)
        while driver.current_url != 'https://passport.bilibili.com/account/security#/home':
            time.sleep(0.5)

    # 读取并保存cookies
    cookies = driver.get_cookies()
    for cookie in cookies:
        httpx_cookies.set(name=cookie['name'], value=cookie['value'], domain=cookie['domain'], path=cookie['path'])

    with open('cookies.json', 'w') as f:
        f.write(json.dumps(cookies))
        f.close()

    driver.quit()


async def get(url: str, params: dict) -> Response:
    try:
        async with limit:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, params=params, cookies=httpx_cookies, headers=headers)
                return response
    except Exception as e:
        tqdm.tqdm.write(f'Error: {url} {e}')
        time.sleep(1)
        return await get(url, params)


async def download(url: str, emote_name: str, ids: str, filename: str) -> None:
    emote_type = '.' + url.split('.')[-1]
    emotes_folder = pathlib.Path.joinpath(download_folder, emote_name)

    if not emotes_folder.exists() and not emotes_folder.is_dir():
        emotes_folder.mkdir()

    if not url.startswith('http'):
        url = 'https://' + url.split('//')[-1]

    if len(re.findall(filename_patten, filename)) > 0:
        filename = re.sub(filename_patten, '', filename)

    download_path = pathlib.Path.joinpath(emotes_folder, f"{ids}-{filename}").with_suffix(emote_type)
    try:
        if not download_path.exists() and not download_path.is_file():
            response = await get(url, {})
            with open(download_path, 'wb') as fs:
                fs.write(response.content)
                fs.close()
        else:
            return
    except Exception as e:
        tqdm.tqdm.write(f'Error: {e} {url}')


# 获取表情列表
async def get_emote_list() -> Union[None, Dict[str, Union[str, Dict[str, str]]]]:
    url = 'https://api.bilibili.com/x/emote/setting/panel'
    params = {'business': 'reply'}
    response = await get(url, params)
    response = response.json()
    if response['code'] == 0:
        return response['data']['all_packages']
    else:
        tqdm.tqdm.write('error code:', response['code'])
        return None


async def get_emote_detail_list(data) -> List:
    id_list = [i.get('id') for i in data]
    url = 'https://api.bilibili.com/x/emote/package'

    params_list = [{'business': 'dynamic', 'ids': ','.join(map(str, id_list[i:i + 25]))} for i in
                   range(0, len(id_list), 25)]
    task_list = [asyncio.create_task(get(url, params)) for params in params_list]
    ret = await asyncio.gather(*task_list)
    # ret = process_map(partial(get, url), params_list[:10], chunksize=8)
    resp = [i.json().get('data', {}).get('packages', []) for i in ret]
    return list(chain(*resp))


async def download_emote_list() -> List:
    emote_list = await get_emote_list()
    emote_detail_list = await get_emote_detail_list(emote_list)
    # emote_list = asyncio.run(get_emote_list())
    # emote_detail_list = asyncio.run(get_emote_detail_list(emote_list))
    if emote_list is None:
        return []
    else:
        emote_tasks_list = []
        for emotes in emote_detail_list:
            emotes: Dict
            emotes_name = emotes.get('text')
            if emotes_name != '颜文字':
                if not emotes.get('emote'):
                    # This emoji was banned
                    continue
                for ids, emote in enumerate(emotes.get('emote')):
                    emote_name = emote['text']
                    if emote.get('gif_url'):
                        download_url = emote['gif_url']
                        task = [download_url, emotes_name, str(ids), emote_name]
                        emote_tasks_list.append(task)
                    if emote.get('url'):
                        download_url = emote['url']
                        task = [download_url, emotes_name, str(ids), emote_name]
                        emote_tasks_list.append(task)
                    else:
                        continue
        return emote_tasks_list


async def main():
    load_cookies()
    resp = await download_emote_list()
    task_list = []
    for i in resp:
        task_list.append(asyncio.create_task(download(*i)))

    # tqdm asyncio 显示进度
    for task in tqdm.asyncio.tqdm.as_completed(task_list):
        await task


if __name__ == '__main__':
    asyncio.run(main())
