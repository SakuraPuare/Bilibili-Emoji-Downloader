import asyncio
import json
import pathlib
import re
import time

import httpx
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

TIMEOUT = 30
HEADER = {
	'authority': 'i0.hdslb.com',
	'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
	'accept-language': 'zh-CN,zh;q=0.9',
	'cache-control': 'max-age=0',
	'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
	'sec-ch-ua-mobile': '?0',
	'sec-ch-ua-platform': '"Windows"',
	'sec-fetch-dest': 'document',
	'sec-fetch-mode': 'navigate',
	'sec-fetch-site': 'none',
	'sec-fetch-user': '?1',
	'upgrade-insecure-requests': '1',
	'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/103.0.0.0Safari/537.36',
}
URL_RE = re.compile(r'//\S*\"')
LIMITS = httpx.Limits(max_keepalive_connections=5, max_connections=10)


def mkdir(folder: str) -> None:
	folder = download_folder / folder
	if not (folder.exists() and folder.is_dir()):
		folder.mkdir()


async def download(dir_name: str, url: str, ids: int, emoji_name: str, types: str) -> None:
	try:
		save_name: str = f"{ids}-{emoji_name}.{types}"
		complete_path = download_folder / dir_name / save_name
		if not complete_path.exists():
			async with httpx.AsyncClient(limits=LIMITS, timeout=30) as client:
				res = await client.get(url, headers=HEADER)
				with open(complete_path, "wb") as fs:
					fs.write(res.content)
					fs.close()
	except:
		await download(dir_name, url, ids, emoji_name, types)
		pass


driver = webdriver.Chrome()
driver.get('https://passport.bilibili.com/login')

# 创建下载文件夹
download_folder = pathlib.Path(__file__).with_name('download')
up_download_folder = download_folder / '主播大表情'
folder_list = [download_folder, up_download_folder]

for i in folder_list:
	if not (i.exists() and i.is_dir()):
		i.mkdir()
	else:
		pass

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
	time.sleep(0.25)
	while driver.current_url != 'https://passport.bilibili.com/account/security#/home':
		time.sleep(0.5)

# 读取并保存cookies
cookies = driver.get_cookies()
with open('cookies.json', 'w') as f:
	f.write(json.dumps(cookies))
	f.close()

# 获取用户uid
driver.get('https://space.bilibili.com/')
while driver.current_url == 'https://space.bilibili.com':
	time.sleep(0.5)
uid = driver.current_url.split('/')[-1]

# 获取表情名称
driver.get('https://space.bilibili.com/281130859/dynamic')
name_list = []
try:
	WebDriverWait(driver, TIMEOUT).until(
		ec.presence_of_element_located((By.CLASS_NAME, 'bili-dyn-list__item')))
	driver.find_elements(By.CLASS_NAME, 'comment')[0].click()
	WebDriverWait(driver, TIMEOUT).until(
		ec.presence_of_element_located((By.CLASS_NAME, 'comment-emoji')))
	driver.find_elements(By.CLASS_NAME, 'comment-emoji')[0].click()
	WebDriverWait(driver, TIMEOUT).until(
		ec.presence_of_element_located((By.CLASS_NAME, 'emoji-box')))
	emoji_list = driver.find_elements(By.CLASS_NAME, 'tab-link')
	for num, ele in enumerate(emoji_list):
		if num % 5 == 0 and num != 0:
			driver.find_element(
				By.XPATH,
				'/html/body/div[2]/div[4]/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[2]/div[2]/div[4]/div[2]/span[2]').click()
		ele.click()
		driver.implicitly_wait(0.5)
		name = driver.find_element(By.CLASS_NAME, 'emoji-title').text
		name_list.append(name)
except TimeoutException:
	print('Loading time out')
	driver.quit()
	exit()

# 获取表情链接
driver.get('https://message.bilibili.com/#/whisper/mid281130859')
try:
	WebDriverWait(driver, TIMEOUT).until(
		ec.presence_of_element_located((By.CLASS_NAME, 'emotion-btn-box')))
	driver.find_elements(By.CLASS_NAME, 'emotion-btn-box')[0].click()
	WebDriverWait(driver, TIMEOUT).until(
		ec.presence_of_element_located((By.CLASS_NAME, 'content-ctnr')))
	emoji_list = driver.find_elements(
		By.CLASS_NAME, 'emoji-cover')
	dom_list = []
	for num, ele in enumerate(emoji_list):
		if num % 6 == 0 and num != 0:
			driver.find_element(
				By.XPATH,
				'/html/body/div[3]/div/div[1]/div[2]/div[2]/div[1]/div/div/div[4]/div[1]/div[4]/div[1]/div[2]' +
				'/div/div/div[3]/div[2]/div/span[2]').click()
		ele.click()
		time.sleep(0.8)
		dom = driver.find_element(
			By.CLASS_NAME, 'emoji-list').get_attribute('outerHTML')
		dom_list.append({'name': name_list[num],
		                 'dom': dom})
except TimeoutException:
	print('Loading time out')
	driver.quit()
	exit()
driver.quit()
time.sleep(5)

# 获取关注列表
subscribe_list = []
driver.get(f"https://space.bilibili.com/{uid}/fans/follow")
WebDriverWait(driver, TIMEOUT).until(
	ec.text_to_be_present_in_element((By.CLASS_NAME, 'be-pager-total'), '共'))
page = int(driver.find_element(By.CLASS_NAME,
                               'be-pager-total').text.split(' ')[1])
next_page_btn = driver.find_element(By.CLASS_NAME, 'be-pager-next')
page_now = 1
while page_now <= page:
	WebDriverWait(driver, TIMEOUT).until(
		ec.text_to_be_present_in_element((By.CLASS_NAME, 'be-pager-total'), '共'))
	sub_dom = driver.find_element(
		By.CLASS_NAME, 'relation-list').get_attribute('innerHTML')
	sub_soup = BeautifulSoup(sub_dom, 'html.parser')
	for i in sub_soup:
		up_uid = i.a.attrs['href'].split('/')[-2]
		up_name = i.contents[-1].a.text
		subscribe_list.append((up_name, up_uid))
	page_now += 1
	if page_now != page:
		next_page_btn.click()

# 获取直播间地址
live_list = []
for name, uid in subscribe_list:
	space_url = f"https://space.bilibili.com/{uid}"
	driver.get(space_url)
	try:
		WebDriverWait(driver, 1.5).until(
			ec.text_to_be_present_in_element((By.CLASS_NAME, 'i-live'), '直播间'))
	except TimeoutException:
		print(f"{name}up主未开通直播间")
		continue
	live_info_dom = driver.find_element(
		By.CLASS_NAME, 'i-live').get_attribute('innerHTML')
	live_info_soup = BeautifulSoup(live_info_dom, 'html.parser')
	url = live_info_soup.find('a').attrs['href']
	live_uid = url.split('?')[0].split('/')[-1]
	live_list.append((name, live_uid))


async def main() -> None:
	tasks = []
	# 颜文字存储
	text_emoji = []
	for i in dom_list:
		file_name = i['name']
		mkdir(file_name)
		dom_text = BeautifulSoup(i['dom'], 'html.parser')
		for j in dom_text:
			if file_name == '颜文字':
				for k in j:
					text_emoji.append(k.text)
				with open(download_folder / '颜文字' / 'emoji.json', 'w', encoding='utf-8') as fp:
					json.dump(text_emoji, fp, ensure_ascii=False)
					fp.close()
			else:
				for pic_ids, emoji in enumerate(j):
					emoji_name = emoji.div.get('title')[1:-1]
					url = re.findall(URL_RE, emoji.div.get('style'))[0][:-1]
					if '@' in url:
						url = url.split('@')[0]
					url = url.replace('//', 'https://')
					types = url.split('.')[-1]
					tmp = asyncio.create_task(
						download(dir_name=file_name, url=url, types=types, emoji_name=emoji_name, ids=pic_ids))
					tasks.append(tmp)
	print(f"开始下载{len(tasks)}个表情包")
	await asyncio.wait(tasks)
	print('Download complete')


if __name__ == '__main__':
	asyncio.run(main())
