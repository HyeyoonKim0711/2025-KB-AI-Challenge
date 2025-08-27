import os
import json
import time
import re
import requests
import pandas as pd
import certifi
from typing import List, Union
from datetime import datetime
from dateutil.relativedelta import relativedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

### FSS 크롤링 ###
# 셀레니움 드라이버 설정
def setup_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)

# 상세 정보 추출
def extract_detailed_info(soup):
    target_keys = [
        "적용가능 금리", "대출한도", "가입대상 세부요건", "가입방법",
        "우대금리", "중도상환 수수료", "대출부대비용", "연체이자율", "담당부서 및 연락처"
    ]
    data = {}
    dl_sets = soup.select("div.dl-set > dl")
    for dl in dl_sets:
        dt_tag = dl.find("dt")
        dd_tags = dl.find_all("dd")
        if not dt_tag or not dd_tags:
            continue
        key = dt_tag.get_text(strip=True).replace('\xa0', ' ').strip()
        if key not in target_keys:
            matched = [k for k in target_keys if k in key]
            if matched:
                key = matched[0]
            else:
                continue
        combined_lines = []
        for dd_tag in dd_tags:
            raw_html = dd_tag.decode_contents().replace('\xa0', ' ')
            if "<br>" in raw_html:
                lines = [BeautifulSoup(line, 'html.parser').get_text(strip=True)
                         for line in raw_html.split('<br>') if line.strip()]
                combined_lines.extend(lines)
            else:
                text = dd_tag.get_text(separator="\n", strip=True).replace('\xa0', ' ')
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                combined_lines.extend(lines)
        data[key] = combined_lines if len(combined_lines) > 1 else combined_lines[0] if combined_lines else ""
    for key in target_keys:
        if key not in data:
            data[key] = ""
    return data

# 페이지 수 감지
def get_last_page_number(driver): 
    soup = BeautifulSoup(driver.page_source, "html.parser")
    page_links = soup.select("div.pagination-set a[data-pageindex]")
    page_numbers = []
    for a in page_links:
        index = a.get("data-pageindex")
        if index and index.isdigit():
            page_numbers.append(int(index))
    return max(page_numbers) if page_numbers else 1

# '금융상품 한눈에'(fss) 전체 상품 크롤링
def crawl_fss_products(max_page=None):
    driver = setup_driver()
    url = "https://finlife.fss.or.kr/finlife/ldng/indvlBusi/list.do?menuNo=700072"
    driver.get(url)
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "금융상품 검색")]'))
    ).click()
    time.sleep(2)

    if max_page is None:
        max_page = get_last_page_number(driver)  
        print(f"총 페이지 수 감지됨: {max_page}")
    else:
        print(f"max_page 지정됨 → {max_page}페이지만 크롤링")

    all_products = []
    current_page = 1

    while current_page <= max_page:
        driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        items = soup.find_all(class_="onOffTr")

        for idx, item in enumerate(items):
            lines = [line.strip() for line in item.text.strip().split('\n') if line.strip()]
            if len(lines) < 8:
                continue
            base_info = lines[:8]

            try:
                detail_buttons = driver.find_elements(By.CSS_SELECTOR, 'a.tabel-more')
                driver.execute_script("arguments[0].click();", detail_buttons[idx])
                time.sleep(1.5)
                detail_soup = BeautifulSoup(driver.page_source, "html.parser")
                detailed_info = extract_detailed_info(detail_soup)

                product = {
                    "금융회사": base_info[0],
                    "상품명": base_info[1],
                    "자금용도": base_info[2],
                    "가입대상": base_info[3],
                    "대출종류": base_info[4],
                    "금리방식": base_info[5],
                    "상환방식": base_info[6],
                    "전월 평균금리": base_info[7],
                    **detailed_info
                }
                all_products.append(product)
            except:
                continue

        if current_page < max_page:
            try:
                page_buttons = driver.find_elements(By.CSS_SELECTOR, 'div.pagination-set a[data-pageindex]')
                for btn in page_buttons:
                    if btn.get_attribute("data-pageindex") == str(current_page + 1):
                        driver.execute_script("arguments[0].click();", btn)
                        break
                current_page += 1
                time.sleep(2)
            except Exception as e:
                print(f"페이지 {current_page + 1} 이동 실패: {e}")
                break
        else:
            break

    driver.quit()
    return all_products

# 크롤링한 상품을 JSON 파일로 저장
def save_fss_products(products, path=os.path.join(OUTPUT_DIR, "fss_products.json")):
    os.makedirs(os.path.dirname(path), exist_ok=True) 
    with open(path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print(f"FSS 저장 완료: {len(products)}건 → {path}")

### KINFA ###
import requests, certifi, time, os
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

service_key = "OOMzi/L4lsQBtwINCMNBqO7LJpepiMcGg5Hnx0rJ5keZ7Zfb/8bYyDgzjsGgPmlvK2afF0Qf+OnsOARuV0IPcQ=="
url = "http://apis.data.go.kr/1160100/service/GetSmallLoanFinanceInstituteInfoService/getOrdinaryFinanceInfo"

# KINFA API 호출 
def get_all_items(likeTrgt: str, basYm: str):
    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 100,
        "resultType": "json",
        "likeTrgt": likeTrgt,
        "basYm": basYm
    }
    all_items = []

    try:
        response = requests.get(url, params=params, verify=certifi.where())
        if response.status_code != 200 or not response.text.strip():
            print(f"[{likeTrgt}][{basYm}] 응답 오류:", response.status_code)
            return []

        data = response.json()
        body = data.get("response", {}).get("body", {})
        total_count = body.get("totalCount", 0)
        num_of_rows = body.get("numOfRows", 100)
        total_pages = (total_count // num_of_rows) + (1 if total_count % num_of_rows > 0 else 0)
        print(f"[{likeTrgt}] {basYm} → 총 {total_count}건")

        for page in range(1, total_pages + 1):
            params["pageNo"] = page
            response = requests.get(url, params=params, verify=certifi.where())
            if response.status_code != 200:
                print(f"{page}페이지 호출 실패:", response.status_code)
                continue
            items = response.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
            all_items.extend(items)
            time.sleep(0.2)
    except Exception as e:
        print(f"[{likeTrgt}][{basYm}] 오류 발생:", e)

    return all_items

# 1개월 기준 데이터 수집
def fetch_one_month(basYm):
    biz_items = get_all_items("사업자", basYm)
    sme_items = get_all_items("소상공인", basYm)
    return biz_items + sme_items

# 2025-01부터 전체 수집
def fetch_data_from_202501():
    start = datetime.strptime("2025-01", "%Y-%m")
    end = datetime.today()
    all_items = []

    while start <= end:
        ym = start.strftime("%Y%m")
        all_items += fetch_one_month(ym)
        start += relativedelta(months=1)

    return all_items

# 과거 중복 상품 제거 및 변수명 한글화
def clean_and_rename(items):
    df = pd.DataFrame(items)
    if df.empty:
        return df

    df = df.sort_values("basYm", ascending=False)
    df = df.drop_duplicates(subset=["finPrdNm", "ofrInstNm"], keep="first")
    df = df.rename(columns={
        'basYm': '기준년월',
        'finPrdNm': '금융상품명',
        'lnLmt': '대출한도',
        'irtCtg': '금리구분',
        'irt': '금리',
        'rdptMthd': '상환방법',
        'usge': '용도',
        'trgt': '대상',
        'ofrInstNm': '제공기관명',
        'rsdAreaPamtEqltIstm': '거주지역원금균등분할상환',
        'suprTgtDtlCond': '지원대상 상세조건',
        'crdtSc': '신용등급',
        'rfrcCnpl': '문의처 및 연락처',
        'jnMthd': '가입(신청)방법',
        'ovItrYr': '연체이자율(연)',
        'prftAddIrtCond': '우대금리/가산금리 조건',
        'cnpl': '연락처',
        'rltSite': '관련 사이트',
        'tgtFltr': '대상_필터',
        'hdlInstDtlVw': '취급기관_상세보기용',
        'prdExisYn': '상품존재여부',
        'prdNm': '상품명',
        'mgmDln': '운영기한'
    })

    columns_to_keep = [
        '기준년월', '금융상품명', '대출한도', '금리구분', '금리', '상환방법', '용도', '대상',
        '제공기관명', '거주지역원금균등분할상환', '지원대상 상세조건', '신용등급', '문의처 및 연락처',
        '가입(신청)방법', '연체이자율(연)', '우대금리/가산금리 조건', '연락처', '관련 사이트',
        '대상_필터', '취급기관_상세보기용', '상품존재여부', '상품명', '운영기한'
    ]
    return df[columns_to_keep]

# 기존 JSON 불러오기 
def load_existing_json(filename: str) -> pd.DataFrame:
    path = os.path.join(OUTPUT_DIR, filename)
    return pd.read_json(path) if os.path.exists(path) else pd.DataFrame()

# 기존 데이터와 병합하여 저장
def save_kinfa_merged(new_df, existing_df=None, path=os.path.join(OUTPUT_DIR, "kinfa_products.json")):
    combined = pd.concat([existing_df, new_df], ignore_index=True) if existing_df is not None else new_df
    combined["기준년월"] = combined["기준년월"].astype(str)
    combined = combined.sort_values("기준년월", ascending=False)
    combined = combined.drop_duplicates(subset=["제공기관명", "금융상품명"], keep="first")
    combined.to_json(path, orient="records", force_ascii=False, indent=2)
    print(f"KINFA 저장 완료: 현재 총{len(combined)}건 → {path}")
