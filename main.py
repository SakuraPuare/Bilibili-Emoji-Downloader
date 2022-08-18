import asyncio
import json
import pathlib
import re
import time

import httpx
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

TIMEOUT = 30
HEADER = {
    'authority': 'i0.hdslb.com',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
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
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
}
URL_RE = re.compile(r'//[^\s]*\"')
LIMITS = httpx.Limits(max_keepalive_connections=5, max_connections=10)


def mkdir(folder: str) -> None:
    folder = download_folder / folder
    if not (folder.exists() and folder.is_dir()):
        folder.mkdir()


async def download(name: str, url: str, ids: int, emoji_name: str, types: str) -> None:
    try:
        save_name: str = f"{ids}-{emoji_name}.{types}"
        complete_path = download_folder / name / save_name
        if not complete_path.exists():
            async with httpx.AsyncClient(limits=LIMITS, timeout=30) as client:
                res = await client.get(url, headers=HEADER)
                with open(complete_path, "wb") as f:
                    f.write(res.content)
                    f.close()
    except:
        pass


driver = webdriver.Chrome()
driver.get('https://passport.bilibili.com/login')

# 创建下载文件夹
download_folder = pathlib.Path(__file__).with_name('download')
if not (download_folder.exists() and download_folder.is_dir()):
    download_folder.mkdir()

# 加载cookies
cookies_path = pathlib.Path(__file__).with_name('cookies.txt')
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
        pass

# 读取并保存cookies
cookies = driver.get_cookies()
with open('cookies.txt', 'w') as f:
    f.write(json.dumps(cookies))
    f.close()

# 获取表情名称
driver.get('https://space.bilibili.com/281130859/dynamic')
try:
    element = WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'bili-dyn-list__item')))
    driver.find_elements(By.CLASS_NAME, 'comment')[0].click()
    element = WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'comment-emoji')))
    driver.find_elements(By.CLASS_NAME, 'comment-emoji')[0].click()
    element = WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'emoji-box')))
    emoji_list = driver.find_elements(By.CLASS_NAME, 'tab-link')
    name_list = []
    for num, ele in enumerate(emoji_list):
        if num % 5 == 0 and num != 0:
            driver.find_element(
                By.XPATH, '/html/body/div[2]/div[4]/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[2]/div[2]/div[4]/div[2]/span[2]').click()
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
    element = WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'emotion-btn-box')))
    driver.find_elements(By.CLASS_NAME, 'emotion-btn-box')[0].click()
    element = WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'content-ctnr')))
    emoji_list = driver.find_elements(
        By.CLASS_NAME, 'emoji-cover')
    dom_list = []
    for num, ele in enumerate(emoji_list):
        if num % 6 == 0 and num != 0:
            driver.find_element(
                By.XPATH, '/html/body/div[3]/div/div[1]/div[2]/div[2]/div[1]/div/div/div[4]/div[1]/div[4]/div[1]/div[2]/div/div/div[3]/div[2]/div/span[2]').click()
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


async def main() -> None:
    tasks = []
    for i in dom_list:
        name = i['name']
        mkdir(name)
        dom = BeautifulSoup(i['dom'], 'html.parser')
        for j in dom:
            if name == '颜文字':
                continue
            for num, emoji in enumerate(j):
                emoji_name = emoji.div.get('title')[1:-1]
                url = re.findall(URL_RE, emoji.div.get('style'))[0][:-1]
                if '@' in url:
                    url = url.split('@')[0]
                url = url.replace('//', 'https://')
                types = url.split('.')[-1]
                tmp = asyncio.create_task(
                    download(name, url, num, emoji_name, types))
                tasks.append(tmp)

    print(f"开始下载{len(tasks)}个表情包")
    await asyncio.wait(tasks)
    print('Download complete')


asyncio.run(main())
