import os
import pandas as pd
import json
import pickle
from utils.crawl_support import download_files, crawl_list, extract_pblanc_id
from utils.preprocess_support_data import preprocess_support_run_all
from utils.embed_and_store import append_vectorstore_from_pdf_json

def update_support_projects(csv_path="utils/data/bizinfo_지원사업_공고목록.csv", base_dir="utils/data/download(support)", vectorstore_dir="embeddings", max_pages=3):
    
    # 기존 CSV 불러오기 또는 초기화
    if os.path.exists(csv_path):
        df_existing = pd.read_csv(csv_path)
    else:
        df_existing = pd.DataFrame(columns=["제목", "링크", "pblanc_id", "벡터스토어 저장"])

    # 새로운 공고 목록 크롤링
    new_data = crawl_list(max_pages=max_pages)
    df_new = pd.DataFrame(new_data)
    df_new["pblanc_id"] = df_new["링크"].apply(extract_pblanc_id)
    df_new = df_new.dropna(subset=["pblanc_id"])
    df_new = df_new[~df_new["pblanc_id"].isin(df_existing["pblanc_id"].astype(str))]

    if df_new.empty:
        return

    print(f"{len(df_new)}개 새로운 공고 발견됨")

    # 첨부파일 다운로드
    for pid in df_new["pblanc_id"].unique():
        download_files(pid, save_root=base_dir)

    # 전처리 수행
    preprocess_support_run_all()

    # 기존 df + 신규 df 병합 및 저장
    df_new["벡터스토어 저장"] = False
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # 벡터스토어에 추가
    append_vectorstore_from_pdf_json(base_dir=base_dir, vectorstore_dir=vectorstore_dir, csv_path=csv_path)
