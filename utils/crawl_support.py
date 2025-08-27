import os
import re
import time
import zipfile
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def get_base_urls():
    base_url = (
        "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do"
        "?hashCode=01&rowsSel=6&cat=&article_seq=&pblancId=&schJrsdCodeTy="
        "&schWntyAt=&schAreaDetailCodes=&schEndAt=N&orderGb=&sort="
        "&condition=searchPblancNm&condition1=AND&preKeywords=&keyword=&rows=15"
    )
    detail_base = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/"
    return base_url, detail_base

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    return webdriver.Chrome(options=options)

def get_last_page_num(driver):
    base_url, _ = get_base_urls()
    driver.get(base_url + "&cpage=1")
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    tag = soup.select_one("div.page_wrap a[title='마지막페이지']")
    if tag:
        match = re.search(r"cpage=(\d+)", tag.get("href", ""))
        if match:
            return int(match.group(1))
    return 1


def parse_page(html):
    _, detail_base = get_base_urls()
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("div.table_Type_1 > table > tbody > tr")
    parsed = []

    for row in rows:
        try:
            tds = row.find_all("td")
            a = row.select_one("td.txt_l a")
            title = a.get_text(strip=True)
            href = a.get("href")
            full_link = detail_base + href if href else None

            department = tds[4].get_text(strip=True) if len(tds) > 4 else ""

            parsed.append({
                "제목": title,
                "링크": full_link,
                "소관부처_지자체": department
            })
        except Exception as e:
            continue

    return parsed


def crawl_list(max_pages=None):
    driver = setup_driver()
    base_url, _ = get_base_urls()
    if not max_pages:
        max_pages = get_last_page_num(driver)
    data = []
    for page in range(1, max_pages + 1):
        driver.get(f"{base_url}&cpage={page}")
        time.sleep(2)
        data.extend(parse_page(driver.page_source))
    driver.quit()
    return data

def save_csv(data, path="utils/data/bizinfo_지원사업_공고목록.csv"):               
    df = pd.DataFrame(data)
    df.to_csv(path, index=False, encoding="utf-8-sig")

def extract_pblanc_id(link):
    if isinstance(link, str) and "pblancId=" in link:
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        return query.get("pblancId", [None])[0]
    return None

def extract_zip_with_encoding(zip_path, extract_to, encoding="euc-kr"):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for zip_info in zip_ref.infolist():
            try:
                decoded_name = zip_info.filename.encode('cp437').decode(encoding)
                zip_info.filename = decoded_name
                zip_ref.extract(zip_info, path=extract_to)
            except:
                continue

def download_files(pblanc_id, save_root="utils/data/download(support)"):      
    save_dir = os.path.join(os.getcwd(), save_root, pblanc_id)
    os.makedirs(save_dir, exist_ok=True)
    url = f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pblanc_id}"
    try:
        res = requests.get(url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        links = soup.select("a.icon_download")
        for link in links:
            name = link["title"].replace("첨부파일 ", "").replace(" 다운로드", "").strip()
            file_url = "https://www.bizinfo.go.kr" + link["href"]
            file_res = requests.get(file_url)
            file_res.raise_for_status()
            path = os.path.join(save_dir, name)
            with open(path, "wb") as f:
                f.write(file_res.content)
            if name.lower().endswith(".zip"):
                try:
                    extract_zip_with_encoding(path, save_dir)
                    os.remove(path)
                except:
                    continue
    except:
        pass


def support_run_all(max_pages=None):
    data = crawl_list(max_pages=max_pages)
    save_csv(data)

    df = pd.read_csv("utils/data/bizinfo_지원사업_공고목록.csv")                              
    df["pblanc_id"] = df["링크"].apply(extract_pblanc_id)
    df = df.dropna(subset=["pblanc_id"])
    df.to_csv("utils/data/bizinfo_지원사업_공고목록.csv", index=False, encoding="utf-8-sig")  

    for pid in df["pblanc_id"].unique():
        download_files(pid)

