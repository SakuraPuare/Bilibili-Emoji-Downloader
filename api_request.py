import asyncio
import json
import pathlib
import re
import time
from typing import Union, Dict

import httpx
from selenium import webdriver

download_folder = pathlib.Path(__file__).with_name('download')
filename_patten = re.compile(r'[\\/:*?\"<>|]')

if not download_folder.exists() and not download_folder.is_dir():
	download_folder.mkdir()
else:
	pass

driver = webdriver.Chrome()
driver.get('https://passport.bilibili.com/login')

# 加载cookies
cookies_path = pathlib.Path(__file__).with_name('cookies.json')
if cookies_path.exists():
	with open(cookies_path, 'r') as f:
		cookies = f.read()
		cookies = json.loads(cookies)
		for cookie in cookies:
			driver.add_cookie(cookie)
	driver.get('https://passport.bilibili.com/account/security#/home')
else:
	# 等待登录
	while driver.current_url == 'https://passport.bilibili.com/account/security#/home':
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
			async with httpx.AsyncClient() as client:
				response = await client.get(url)
				with open(download_path, 'wb') as fs:
					fs.write(response.content)
					fs.close()
		else:
			return
	except Exception as e:
		print(e, url)
		return await download(url, emote_name, ids, filename)

	pass


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
		return None


async def download_emote_list() -> None:
	emote_list = await get_emote_list()
	if emote_list is None:
		return
	else:
		emote_list = emote_list['all_packages']
		for emotes in emote_list:
			emotes_name = emotes['text']
			emote_tasks_list = []
			if emotes_name != '颜文字':
				for ids, emote in enumerate(emotes['emote']):
					emote_name = emote['text']
					if emote.__contains__('gif_url'):
						download_url = emote['gif_url']
					elif emote.__contains__('url'):
						download_url = emote['url']
					else:
						continue
					# await download(download_url, emotes_name, ids, emote_name)
					task = asyncio.create_task(download(download_url, emotes_name, str(ids), emote_name))
					emote_tasks_list.append(task)
				await asyncio.wait(emote_tasks_list)


async def main():
	await download_emote_list()
	pass


if __name__ == '__main__':
	asyncio.run(main())
