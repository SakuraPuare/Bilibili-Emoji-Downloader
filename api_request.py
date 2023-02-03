import asyncio
import json
import pathlib
import re
import time
from typing import Union, Dict, List

import httpx
import tqdm.asyncio
from selenium import webdriver

download_folder = pathlib.Path(__file__).with_name('download')
filename_patten = re.compile(r'[\\/:*?\"<>|]')

if not download_folder.exists() and not download_folder.is_dir():
    download_folder.mkdir()

driver = webdriver.Chrome()
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
httpx_cookies = httpx.Cookies()
for cookie in cookies:
    httpx_cookies.set(name=cookie['name'], value=cookie['value'], domain=cookie['domain'], path=cookie['path'])

with open('cookies.json', 'w') as f:
    f.write(json.dumps(cookies))
    f.close()

driver.quit()


async def download(url: str, emote_name: str, ids: str, filename: str, sem: asyncio.Semaphore) -> None:
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
            async with sem:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, cookies=httpx_cookies)
                    with open(download_path, 'wb') as fs:
                        fs.write(response.content)
                        fs.close()
                await asyncio.sleep(0.5)
        else:
            return
    except Exception as e:
        print(e, url)
        return await download(url, emote_name, ids, filename)


# 获取表情列表
async def get_emote_list() -> Union[None, Dict[str, Union[str, Dict[str, str]]]]:
    url = 'https://api.bilibili.com/x/emote/setting/panel'
    params = {'business': 'reply'}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, cookies=httpx_cookies, params=params)
    response = response.json()
    if response['code'] == 0:
        return response['data']
    else:
        print('error code:', response['code'])
        return None


async def download_emote_list() -> List:
    emote_list = await get_emote_list()
    if emote_list is None:
        return []
    else:
        emote_list = emote_list['all_packages']
        emote_tasks_list = []
        for emotes in emote_list:
            emotes: Dict
            emotes_name = emotes.get('text')
            if emotes_name != '颜文字':
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
        # await download(download_url, emotes_name, ids, emote_name)
        # task = asyncio.create_task(download(download_url, emotes_name, str(ids), emote_name))
        # task = [download_url, emotes_name, str(ids), emote_name]
        # emote_tasks_list.append(task)


# async def download_emote_list() -> None:
# 	emote_list = await get_emote_list()
# 	if emote_list is None:
# 		return
# 	else:
# 		emote_list = emote_list['all_packages']
# 		emote_tasks_list = []
# 		for emotes in emote_list:
# 			emotes_name = emotes['text']
# 			if emotes_name != '颜文字':
# 				for ids, emote in enumerate(emotes['emote']):
# 					emote_name = emote['text']
# 					if emote.__contains__('gif_url'):
# 						download_url = emote['gif_url']
# 					elif emote.__contains__('url'):
# 						download_url = emote['url']
# 					else:
# 						continue
# 					# await download(download_url, emotes_name, ids, emote_name)
# 					task = asyncio.create_task(download(download_url, emotes_name, str(ids), emote_name))
# 					emote_tasks_list.append(task)
# 		await asyncio.wait(emote_tasks_list)


async def main():
    # data_file = pathlib.Path('raw.json')
    # if data_file.exists():
    #     file_time = datetime.datetime.fromtimestamp(os.stat(data_file).st_mtime)
    # else:
    #     file_time = datetime.datetime.fromtimestamp(0)
    # time_now = datetime.datetime.fromtimestamp(time.time())
    # if (time_now - file_time).days > 1:
    resp = await download_emote_list()
    #     with open(data_file, 'w', encoding='u8') as fw:
    #         json.dump(resp, fw, ensure_ascii=False)
    # else:
    #     with open(data_file, 'r', encoding='u8') as fr:
    #         resp = json.load(fr)
    task_list = []
    sem = asyncio.Semaphore(100)
    for i in resp:
        task_list.append(asyncio.create_task(download(*i, sem=sem)))

    # tqdm asyncio 显示进度
    for task in tqdm.asyncio.tqdm.as_completed(task_list):
        await task


if __name__ == '__main__':
    asyncio.run(main())
