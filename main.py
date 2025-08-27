
import streamlit as st
from utils.query_and_generate import answer_query
import random


########### 스트림릿 구현 ################

# Sidebar 입력
st.sidebar.header("🧑‍💼 사용자 정보 입력")

biz_type = st.sidebar.radio("사업 종류", options=["소상공인", "중소기업"])
region = st.sidebar.selectbox(
    "거주 지역",
    options=[
        "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시",
        "울산광역시", "세종특별자치시", "경기도", "강원도", "충청북도", "충청남도",
        "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"
    ]
)

industries = [
    "농업, 임업 및 어업", "광업", "제조업", "전기, 가스, 증기 및 공기 조절 공급업",
    "수도, 하수 및 폐기물 처리, 원료 재생업", "건설업", "도매 및 소매업", "운수 및 창고업",
    "숙박 및 음식점업", "정보통신업", "금융 및 보험업", "부동산업",
    "전문, 과학 및 기술 서비스업", "사업시설 관리, 사업 지원 및 임대 서비스업",
    "공공 행정, 국방 및 사회보장 행정", "교육 서비스업", "보건업 및 사회복지 서비스업",
    "예술, 스포츠 및 여가관련 서비스업", "협회 및 단체, 수리 및 기타 개인 서비스업",
    "가구내 고용활동 및 달리 분류되지 않은 자가소비 생산활동", "국제 및 외국기관"
]
selected_industries = st.sidebar.multiselect("업종", options=industries)

st.sidebar.markdown("\n\n\n")

st.sidebar.markdown(f"### 🐝 오늘의 꿀팁\n")
st.sidebar.markdown(
    '''
    <div style="text-align:center;">
      <a href="https://www.kbstar.com" target="_blank">
        <img src="https://raw.githubusercontent.com/HyeyoonKim0711/2025-KB-AI-Challenge-2/refs/heads/main/%EA%BF%80%EB%B2%8C%EB%B9%84%EC%84%9C.jpg"
             alt="사장님의 꿀벌 비서" style="display:block;margin:0 auto;border-radius:12px;" width="200">
      </a>
    </div>
    ''',
    unsafe_allow_html=True
)

messages = [
    "오늘도 파이팅입니다, 사장님! 💪",
    "사장님의 성공을 응원해요 🐝",
    "작은 꿀 한 방울이 모여 큰 단지가 됩니다 🍯",
    "📌 대출 신청 전 반드시 금리를 비교해 보세요.",
    "🍯 지원사업은 신청 마감일을 꼭 확인하세요.",
    "💡 금리 인하 요구권을 활용해 보셨나요?"
]
st.sidebar.success(random.choice(messages))


st.title("사장님의 꿀벌 비서 🐝")
WELCOME_MSG = """안녕하세요! 저는 사장님의 꿀벌 비서 🐝
사장님을 위한 KB 금융 도우미 꿀벌이에요.
필요한 정보의 '꿀'만 골라 담아 드릴게요 🍯"""

if st.button("대화 초기화"):
    st.session_state["messages"] = [{"role": "assistant", "content": WELCOME_MSG}]

if "messages" not in st.session_state or not st.session_state["messages"]:
    st.session_state["messages"] = [{"role": "assistant", "content": WELCOME_MSG}]


ASSISTANT_AVATAR = "image/bee.jpg"
USER_AVATAR = "🧑‍💼"

# 초기 메시지 렌더
for msg in st.session_state["messages"]:
    avatar = ASSISTANT_AVATAR if msg["role"] == "assistant" else USER_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# 사용자 입력
user_input = st.chat_input("금융 상품이나 정부 지원사업에 대해 물어보세요! 🍯")

if user_input:
    # 사용자 메시지 세션에 저장
    user_msg = {"role": "user", "content": user_input}
    st.session_state["messages"].append(user_msg)
    st.chat_message("user", avatar=USER_AVATAR).write(user_input)

    # 히스토리 문자열 구성
    history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state["messages"]])

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.spinner("답변 생성 중..."):
            # answer_query에 history 함께 전달
            try:
                response = answer_query(
                    question=user_input,
                    biz_type=biz_type,
                    region=region,
                    selected_industries=selected_industries,
                    history=history,  
                )
            except TypeError:
                response = answer_query(user_input, biz_type, region)

            st.markdown(response)

    # assistant 메시지도 세션에 저장
    st.session_state["messages"].append({"role": "assistant", "content": response})
