import streamlit as st
import google.generativeai as genai
import sys
import re # 파싱(분리)을 위해 re 모듈 사용

# ===================================================
# ⭐️ 1. 파싱 함수 정의 (캐릭터별 말풍선 분리)
# ===================================================

# Gemini 응답 텍스트를 [이름]: 대사 형식으로 분리하고 출력하는 함수
def parse_and_display_response(response_text, is_initial=False):
    # 정규식: 대괄호 안의 이름과 콜론을 찾음 (예: [강건우]:)
    # \n*(\[.+?\]:\s*) : 줄바꿈(선택적) 후 [이름]: 공백을 찾음
    pattern = re.compile(r'\n*(\[[^\]]+\]:\s*)') 
    
    # 패턴 기준으로 텍스트를 나눔
    parts = pattern.split(response_text)
    
    messages_to_save = []
    
    # parts 리스트: 빈 문자열, [이름]:, 대사, [이름]:, 대사 순서로 구성됨
    for i in range(1, len(parts), 2):
        speaker = parts[i].strip() # [강건우]:
        dialogue = parts[i+1].strip() # 대화 내용
        
        if dialogue: 
            # 말풍선에 출력
            with st.chat_message("assistant"):
                st.markdown(f"**{speaker}** {dialogue}") 
            
            # 세션 상태에 저장할 형식
            messages_to_save.append({"role": "assistant", "content": f"**{speaker}** {dialogue}"})
            
    # 입장 메시지 처리 후 바로 st.rerun()을 호출하는 경우 (초기화 단계)
    if is_initial:
        st.session_state.messages.extend(messages_to_save)
        st.session_state.initial_message_sent = True
        st.rerun()
    
    return messages_to_save

# ===================================================
# ⭐️ 2. 기본 설정 및 데이터
# ===================================================

st.set_page_config(page_title="7인 자캐 단톡방 시뮬레이터", layout="wide")
st.title("📱 7인 자캐 단톡방 시뮬레이터")

# ⚠️ 보안된 API 키 로드 (Streamlit Secrets 사용)
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("오류: Gemini API 키(GEMINI_API_KEY)가 Streamlit Secrets에 설정되지 않았습니다.")
    st.stop()

# 자캐 6명 설정
CHARACTERS = """
1. [강건우]: 20대 초반, 다혈질, 행동파. 리더인 척하지만 허당임. 말투가 거칠음.
2. [이서아]: 20대 초반, 차가운 이성주의자. 안경캐. 팩트폭격을 주로 함.
3. [김포포]: 10대 후반, 4차원, 귀여운 척함. 이모티콘 많이 씀. 눈치가 없음.
4. [박현수]: 20대 중반, 피곤에 찌든 대학원생. 만사가 귀찮음. 
5. [최유리]: 20대 초반, 인싸, 유행어 많이 씀. 분위기 메이커.
6. [정태민]: 20대 초반, 소심함, 말끝을 흐림. 착하지만 답답함.
"""

# ===================================================
# ⭐️ 3. 모델 초기화 함수
# ===================================================

# API 호출을 최소화하기 위해 @st.cache_resource 사용 (KeyError 방지용 history=[])
@st.cache_resource 
def initialize_model(user_role):
    genai.configure(api_key=API_KEY)
    
    system_prompt = f"""
    [규칙]: 당신은 아래 6명의 캐릭터를 동시에 연기합니다. 사용자 역할에 맞게 자연스럽게 2~4명이 대화에 참여하세요. 출력 형식은 반드시 "[이름]: 대사"로만 작성합니다. (지문 금지, 구어체 사용)

    [캐릭터 명단]: {CHARACTERS}
    [사용자(User) 설정]: 사용자는 **'{user_role}'입니다.
    """
    
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt
    )
    # 채팅 세션을 항상 빈 기록으로 시작합니다.
    return model.start_chat(history=[])

# ===================================================
# ⭐️ 4. 웹 인터페이스 (UI) 구현 및 로직
# ===================================================

# 1. 사용자 역할 선택 UI (사이드바)
role_options = ["어리버리한 신입 부원", "정체불명의 해킹범", "대화는 안 통하는 '귀신'", "직접 입력..."]
selected_role = st.sidebar.selectbox("당신의 정체를 선택하세요:", role_options)

if selected_role == "직접 입력...":
    user_role = st.sidebar.text_input("직접 역할을 입력하세요:")
else:
    user_role = selected_role

# 2. 세션 초기화 및 새 채팅 시작 버튼 (버튼 ID 충돌 방지 key 추가)
if 'chat' not in st.session_state or st.sidebar.button("새 채팅 시작", key="restart_chat_btn"): 
    if user_role:
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
                
                # 사용자 입장 메시지 저장
                st.session_state.messages.append({"role": "user", "content": initial_input})
                
                # 🚨 파싱 함수를 통해 입장 메시지 저장 및 출력 후 st.rerun() 호출
                parse_and_display_response(response.text, is_initial=True) 
                
            except Exception as e:
                st.error(f"API 호출 중 오류 발생: {e}")
                st.stop()

# 4. 사용자 입력 처리 (입력창이 항상 보이도록 조건문 밖, 파일의 가장 아래에 위치)
if prompt := st.chat_input("채팅을 입력하세요..."):
    
    # 채팅 객체가 없으면 입력 처리를 중단합니다. (초기화 전 입력 방지)
    if 'chat' not in st.session_state:
        st.warning("먼저 역할을 선택하고 '새 채팅 시작' 버튼을 눌러주세요.")
        st.stop()
        
    # 사용자 메시지 저장
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Gemini API 호출 및 응답
    with st.spinner('캐릭터들이 대화 중...'):
        try:
            response = st.session_state.chat.send_message(prompt)
            full_response_text = response.text 
        except Exception as e:
            st.error(f"API 호출 중 오류 발생: {e}")
            st.stop()
    
    # 응답 파싱 및 저장
    parsed_messages = parse_and_display_response(full_response_text)
    st.session_state.messages.extend(parsed_messages)
