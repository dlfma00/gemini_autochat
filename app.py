import streamlit as st
import google.generativeai as genai
import sys
# ===================================================
# ⭐️ app.py 상단 (import문 아래)에 추가하세요
# ===================================================

# Gemini 응답 텍스트를 [이름]: 대사 형식으로 분리하는 함수
def parse_and_display_response(response_text):
    # 정규표현식을 사용해 "[이름]:" 패턴을 기준으로 텍스트를 나눕니다.
    # 예: "[강건우]: 안녕하세요"
    import re
    
    # 정규식: 대괄호 안의 이름과 콜론을 찾음 (예: [강건우]:)
    pattern = re.compile(r'(\[[^\]]+\]:\s*)')
    
    # 패턴 기준으로 텍스트를 나눔 (이름이 포함된 구분자도 유지)
    parts = pattern.split(response_text)
    
    messages_to_save = []
    
    # parts 리스트는 빈 문자열, 이름+콜론, 대사, 이름+콜론, 대사 순서로 나옵니다.
    for i in range(1, len(parts), 2):
        speaker = parts[i].strip() # [강건우]:
        dialogue = parts[i+1].strip() # 대화 내용
        
        if dialogue: # 대화 내용이 비어있지 않다면
            # 말풍선에 출력
            with st.chat_message("assistant"):
                st.markdown(f"**{speaker}** {dialogue}") # 이름은 굵게 표시
            
            # 세션 상태에 저장할 형식 (나중에 다시 로드할 때 필요)
            messages_to_save.append({"role": "assistant", "content": f"**{speaker}** {dialogue}"})
            
    return messages_to_save

# ===================================================
# ⭐️ 여기까지 추가합니다.
# ===================================================
# ===================================================
# ⭐️ 1. 기본 설정 및 데이터
# ===================================================

# Streamlit 설정: 웹페이지 제목 및 레이아웃 설정
st.set_page_config(page_title="7인 자캐 단톡방 시뮬레이터", layout="wide")
st.title("📱 7인 자캐 단톡방 시뮬레이터")

# ⚠️ 보안된 API 키 로드
try:
    # Streamlit Cloud Secrets에서 안전하게 키를 가져옵니다.
    API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("오류: Gemini API 키(GEMINI_API_KEY)가 Streamlit Secrets에 설정되지 않았습니다.")
    st.stop() # 키가 없으면 앱 실행을 멈춥니다.

# 자캐 6명 설정 (여기에 친구들 캐릭터 설정을 자세히 넣어주세요!)
CHARACTERS = """
1. [강건우]: 20대 초반, 다혈질, 행동파. 리더인 척하지만 허당임. 말투가 거칠음.
2. [이서아]: 20대 초반, 차가운 이성주의자. 안경캐. 팩트폭격을 주로 함.
3. [김포포]: 10대 후반, 4차원, 귀여운 척함. 이모티콘 많이 씀. 눈치가 없음.
4. [박현수]: 20대 중반, 피곤에 찌든 대학원생. 만사가 귀찮음. 
5. [최유리]: 20대 초반, 인싸, 유행어 많이 씀. 분위기 메이커.
6. [정태민]: 20대 초반, 소심함, 말끝을 흐림. 착하지만 답답함.
"""

# ===================================================
# ⭐️ 2. 모델 초기화 함수
# ===================================================

# @st.cache_resource 데코레이터는 제거했습니다. (KeyError 방지)
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
    # ChatSession은 항상 빈 기록으로 시작합니다. (KeyError 방지)
    return model.start_chat(history=[])

# ===================================================
# ⭐️ 3. 웹 인터페이스 (UI) 구현
# ===================================================

# 1. 사용자 역할 선택 UI (사이드바)
role_options = ["어리버리한 신입 부원", "정체불명의 해킹범", "대화는 안 통하는 '귀신'", "직접 입력..."]
selected_role = st.sidebar.selectbox("당신의 정체를 선택하세요:", role_options)

if selected_role == "직접 입력...":
    user_role = st.sidebar.text_input("직접 역할을 입력하세요:")
else:
    user_role = selected_role

# 2. 세션 초기화 및 새 채팅 시작 버튼 (버튼 ID 중복 오류 방지 위해 key="restart_chat_btn" 추가)
# 이 블록이 앱의 핵심 초기화 로직입니다.
if 'chat' not in st.session_state or st.sidebar.button("새 채팅 시작", key="restart_chat_btn"): 
    if user_role:
        # 메시지 기록을 먼저 비우고 모델을 초기화합니다.
        st.session_state.messages = []
        st.session_state.chat = initialize_model(user_role)
        
        st.session_state.initial_message_sent = False
        st.sidebar.success(f"✅ 당신은 [{user_role}]로 입장합니다.")
    else:
        st.sidebar.warning("역할을 먼저 입력해 주세요.")
    
# 3. 대화 기록 표시 및 입장 메시지 전송
if 'chat' in st.session_state:
    # 대화 기록 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 입장 메시지 자동 전송 (최초 1회)
    if not st.session_state.initial_message_sent:
        initial_input = f"(시스템 알림: '{user_role}'님이 입장하셨습니다.)"
        with st.spinner('캐릭터들이 당신의 입장을 인식 중...'):
            try:
                response = st.session_state.chat.send_message(initial_input)
                
                # 메시지 저장
                st.session_state.messages.append({"role": "user", "content": initial_input})
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.session_state.initial_message_sent = True
                st.rerun()
            except Exception as e:
                st.error(f"API 호출 중 오류 발생: {e}")
                st.stop()


    # 4. 사용자 입력 처리
    if prompt := st.chat_input("채팅을 입력하세요..."):
        # 사용자 메시지 저장
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Gemini API 호출 및 응답
        with st.spinner('캐릭터들이 대화 중...'):
            try:
                response = st.session_state.chat.send_message(prompt)
            except Exception as e:
                st.error(f"API 호출 중 오류 발생: {e}")
                st.stop()
        
        # AI 응답을 화면에 표시 및 저장
        with st.chat_message("assistant"):
            st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
