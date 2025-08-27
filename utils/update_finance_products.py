import json
import os
import pandas as pd
from datetime import datetime
from utils.crawl_finance import crawl_fss_products, fetch_one_month, clean_and_rename, load_existing_json, save_kinfa_merged
import sys


# 데이터 저장 디렉토리
OUTPUT_DIR = "data"  

### FSS 업데이트 ###
def update_fss():
    # 저장 경로 생성
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, "fss_products.json")

    # 신규 데이터 수집
    new_products = crawl_fss_products(max_page=3)

    # 기존 데이터 로딩
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = []

    # 중복 검사 및 추가
    added = 0
    for p in new_products:
        if all(not (p["금융회사"] == e["금융회사"] and p["상품명"] == e["상품명"]) for e in existing):
            existing.append(p)
            added += 1

    # 저장
    if added > 0:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"[FSS] 신규 상품 {added}개 추가됨 → 전체 {len(existing)}개 저장 완료")
    else:
        print("[FSS] 신규 상품 없음")

### KINFA 업데이트 ###

# 저장 경로
OUTPUT_DIR = "data"
KINFA_PATH = os.path.join(OUTPUT_DIR, "kinfa_products.json")

# KINFA 데이터 저장 함수
def save_kinfa_merged(new_df, existing_df=None, path=None):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = path or KINFA_PATH

    combined = pd.concat([existing_df, new_df], ignore_index=True) if existing_df is not None else new_df
    combined["기준년월"] = combined["기준년월"].astype(str)
    combined = combined.sort_values("기준년월", ascending=False)
    combined = combined.drop_duplicates(subset=["제공기관명", "금융상품명"], keep="first")

    combined.to_json(path, orient="records", force_ascii=False, indent=2)
    print(f"[KINFA] 저장 완료: {len(combined)}건 → {path}")

# 월별 업데이트
def update_monthly(basYm=None):
    basYm = basYm or datetime.today().strftime("%Y%m")
    print(f"[KINFA] {basYm} 데이터 수집 시작")

    items = fetch_one_month(basYm)
    df = clean_and_rename(items)

    if df.empty:
        print("[KINFA] 수집된 데이터 없음")
        return

    existing = load_existing_json()

    if existing.empty:
        print("[KINFA] 기존 데이터 없음 → 전체 저장")
        save_kinfa_merged(df)
        return

    df["_merge_key"] = df["제공기관명"] + "__" + df["금융상품명"]
    existing["_merge_key"] = existing["제공기관명"] + "__" + existing["금융상품명"]

    new_only = df[~df["_merge_key"].isin(existing["_merge_key"])].drop(columns="_merge_key")
    existing.drop(columns="_merge_key", inplace=True)

    print(f"[KINFA] 신규 상품 {len(new_only)}개 저장 완료")
    save_kinfa_merged(new_only, existing)

### MAIN 함수 ###
# if __name__ == "__main__":
#     print("금융 상품 데이터 업데이트 시작")
#     update_fss()  # FSS 금융상품 수집
#     update_monthly()  # KINFA 금융상품 수집
#     print("모든 업데이트 완료")