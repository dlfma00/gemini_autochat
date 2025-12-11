
# ===================================================
# ⭐️ 셀 2: app.py 파일 생성 및 웹 챗봇 코드 (Streamlit 적용)
# ===================================================
import streamlit as st
import google.generativeai as genai

# Streamlit 설정: 웹페이지 제목 및 레이아웃 설정
st.set_page_config(page_title="7인 자캐 단톡방 시뮬레이터", layout="wide")
st.title("📱 7인 자캐 단톡방 시뮬레이터")

# ⚠️ 여기에 발급받은 API 키를 넣으세요! (Streamlit Cloud 배포 시는 보안상 별도 처리 필요)
# 지금은 테스트를 위해 여기에 직접 넣어둡니다.
API_KEY = st.secrets["GEMINI_API_KEY"]

# 자캐 6명 설정
CHARACTERS = """
1. [강건우]: 20대 초반, 다혈질, 행동파. 리더인 척하지만 허당임. 말투가 거칠음.
2. [이서아]: 20대 초반, 차가운 이성주의자. 안경캐. 팩트폭격을 주로 함.
3. [김포포]: 10대 후반, 4차원, 귀여운 척함. 이모티콘 많이 씀. 눈치가 없음.
4. [박현수]: 20대 중반, 피곤에 찌든 대학원생. 만사가 귀찮음. 
5. [최유리]: 20대 초반, 인싸, 유행어 많이 씀. 분위기 메이커.
6. [정태민]: 20대 초반, 소심함, 말끝을 흐림. 착하지만 답답함.
"""

# API 설정 및 모델 초기화 함수
def initialize_model(user_role):
    # API 키 설정
    genai.configure(api_key=API_KEY)
    
    # 시스템 프롬프트 설정 (사용자 역할이 포함됨)
    system_prompt = f"""
    [규칙]: 당신은 아래 6명의 캐릭터를 동시에 연기합니다. 사용자 역할에 맞게 자연스럽게 2~4명이 대화에 참여하세요. 출력 형식은 반드시 "[이름]: 대사"로만 작성합니다. (지문 금지, 구어체 사용)

    [캐릭터 명단]: {CHARACTERS}
    [사용자(User) 설정]: 사용자는 **'{user_role}'**입니다.
    """
    
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt
    )
    # Streamlit은 st.session_state를 사용하여 대화 기록을 유지합니다.
    return model.start_chat(history=[]) # <--- 무조건 빈 리스트로 시작

# ===================================================
# ⭐️ 웹 인터페이스 (UI) 구현
# ===================================================

# 1. 사용자 역할 선택 UI
role_options = ["어리버리한 신입 부원", "정체불명의 해킹범", "대화는 안 통하는 '귀신'", "직접 입력..."]
selected_role = st.sidebar.selectbox("당신의 정체를 선택하세요:", role_options)

if selected_role == "직접 입력...":
    user_role = st.sidebar.text_input("직접 역할을 입력하세요:")
else:
    user_role = selected_role

# 세션 초기화 (모델과 대화 기록)
if 'chat' not in st.session_state or st.sidebar.button("새 채팅 시작"):
    if user_role:
        st.session_state.chat = initialize_model(user_role)
        st.session_state.messages = []
        st.session_state.initial_message_sent = False
        st.sidebar.success(f"✅ 당신은 [{user_role}]로 입장합니다.")
    else:
        st.sidebar.warning("역할을 먼저 입력해 주세요.")

# 2. 대화 기록 표시
if 'chat' not in st.session_state or st.sidebar.button("새 채팅 시작"):
    if user_role:
        # 1. 메시지 기록을 먼저 비웁니다. (KeyError 방지)
        st.session_state.messages = []
        
        # 2. 비워진 기록으로 모델을 초기화합니다.
        st.session_state.chat = initialize_model(user_role)
        
        st.session_state.initial_message_sent = False
        st.sidebar.success(f"✅ 당신은 [{user_role}]로 입장합니다.")
    else:
        st.sidebar.warning("역할을 먼저 입력해 주세요.")

    # 입장 메시지 자동 전송 (최초 1회)
    if not st.session_state.initial_message_sent:
        initial_input = f"(시스템 알림: '{user_role}'님이 입장하셨습니다.)"
        with st.spinner('캐릭터들이 당신의 입장을 인식 중...'):
            response = st.session_state.chat.send_message(initial_input)
            
            # 사용자 메시지로 저장
            st.session_state.messages.append({"role": "user", "content": initial_input})
            
            # AI 메시지로 저장
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.session_state.initial_message_sent = True
            st.rerun()

    # 3. 사용자 입력 처리
    if prompt := st.chat_input("채팅을 입력하세요..."):
        # 사용자 메시지를 화면에 표시 및 저장
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Gemini API 호출 및 응답
        with st.spinner('캐릭터들이 대화 중...'):
            response = st.session_state.chat.send_message(prompt)
        
        # AI 응답을 화면에 표시 및 저장
        with st.chat_message("assistant"):
            st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
