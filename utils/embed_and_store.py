import os
import re
import pickle
import pandas as pd
from langchain.document_loaders import PDFPlumberLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.schema import Document
from typing import List
from utils.kure_embedding import KUREEmbedding
from dotenv import load_dotenv

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

EXCLUDE_KEYWORDS = ['지원서', '사업계획서', '계획서', '서식', '양식', '신청서', 
                    '동의서', '서약서', '의향서', '확인서']

kure_model = KUREEmbedding()


def remove_newlines_except_after_period(text):
    return re.sub(r'(?<!\.)(\n|\r\n)', ' ', text)

def load_document(file_path, folder_name, title, gov_name): 
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        loader = PDFPlumberLoader(file_path)
    elif ext == ".json":
        loader = TextLoader(file_path, encoding="utf-8")
    else:
        return []

    docs = loader.load()
    for doc in docs:
        doc.page_content = remove_newlines_except_after_period(doc.page_content)
        doc.metadata.update({
            "folder_name": folder_name,
            "file_type": ext,
            "title": title,
            "소관부처_지자체": gov_name, 
            "종류": "지원사업"
        })
    return docs

def save_vectorstore(documents, vectorstore_dir):
    texts = [doc.page_content for doc in documents]
    metas = [doc.metadata for doc in documents]
    embedding_model = kure_model

    batch_size = 32
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embeddings = embedding_model.embed_documents(batch)
        all_embeddings.extend(batch_embeddings)

    vectorstore = FAISS.from_embeddings(list(zip(texts, all_embeddings)), embedding_model)
    os.makedirs(vectorstore_dir, exist_ok=True)
    vectorstore.save_local(vectorstore_dir)

    with open(os.path.join(vectorstore_dir, "documents.pkl"), "wb") as f:
        pickle.dump(documents, f)

def append_vectorstore_from_pdf_json(base_dir, vectorstore_dir, csv_path):
    df = pd.read_csv(csv_path)
    if "벡터스토어 저장" not in df.columns:
        df["벡터스토어 저장"] = False

    all_split_docs = []

    # 문서 로딩 및 Split
    for folder_name in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue

        match_row = df[df["pblanc_id"].astype(str) == folder_name]
        if match_row.empty:
            continue
        title = match_row.iloc[0]["제목"]
        gov_name = match_row.iloc[0]["소관부처_지자체"] if "소관부처_지자체" in match_row.columns else ""

        all_docs = []
        for file_name in os.listdir(folder_path):
            if not (file_name.endswith(".pdf") or file_name.endswith(".json")):
                continue
            if any(keyword in file_name for keyword in EXCLUDE_KEYWORDS):
                continue

            file_path = os.path.join(folder_path, file_name)
            docs = load_document(file_path, folder_name, title, gov_name)
            all_docs.extend(docs)

        if all_docs:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
            split_docs = text_splitter.split_documents(all_docs)
            all_split_docs.extend(split_docs)
            df.loc[df["pblanc_id"].astype(str) == folder_name, "벡터스토어 저장"] = True

    if not all_split_docs:
        return

    # 임베딩 준비
    texts = [doc.page_content for doc in all_split_docs]
    metadatas = [doc.metadata for doc in all_split_docs]
    embedding_model = kure_model

    # 기존 벡터스토어 로드 or 새로 생성
    if os.path.exists(os.path.join(vectorstore_dir, "index.faiss")):
        vectorstore = FAISS.load_local(
            vectorstore_dir,
            embedding_model.embed_query,
            allow_dangerous_deserialization=True
        )

        # 배치 단위로 add_texts 수행
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            vectorstore.add_texts(texts=batch_texts, metadatas=batch_metas)

    else:
        vectorstore = FAISS.from_texts(texts=texts, embedding=embedding_model, metadatas=metadatas)

    # 저장
    vectorstore.save_local(vectorstore_dir)
    with open(os.path.join(vectorstore_dir, "documents.pkl"), "ab") as f:
        pickle.dump(all_split_docs, f)

    df.to_csv(csv_path, index=False)


# 긴 줄 정리
def remove_newlines_except_after_period(text: str) -> str:
    return " ".join(text.split())

def process_and_save_txt_documents(txt_dirs: List[str], vectorstore_dir: str):
    all_docs: List[Document] = []
    
    # 지역명 목록 정의
    possible_regions = [
        "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
        "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "전국"
    ]

    # TXT 로드 → Document 생성(메타데이터 포함)
    for txt_dir in txt_dirs:
        full_dir = os.path.join(os.getcwd(), txt_dir)
        if not os.path.exists(full_dir):
            continue

        for file_name in os.listdir(full_dir):
            if not file_name.endswith(".txt"):
                continue

            file_path = os.path.join(full_dir, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                continue

            # 파일명 파싱 안전화
            parts = file_name.replace(".txt", "").split("_")
            bank_name = parts[2] if len(parts) > 2 else ""
            product_name = parts[3] if len(parts) > 3 else ""

            # 파일명에서 지역 추출 시도
            region_name = ""
            for region in possible_regions:
                if (len(parts) > 2 and region in parts[2]) or (len(parts) > 3 and region in parts[3]):
                    region_name = region
                    break
            # 없으면 '전국'
            if not region_name:
                region_name = "전국"

            metadata = {
                "folder_name": txt_dir,
                "file_type": ".txt",
                "bank_name": bank_name,
                "product_name": product_name,
                "종류": "금융상품",
                "지역": region_name
            }

            doc = Document(
                page_content=remove_newlines_except_after_period(content),
                metadata=metadata
            )
            all_docs.append(doc)

    if not all_docs:
        return None

    # Split
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=50)
    split_docs = splitter.split_documents(all_docs)

    # 임베딩/벡터스토어 저장 (배치 처리)
    save_dir = vectorstore_dir
    os.makedirs(save_dir, exist_ok=True)

    embedding_model = kure_model
    batch_size = 48

    index_path = os.path.join(save_dir, "index.faiss")
    vectorstore = None

    if os.path.exists(index_path):
        try:
            vectorstore = FAISS.load_local(
                save_dir, embedding_model, allow_dangerous_deserialization=True
            )
        except Exception as e:
            return None

        # 기존 인덱스에 배치로 추가
        added = 0
        for i in range(0, len(split_docs), batch_size):
            batch_docs = split_docs[i:i + batch_size]
            try:
                vectorstore.add_documents(batch_docs)
                added += len(batch_docs)
            except Exception as e:
                continue

    else:
        start_idx = 0
        if len(split_docs) == 0:
            return None

        # 첫 배치
        first_batch = split_docs[:batch_size]
        try:
            vectorstore = FAISS.from_documents(first_batch, embedding_model)
            start_idx = len(first_batch)
        except Exception as e:
            return None

        # 나머지 배치
        added = start_idx
        for i in range(start_idx, len(split_docs), batch_size):
            batch_docs = split_docs[i:i + batch_size]
            try:
                vectorstore.add_documents(batch_docs)
                added += len(batch_docs)
            except Exception as e:
                continue

    # 저장
    try:
        vectorstore.save_local(save_dir)
    except Exception as e:
        return None

    doc_file = os.path.join(save_dir, "documents.pkl")
    try:
        if os.path.exists(doc_file):
            with open(doc_file, "rb") as f:
                existing_docs = pickle.load(f)
            all_combined = existing_docs + split_docs
        else:
            all_combined = split_docs

        with open(doc_file, "wb") as f:
            pickle.dump(all_combined, f)
    except Exception as e:
        print(f"문서 병합 저장 실패(무시 가능): {e}")

    return vectorstore