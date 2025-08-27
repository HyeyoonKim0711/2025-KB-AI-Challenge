import os, re, json
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.schema.runnable import RunnableMap
from langchain.callbacks import get_openai_callback
from langchain.prompts import load_prompt
from utils.kure_embedding import KUREEmbedding


load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

### 벡터스토어 및 리트리버
vectorstore_path = "embeddings"
embeddings = KUREEmbedding()
vectorstore = FAISS.load_local(vectorstore_path, embeddings.embed_query, allow_dangerous_deserialization=True)
retriever = vectorstore.as_retriever(search_kwargs={"k": 7})

llm_answerer = ChatOpenAI(model="gpt-4o-mini", temperature=0)
answer_prompt = load_prompt("prompts/prompt.yaml", encoding="utf-8")

def combine_docs(docs, max_chars=3000):
    return "\n\n".join(doc.page_content for doc in docs)[:max_chars]


### 의도 감지: 추천성 질문만 recommend
def detect_intent(q: str) -> str:
    q = q.lower()

    # 추천/상품 요청 패턴
    reco = [
        r"추천",                         
        r"뭐가 좋",                      
        r"어떤.*(상품|정책|지원)",        
        r"지원사업.*알려줘",             
        r"맞는.*(상품|사업|정책)",
        r"대출.*가능",                   
        r"(있을까|있나요|있을까요)",     
        r"(도움(받|줄).*상품)",           
        r"(지원|대출).*있(나|는지)",      
        r"(창업|사업).*지원.*있",        
        r"(혜택|정책).*있",               
        r"(어떤게|무엇이).*좋",        
    ]
    if any(re.search(p, q) for p in reco):
        return "recommend"

    # 정보/절차/금액 질문 패턴
    info = [
        r"얼마(나|까지)?", r"한도", r"금액",
        r"필요(해|한|했)", r"방법|절차|서류",
        r"정의|개념|차이|방식", r"기억(해|하)"
    ]
    if any(re.search(p, q) for p in info):
        return "info"

    # 둘 다 아니면 스몰토크/기타
    return "smalltalk"



### 메타데이터 정리
def meta_of(doc):
    md = doc.metadata or {}
    return {
        "title": md.get("title") or "",
        "종류": md.get("종류") or "",
        "bank_name": md.get("bank_name") or "",
        "product_name": md.get("product_name") or "",
        "소관부처_지자체": md.get("소관부처_지자체") or md.get("주관기관") or "",
        "지역": md.get("지역") or ""
    }

def first_n(text, n=1600):
    return (text or "")[:n]



### 표 생성 
# 요약 LLM
llm_summarizer = ChatOpenAI(model="gpt-4o-mini", temperature=0)

def summarize_multiple_docs(docs):
    contents = "\n\n".join([
        f"[문서{i+1}]\n{first_n(doc.page_content, 1600)}"
        for i, doc in enumerate(docs)
    ])
    prompt = f"""
    다음 금융상품/정책 각각에 대해, 반드시 아래 형식을 지켜서 1~2문장으로 자연스럽게 요약해 주세요.
    - 각 요약은 반드시 "[문서번호]:"로 시작
    - 대상, 자금 용도, 지원 한도, 금리, 상환 방식, 추천 대상(어떤 분께 적합한지)을 포함
    - 나열식이 아닌 문장 흐름으로 작성
    - 다른 불필요한 번호나 기호는 쓰지 말 것

    {contents}
    """
    resp = llm_summarizer.invoke(prompt)
    text = resp.content.strip()

    # "[문서번호]:" 뒤 내용을 전부 추출
    summaries = re.findall(r"\[문서\d+\]:\s*(.+)", text)

    # 문서 수와 맞지 않으면 빈칸 채움
    if len(summaries) < len(docs):
        summaries += [""] * (len(docs) - len(summaries))

    return summaries

def to_markdown_table(docs):
    summaries = summarize_multiple_docs(docs)
    header = "| 상품/사업명 | 종류 | 요약 |"
    sep    = "|---|---|---|"
    lines  = [header, sep]

    for doc, summary in zip(docs, summaries):
        md = meta_of(doc)
        kind = md.get("종류", "")

        # 금융상품이면 은행명 + 상품명, 지원사업이면 title 사용
        if kind == "금융상품":
            title = f"{md.get('bank_name', '')} {md.get('product_name', '')}".strip()
        else:
            title = md.get("title", "")

        lines.append(f"| {title} | {kind} | {summary} |")

    return "\n".join(lines)


########### 메인 함수: 질문 → 검색 → 답변 생성 ###########
def answer_query(question: str, biz_type: str, region: str, selected_industries: str, history: str = ""):
    
    
    # 검색용 쿼리 생성
    user_context_sentence = f"{region}에 거주하는 {biz_type}"
    if selected_industries:
        user_context_sentence += f", 업종은 {', '.join(selected_industries)}"
    
    search_query = f"{user_context_sentence}. {question}"

    # 여기서만 context 포함된 쿼리로 검색
    retrieved_docs = retriever.invoke(search_query)
    
    print("검색된 문서:")
    for i, doc in enumerate(retrieved_docs):
        print(f"[{i+1}] {doc.metadata.get('source', '알 수 없음')}\n{doc.page_content}...\n")

    # 검색 결과 없을 때
    if not retrieved_docs:
        return "관련 문서를 찾지 못했어요. 질문을 조금 더 구체적으로 적어주시거나 다른 키워드로 다시 질문해 주세요."

    # 검색 문서 필터링
    local_regions = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시",
    "울산광역시", "세종특별자치시", "경기도", "강원도", "충청북도", "충청남도",
    "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"
    ]

    region_aliases = {
        "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
        "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
        "경기": "경기도", "강원": "강원도", "충북": "충청북도", "충남": "충청남도",
        "전북": "전라북도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도",
        "제주": "제주특별자치도"
    }

    def normalize_region(name: str):
        if not name:
            return ""
        name = name.strip().replace(" ", "")

        # 별칭 처리 (앞부분에 해당 단어가 있으면 매핑)
        for short, full in region_aliases.items():
            if short in name: 
                name = full
                break

        # 전북특별자치도 → 전라북도, 강원특별자치도 → 강원도 등 통일
        name = name.replace("특별자치도", "도")
        return name

    def region_filter(user_region, doc_region):
        if not doc_region:
            return False
        doc_norm = normalize_region(doc_region)
        user_norm = normalize_region(user_region)
        if any(normalize_region(r) == doc_norm for r in local_regions):
            return doc_norm == user_norm
        return True


    # 필터 적용
    filtered_docs = [
        d for d in retrieved_docs
        if region_filter(region, d.metadata.get("소관부처_지자체")) 
        or region_filter(region, d.metadata.get("지역"))
    ]

    top3 = filtered_docs[:3]
    if not top3:
        return f"😥 죄송하지만, 현재 {region} 지역에 맞는 지원사업이나 금융상품을 찾지 못했어요. 다른 지역 조건이나 키워드로 다시 검색해 보시겠어요? 또는 “전국 단위” 사업은 조건을 완화하면 찾아드릴게요! 🐝"


    top3_meta_json = json.dumps([meta_of(d) for d in top3], ensure_ascii=False, indent=2)
    top1_content = first_n(top3[0].page_content, 1600)
    intent = detect_intent(question)
    top3_table_md = to_markdown_table(top3)

    
    answer_chain = (
        RunnableMap({
            "question": lambda x: x["question"],
            "context":  lambda x: combine_docs(x["docs"]),
            "biz_type": lambda x: x["biz_type"],
            "region":   lambda x: x["region"],
            "selected_industries": lambda x: x["selected_industries"],
            "history":  lambda x: x.get("history", ""),
            "intent":   lambda x: x["intent"],
            "top3_meta_json": lambda x: x["top3_meta_json"],
            "top1_content":   lambda x: x["top1_content"],
            "top3_table_md":  lambda x: x["top3_table_md"],
        })
        | answer_prompt
        | llm_answerer
    )

    prompt_text = answer_prompt.format(
    question=search_query,
    context=combine_docs(filtered_docs),
    biz_type=biz_type,
    region=region,
    selected_industries=selected_industries,
    history=history,
    intent=intent,
    top3_meta_json=top3_meta_json,
    top1_content=top1_content,
    top3_table_md=top3_table_md,
        )

    print("\n📌 최종 LLM 입력 프롬프트 ====================================")
    print(prompt_text)
    print("==========================================================\n")

    with get_openai_callback() as cb:
        response = answer_chain.invoke({
            "question": search_query,
            "docs": filtered_docs,     
            "biz_type": biz_type,
            "region": region,
            "selected_industries": selected_industries,
            "history": history,
            "intent": intent, 
            "top3_meta_json": top3_meta_json,
            "top1_content": top1_content,
            "top3_table_md": top3_table_md,
        })

        print(f"\n💰 토큰 사용량")
        print(f"  - 총 사용량: {cb.total_tokens}")
        print(f"  - 프롬프트 토큰: {cb.prompt_tokens}")
        print(f"  - 응답 토큰: {cb.completion_tokens}")
        print(f"  - 비용: ${cb.total_cost:.6f}")

    return response.content
